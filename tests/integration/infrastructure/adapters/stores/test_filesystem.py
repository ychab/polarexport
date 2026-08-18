import logging
import os
from datetime import date
from pathlib import Path

import pytest

from polarexport.domain.enums import NightSource
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore

from tests.unit.factories.ports.stores.night import StoredPayloadFactory


class TestFilesystemNightStore:
    @pytest.fixture
    def store(self, tmp_path: Path) -> FilesystemNightStore:
        return FilesystemNightStore(data_dir=tmp_path, api="polar-accesslink-v3")

    async def test__write_then_read__round_trips_payload(self, store: FilesystemNightStore) -> None:
        stored = StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 15), payload={"foo": "bar"})

        await store.write(stored)
        result = await store.read(NightSource.SLEEP, DateRange(date_min=date(2026, 8, 15), date_max=date(2026, 8, 15)))

        assert result[date(2026, 8, 15)].payload == {"foo": "bar"}
        assert result[date(2026, 8, 15)].fetched_at == stored.fetched_at

    async def test__write_then_read__none_payload_round_trips(self, store: FilesystemNightStore) -> None:
        stored = StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 15), payload=None)

        await store.write(stored)
        result = await store.read(NightSource.SLEEP, DateRange(date_min=date(2026, 8, 15), date_max=date(2026, 8, 15)))

        assert result[date(2026, 8, 15)].payload is None

    async def test__write__creates_exact_directory_layout(self, store: FilesystemNightStore, tmp_path: Path) -> None:
        stored = StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 15), payload={"foo": "bar"})

        await store.write(stored)

        expected_path = tmp_path / "polar-accesslink-v3" / "sleep" / "2026" / "08" / "2026-08-15.json"
        assert expected_path.is_file()

    async def test__write_twice__overwrites_cleanly(self, store: FilesystemNightStore) -> None:
        first = StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 15), payload={"v": 1})
        second = StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 15), payload={"v": 2})

        await store.write(first)
        await store.write(second)

        result = await store.read(NightSource.SLEEP, DateRange(date_min=date(2026, 8, 15), date_max=date(2026, 8, 15)))
        assert result[date(2026, 8, 15)].payload == {"v": 2}

    async def test__read__range_with_holes_returns_only_present_dates(self, store: FilesystemNightStore) -> None:
        await store.write(
            StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 10), payload={"a": 1})
        )
        await store.write(
            StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 12), payload={"a": 2})
        )

        result = await store.read(NightSource.SLEEP, DateRange(date_min=date(2026, 8, 10), date_max=date(2026, 8, 12)))

        assert set(result.keys()) == {date(2026, 8, 10), date(2026, 8, 12)}

    async def test__read__corrupt_file_logs_warning_and_is_skipped(
        self,
        store: FilesystemNightStore,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        await store.write(
            StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 10), payload={"a": 1})
        )
        corrupt_path = tmp_path / "polar-accesslink-v3" / "sleep" / "2026" / "08" / "2026-08-11.json"
        corrupt_path.write_text("not valid json {", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = await store.read(
                NightSource.SLEEP, DateRange(date_min=date(2026, 8, 10), date_max=date(2026, 8, 11))
            )

        assert set(result.keys()) == {date(2026, 8, 10)}
        assert any(record.levelno == logging.WARNING for record in caplog.records)
        assert corrupt_path.exists()  # a bad file is never deleted, only skipped

    async def test__access_token_never_appears_in_stored_files(
        self, store: FilesystemNightStore, tmp_path: Path
    ) -> None:
        access_token = os.environ["POLAR_ACCESS_TOKEN"]
        stored = StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 15), payload={"a": 1})

        await store.write(stored)

        for path in tmp_path.rglob("*.json"):
            assert access_token not in path.read_text(encoding="utf-8")
