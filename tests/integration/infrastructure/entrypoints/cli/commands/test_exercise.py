import json
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

from polarexport.application.inputs.exercise import ExerciseExportInput
from polarexport.application.inputs.exercise import ExerciseSyncInput
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.stores.filesystem_exercise import FilesystemExerciseStore
from polarexport.infrastructure.adapters.stores.json_credentials import JsonCredentialsStore
from polarexport.infrastructure.adapters.stores.json_profile import JsonProfileStore
from polarexport.infrastructure.entrypoints.cli.commands import exercise as exercise_module
from polarexport.infrastructure.entrypoints.cli.commands.exercise import exercise_logic

from tests.integration.utils.wiremock import WireMockContext


@pytest.fixture
def date_range() -> DateRange:
    return DateRange(date_min=date(2026, 8, 17), date_max=date(2026, 8, 20))


@pytest.fixture
def today() -> date:
    return date(2026, 8, 20)


@pytest.fixture
def generated_at() -> datetime:
    return datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def wiremock_exercise_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FilesystemExerciseStore:
    store = FilesystemExerciseStore(data_dir=tmp_path / "data")
    monkeypatch.setattr(exercise_module, "get_exercise_store", lambda: store)
    return store


@pytest.fixture(autouse=True)
def wiremock_profile_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JsonProfileStore:
    store = JsonProfileStore(data_dir=tmp_path / "data")
    monkeypatch.setattr(exercise_module, "get_profile_store", lambda: store)
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

    monkeypatch.setattr(exercise_module, "get_polar_client", _get_polar_client)


@pytest.mark.wiremock
class TestExerciseLogic:
    async def test__happy_path__archive_written_from_wiremock_data(
        self,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        tmp_path: Path,
    ) -> None:
        sync_in = ExerciseSyncInput()
        export_in = ExerciseExportInput(date_range=date_range, output_dir=tmp_path)

        sync_report, export_report = await exercise_logic(sync_in, export_in, today=today, generated_at=generated_at)

        assert sync_report is not None
        assert sync_report.fetched == 3
        assert export_report.archive_path.exists()
        with zipfile.ZipFile(export_report.archive_path) as archive:
            names = archive.namelist()
            assert "manifest.json" in names
            assert "README.md" in names
            assert "exercises.json" in names
            assert any(name.startswith("raw/exercise/") for name in names)

            document = json.loads(archive.read("exercises.json"))
            sessions = {session["id"]: session for session in document["exercises"]}
            kickboxing = sessions["54klrKbL"]
            assert kickboxing["heart_rate"]["minimum"] is not None
            assert kickboxing["heart_rate"]["minimum"] < kickboxing["heart_rate"]["average"]
            assert kickboxing["heart_rate_per_minute"] is not None

    async def test__second_run__known_sessions_skipped_not_rewritten(
        self,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        tmp_path: Path,
        polar_wiremock: WireMockContext,
    ) -> None:
        # `GET /v3/exercises` has no date filter, so — unlike `night`'s per-date caching — every sync
        # re-fetches everything Polar still holds; the second run costs the same fixed number of
        # requests (exercises + profile) instead of zero. Deduplication happens after the fetch, by
        # id: known sessions are skipped, not rewritten.
        sync_in = ExerciseSyncInput()
        first_export_in = ExerciseExportInput(date_range=date_range, output_dir=tmp_path)
        await exercise_logic(sync_in, first_export_in, today=today, generated_at=generated_at)

        request_count_before = polar_wiremock.count_requests()

        second_export_in = ExerciseExportInput(date_range=date_range, output_dir=tmp_path, force=True)
        sync_report, export_report = await exercise_logic(
            sync_in, second_export_in, today=today, generated_at=generated_at
        )

        assert polar_wiremock.count_requests() == request_count_before + 2
        assert sync_report is not None
        assert sync_report.fetched == 0
        assert sync_report.skipped == 3
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

        sync_in = ExerciseSyncInput()
        export_in = ExerciseExportInput(date_range=date_range, output_dir=tmp_path)

        with caplog.at_level(logging.DEBUG):
            _, export_report = await exercise_logic(sync_in, export_in, today=today, generated_at=generated_at)

        assert export_report.archive_path.exists()
        with zipfile.ZipFile(export_report.archive_path) as archive:
            for name in archive.namelist():
                assert dummy_token not in archive.read(name).decode("utf-8")
        assert dummy_token not in caplog.text
        assert credentials_path.is_file()
