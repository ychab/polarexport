import json
import logging
from datetime import date
from pathlib import Path

import pytest

from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.stores.filesystem_exercise import FilesystemExerciseStore

from tests.unit.factories.ports.stores.exercise import StoredExerciseFactory


class TestFilesystemExerciseStoreWrite:
    @pytest.fixture
    def failing_json_dump(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(*args: object, **kwargs: object) -> None:
            raise ValueError("boom")

        monkeypatch.setattr("polarexport.infrastructure.adapters.stores.filesystem_exercise.json.dump", _raise)

    async def test__serialisation_fails__temp_file_is_cleaned_up(
        self, tmp_path: Path, failing_json_dump: None
    ) -> None:
        store = FilesystemExerciseStore(data_dir=tmp_path, api="polar-accesslink-v3")
        stored = StoredExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))

        with pytest.raises(ValueError, match="boom"):
            await store.write(stored)

        month_dir = tmp_path / "polar-accesslink-v3" / "exercise" / "2026" / "08"
        assert list(month_dir.iterdir()) == []

    async def test__write__creates_missing_parent_directories(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "fresh" / "data"
        store = FilesystemExerciseStore(data_dir=data_dir, api="polar-accesslink-v3")
        stored = StoredExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))

        await store.write(stored)

        assert (data_dir / "polar-accesslink-v3" / "exercise" / "2026" / "08" / "2026-08-18-54klrKbL.json").is_file()

    async def test__stored_api_mismatches_store_api__raises_value_error(self, tmp_path: Path) -> None:
        store = FilesystemExerciseStore(data_dir=tmp_path, api="polar-accesslink-v3")
        stored = StoredExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18), api="some-other-api")

        with pytest.raises(ValueError, match="some-other-api"):
            await store.write(stored)

        assert list(tmp_path.iterdir()) == []


class TestFilesystemExerciseStoreRead:
    @pytest.fixture
    def store(self, tmp_path: Path) -> FilesystemExerciseStore:
        return FilesystemExerciseStore(data_dir=tmp_path, api="polar-accesslink-v3")

    async def test__envelope_missing_id__skipped_and_warns(
        self, store: FilesystemExerciseStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        month_dir = tmp_path / "polar-accesslink-v3" / "exercise" / "2026" / "08"
        month_dir.mkdir(parents=True)
        (month_dir / "2026-08-18-54klrKbL.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "api": "polar-accesslink-v3",
                    "date": "2026-08-18",
                    "fetched_at": "2026-08-18T12:00:00+00:00",
                    "payload": {},
                }
            ),
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING):
            result = await store.read(DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18)))

        assert result == {}
        assert any(record.levelno == logging.WARNING for record in caplog.records)
