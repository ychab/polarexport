from datetime import date
from pathlib import Path

import pytest

from polarexport.domain.enums import NightSource
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore

from tests.unit.factories.ports.stores.night import StoredPayloadFactory


class TestFilesystemNightStoreMissing:
    @pytest.fixture
    def store(self, tmp_path: Path) -> FilesystemNightStore:
        return FilesystemNightStore(data_dir=tmp_path, api="polar-accesslink-v3")

    @pytest.fixture
    def today(self) -> date:
        return date(2026, 8, 17)  # history window starts 2026-07-21

    @pytest.fixture
    def day_inside_window(self) -> date:
        return date(2026, 8, 10)

    @pytest.fixture
    def day_outside_window(self) -> date:
        return date(2026, 7, 1)

    async def test__not_stored__inside_window__is_missing(
        self, store: FilesystemNightStore, today: date, day_inside_window: date
    ) -> None:
        result = await store.missing(NightSource.SLEEP, (day_inside_window,), today=today)

        assert result == (day_inside_window,)

    async def test__not_stored__outside_window__is_missing(
        self, store: FilesystemNightStore, today: date, day_outside_window: date
    ) -> None:
        result = await store.missing(NightSource.SLEEP, (day_outside_window,), today=today)

        assert result == (day_outside_window,)

    async def test__stored_with_payload__inside_window__not_missing(
        self, store: FilesystemNightStore, today: date, day_inside_window: date
    ) -> None:
        await store.write(
            StoredPayloadFactory.build(source=NightSource.SLEEP, date=day_inside_window, payload={"a": 1})
        )

        result = await store.missing(NightSource.SLEEP, (day_inside_window,), today=today)

        assert result == ()

    async def test__stored_with_payload__outside_window__not_missing(
        self, store: FilesystemNightStore, today: date, day_outside_window: date
    ) -> None:
        await store.write(
            StoredPayloadFactory.build(source=NightSource.SLEEP, date=day_outside_window, payload={"a": 1})
        )

        result = await store.missing(NightSource.SLEEP, (day_outside_window,), today=today)

        assert result == ()

    async def test__stored_empty__inside_window__is_missing(
        self, store: FilesystemNightStore, today: date, day_inside_window: date
    ) -> None:
        await store.write(StoredPayloadFactory.build(source=NightSource.SLEEP, date=day_inside_window, payload=None))

        result = await store.missing(NightSource.SLEEP, (day_inside_window,), today=today)

        assert result == (day_inside_window,)

    async def test__stored_empty__outside_window__not_missing(
        self, store: FilesystemNightStore, today: date, day_outside_window: date
    ) -> None:
        await store.write(StoredPayloadFactory.build(source=NightSource.SLEEP, date=day_outside_window, payload=None))

        result = await store.missing(NightSource.SLEEP, (day_outside_window,), today=today)

        assert result == ()


class TestFilesystemNightStoreWrite:
    @pytest.fixture
    def failing_json_dump(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(*args: object, **kwargs: object) -> None:
            raise ValueError("boom")

        monkeypatch.setattr("polarexport.infrastructure.adapters.stores.filesystem.json.dump", _raise)

    async def test__serialisation_fails__temp_file_is_cleaned_up(
        self, tmp_path: Path, failing_json_dump: None
    ) -> None:
        store = FilesystemNightStore(data_dir=tmp_path, api="polar-accesslink-v3")
        stored = StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 15), payload={"a": 1})

        with pytest.raises(ValueError, match="boom"):
            await store.write(stored)

        month_dir = tmp_path / "polar-accesslink-v3" / "sleep" / "2026" / "08"
        assert list(month_dir.iterdir()) == []

    async def test__write__creates_missing_parent_directories(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "fresh" / "data"
        store = FilesystemNightStore(data_dir=data_dir, api="polar-accesslink-v3")
        stored = StoredPayloadFactory.build(source=NightSource.SLEEP, date=date(2026, 8, 15), payload={"a": 1})

        await store.write(stored)

        assert (data_dir / "polar-accesslink-v3" / "sleep" / "2026" / "08" / "2026-08-15.json").is_file()
