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

from polarexport.application.inputs.night import NightExportInput
from polarexport.application.inputs.night import NightSyncInput
from polarexport.domain.enums import NightSource
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore
from polarexport.infrastructure.entrypoints.cli.commands import night as night_module
from polarexport.infrastructure.entrypoints.cli.commands.night import night_logic

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
