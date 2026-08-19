import logging
import os
import zipfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path

from pydantic import HttpUrl

import pytest
from typer.testing import CliRunner

from polarexport.application.inputs.night import NightExportInput
from polarexport.application.inputs.night import NightSyncInput
from polarexport.domain.enums import NightSource
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore
from polarexport.infrastructure.adapters.stores.json_credentials import JsonCredentialsStore
from polarexport.infrastructure.config.settings.app import app_settings
from polarexport.infrastructure.config.settings.polar import polar_settings
from polarexport.infrastructure.entrypoints.cli.commands import night as night_module
from polarexport.infrastructure.entrypoints.cli.commands.night import night_logic
from polarexport.infrastructure.entrypoints.cli.main import app as cli_app

from tests.integration.utils.wiremock import WireMockContext


@pytest.fixture
def date_range() -> DateRange:
    day = date(2026, 8, 15)
    return DateRange(date_min=day, date_max=day)


@pytest.fixture
def today() -> date:
    return date(2026, 8, 15)


@pytest.fixture
def generated_at() -> datetime:
    return datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def wiremock_night_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FilesystemNightStore:
    store = FilesystemNightStore(data_dir=tmp_path / "data")
    monkeypatch.setattr(night_module, "get_night_store", lambda: store)
    return store


@pytest.fixture(autouse=True)
def wiremock_polar_client(monkeypatch: pytest.MonkeyPatch) -> None:
    base_url = os.getenv("WIREMOCK_POLAR_BASE_URL", "")

    @asynccontextmanager
    async def _get_polar_client() -> AsyncIterator[PolarAccessLinkClient]:
        async with PolarAccessLinkClient(
            access_token="dummy-access-token",
            user_id="dummy-user",
            base_url=HttpUrl(base_url),
            concurrency=2,
            verify_ssl=False,
        ) as client:
            yield client

    monkeypatch.setattr(night_module, "get_polar_client", _get_polar_client)


@pytest.mark.wiremock
class TestNightLogic:
    async def test__happy_path__archive_written_from_wiremock_data(
        self,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        tmp_path: Path,
    ) -> None:
        sync_in = NightSyncInput(date_range=date_range, sources=frozenset(NightSource))
        export_in = NightExportInput(date_range=date_range, sources=frozenset(NightSource), output_dir=tmp_path)

        sync_report, export_report = await night_logic(sync_in, export_in, today=today, generated_at=generated_at)

        assert sync_report is not None
        assert export_report.archive_path.exists()
        with zipfile.ZipFile(export_report.archive_path) as archive:
            names = archive.namelist()
            assert "manifest.json" in names
            assert "README.md" in names
            assert "nights.json" in names
            assert any(name.startswith("raw/sleep/") for name in names)

    async def test__second_run__zero_http_requests(
        self,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        tmp_path: Path,
        polar_wiremock: WireMockContext,
    ) -> None:
        # Restricted to the per-date sources (sleep, recharge, heart-rate): their WireMock stub matches
        # any date and always returns data, so a stored payload is never "empty" and the store never
        # asks for it again. skin-temperature/sleepwise stubs return data pinned to one fixed date and
        # would legitimately come back empty for this date_range, which is a distinct behaviour already
        # covered by the NightSyncUseCase unit tests, not what this test is proving.
        sources = frozenset({NightSource.SLEEP, NightSource.RECHARGE, NightSource.HEART_RATE})
        sync_in = NightSyncInput(date_range=date_range, sources=sources)
        first_export_in = NightExportInput(date_range=date_range, sources=sources, output_dir=tmp_path)
        await night_logic(sync_in, first_export_in, today=today, generated_at=generated_at)

        request_count_before = polar_wiremock.count_requests()

        second_export_in = NightExportInput(date_range=date_range, sources=sources, output_dir=tmp_path, force=True)
        sync_report, export_report = await night_logic(
            sync_in, second_export_in, today=today, generated_at=generated_at
        )

        assert polar_wiremock.count_requests() == request_count_before
        assert sync_report is not None
        assert all(stat.fetched == 0 for stat in sync_report.stats.values())
        assert export_report.archive_path.exists()

    async def test__access_token_never_appears_in_archive_or_logs__with_credentials_file_present(
        self,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        dummy_token = "dummy-credentials-file-token-must-never-leak"
        credentials_path = tmp_path / "data" / "auth" / "credentials.json"
        await JsonCredentialsStore().write(
            access_token=dummy_token,
            user_id="dummy-user",
            obtained_at=generated_at,
            expires_in=473040000,
            path=credentials_path,
            force=False,
        )

        sync_in = NightSyncInput(date_range=date_range, sources=frozenset(NightSource))
        export_in = NightExportInput(date_range=date_range, sources=frozenset(NightSource), output_dir=tmp_path)

        with caplog.at_level(logging.DEBUG):
            _, export_report = await night_logic(sync_in, export_in, today=today, generated_at=generated_at)

        assert export_report.archive_path.exists()
        with zipfile.ZipFile(export_report.archive_path) as archive:
            for name in archive.namelist():
                assert dummy_token not in archive.read(name).decode("utf-8")
        assert dummy_token not in caplog.text
        assert credentials_path.is_file()


class TestNightCLIMalformedCredentials:
    @pytest.fixture(autouse=True)
    def wiremock_polar_client(self) -> None:
        """Overrides the module-level autouse fixture of the same name: this test must exercise the
        real credential resolution path in `get_polar_client`, not bypass it with a pre-built client."""
        return None

    def test__malformed_credentials_file__prints_one_sentence__no_traceback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(app_settings, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(polar_settings, "ACCESS_TOKEN", None)
        monkeypatch.setattr(polar_settings, "USER_ID", None)
        credentials_path = tmp_path / "data" / "auth" / "credentials.json"
        credentials_path.parent.mkdir(parents=True)
        credentials_path.write_text('{"schema_version": 2, "user": "x"}', encoding="utf-8")

        result = CliRunner().invoke(cli_app, ["night"])

        assert result.exit_code == 1
        assert "KeyError" not in result.output
        assert "Traceback" not in result.output
        assert "No Polar credentials found" in result.output
