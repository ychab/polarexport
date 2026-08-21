import logging
import os
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path

import pytest

from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.stores.filesystem_exercise import FilesystemExerciseStore

from tests.unit.factories.ports.stores.exercise import StoredExerciseFactory


class TestFilesystemExerciseStore:
    @pytest.fixture
    def store(self, tmp_path: Path) -> FilesystemExerciseStore:
        return FilesystemExerciseStore(data_dir=tmp_path, api="polar-accesslink-v3")

    async def test__write_then_read__round_trips_payload(self, store: FilesystemExerciseStore) -> None:
        stored = StoredExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18), payload={"foo": "bar"})

        await store.write(stored)
        result = await store.read(DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18)))

        assert result["54klrKbL"].payload == {"foo": "bar"}
        assert result["54klrKbL"].fetched_at == stored.fetched_at

    async def test__write__creates_exact_directory_layout(
        self, store: FilesystemExerciseStore, tmp_path: Path
    ) -> None:
        stored = StoredExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))

        await store.write(stored)

        expected_path = tmp_path / "polar-accesslink-v3" / "exercise" / "2026" / "08" / "2026-08-18-54klrKbL.json"
        assert expected_path.is_file()

    async def test__two_sessions_same_day__both_round_trip_with_distinct_filenames(
        self, store: FilesystemExerciseStore, tmp_path: Path
    ) -> None:
        first = StoredExerciseFactory.build(id="aaaaaaaa", date=date(2026, 8, 18), payload={"session": 1})
        second = StoredExerciseFactory.build(id="bbbbbbbb", date=date(2026, 8, 18), payload={"session": 2})

        await store.write(first)
        await store.write(second)

        month_dir = tmp_path / "polar-accesslink-v3" / "exercise" / "2026" / "08"
        assert set(month_dir.glob("*.json")) == {
            month_dir / "2026-08-18-aaaaaaaa.json",
            month_dir / "2026-08-18-bbbbbbbb.json",
        }
        result = await store.read(DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18)))
        assert result["aaaaaaaa"].payload == {"session": 1}
        assert result["bbbbbbbb"].payload == {"session": 2}

    async def test__read__range_scoped_to_touched_months_only(self, store: FilesystemExerciseStore) -> None:
        await store.write(StoredExerciseFactory.build(id="julySession", date=date(2026, 7, 15), payload={"m": 7}))
        await store.write(StoredExerciseFactory.build(id="aug1Session", date=date(2026, 8, 5), payload={"m": 8.1}))
        await store.write(StoredExerciseFactory.build(id="aug2Session", date=date(2026, 8, 20), payload={"m": 8.2}))

        result = await store.read(DateRange(date_min=date(2026, 8, 1), date_max=date(2026, 8, 31)))

        assert set(result.keys()) == {"aug1Session", "aug2Session"}

    async def test__read__month_with_no_directory__is_skipped(self, store: FilesystemExerciseStore) -> None:
        result = await store.read(DateRange(date_min=date(2026, 6, 1), date_max=date(2026, 6, 30)))

        assert result == {}

    async def test__read__corrupt_file_logs_warning_and_is_skipped(
        self,
        store: FilesystemExerciseStore,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        await store.write(StoredExerciseFactory.build(id="goodSession", date=date(2026, 8, 10), payload={"a": 1}))
        corrupt_path = tmp_path / "polar-accesslink-v3" / "exercise" / "2026" / "08" / "2026-08-11-badSession.json"
        corrupt_path.write_text("not valid json {", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = await store.read(DateRange(date_min=date(2026, 8, 10), date_max=date(2026, 8, 11)))

        assert set(result.keys()) == {"goodSession"}
        assert any(record.levelno == logging.WARNING for record in caplog.records)
        assert corrupt_path.exists()  # a bad file is never deleted, only skipped

    async def test__known_ids__empty_store__returns_empty_frozenset(self, store: FilesystemExerciseStore) -> None:
        result = await store.known_ids()

        assert result == frozenset()

    async def test__known_ids__after_writes__returns_all_ids(self, store: FilesystemExerciseStore) -> None:
        await store.write(StoredExerciseFactory.build(id="aaaaaaaa", date=date(2026, 7, 15)))
        await store.write(StoredExerciseFactory.build(id="bbbbbbbb", date=date(2026, 8, 5)))
        await store.write(StoredExerciseFactory.build(id="cccccccc", date=date(2026, 8, 20)))

        result = await store.known_ids()

        assert result == frozenset({"aaaaaaaa", "bbbbbbbb", "cccccccc"})

    async def test__access_token_never_appears_in_stored_files(
        self, store: FilesystemExerciseStore, tmp_path: Path
    ) -> None:
        access_token = os.environ["POLAR_ACCESS_TOKEN"]
        stored = StoredExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18), payload={"a": 1})

        await store.write(stored)

        for path in tmp_path.rglob("*.json"):
            assert access_token not in path.read_text(encoding="utf-8")


class TestFilesystemExerciseStoreAvailability:
    @pytest.fixture
    def store(self, tmp_path: Path) -> FilesystemExerciseStore:
        return FilesystemExerciseStore(data_dir=tmp_path, api="polar-accesslink-v3")

    async def test__never_written__read_returns_none(self, store: FilesystemExerciseStore) -> None:
        result = await store.read_availability()

        assert result is None

    async def test__write_then_read__round_trips(self, store: FilesystemExerciseStore) -> None:
        await store.write_availability(SourceAvailability.UNAVAILABLE, observed_at=datetime(2026, 8, 18, tzinfo=UTC))

        result = await store.read_availability()

        assert result == SourceAvailability.UNAVAILABLE

    async def test__write_twice__overwrites_with_latest_observation(self, store: FilesystemExerciseStore) -> None:
        await store.write_availability(SourceAvailability.UNAVAILABLE, observed_at=datetime(2026, 8, 17, tzinfo=UTC))
        await store.write_availability(SourceAvailability.AVAILABLE, observed_at=datetime(2026, 8, 18, tzinfo=UTC))

        result = await store.read_availability()

        assert result == SourceAvailability.AVAILABLE

    async def test__write__creates_status_file_at_expected_path(
        self, store: FilesystemExerciseStore, tmp_path: Path
    ) -> None:
        await store.write_availability(SourceAvailability.AVAILABLE, observed_at=datetime(2026, 8, 18, tzinfo=UTC))

        assert (tmp_path / "polar-accesslink-v3" / "exercise" / "_status.json").is_file()

    async def test__known_ids__ignores_status_file(self, store: FilesystemExerciseStore) -> None:
        await store.write_availability(SourceAvailability.AVAILABLE, observed_at=datetime(2026, 8, 18, tzinfo=UTC))
        await store.write(StoredExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18)))

        result = await store.known_ids()

        assert result == frozenset({"54klrKbL"})

    async def test__read__corrupt_file_logs_warning_and_returns_none(
        self,
        store: FilesystemExerciseStore,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        status_path = tmp_path / "polar-accesslink-v3" / "exercise" / "_status.json"
        status_path.parent.mkdir(parents=True)
        status_path.write_text("not valid json {", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = await store.read_availability()

        assert result is None
        assert any(record.levelno == logging.WARNING for record in caplog.records)
