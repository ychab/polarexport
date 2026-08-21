import zipfile
from datetime import date
from pathlib import Path

import pytest

from polarexport.domain.const import EXERCISE_ARCHIVE_NAME_TEMPLATE
from polarexport.domain.exceptions import ArchiveAlreadyExistsError
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.archivers.zip_exercise import ZipExerciseArchiver

from tests.unit.factories.entities.exercise import ExerciseFactory
from tests.unit.factories.entities.exercise_export import ExerciseManifestFactory


class TestZipExerciseArchiverWrite:
    @pytest.fixture
    def date_range(self) -> DateRange:
        return DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18))

    @pytest.fixture
    def archive_name(self, date_range: DateRange) -> str:
        return EXERCISE_ARCHIVE_NAME_TEMPLATE.format(
            date_min=date_range.date_min.isoformat(), date_max=date_range.date_max.isoformat()
        )

    async def test__target_exists_without_force__raises_archive_already_exists_error(
        self, tmp_path: Path, date_range: DateRange, archive_name: str
    ) -> None:
        (tmp_path / archive_name).write_bytes(b"not a real zip")
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        archiver = ZipExerciseArchiver()

        with pytest.raises(ArchiveAlreadyExistsError):
            await archiver.write(
                [exercise], manifest, {}, output_dir=tmp_path, include_raw=False, include_samples=True, force=False
            )

    async def test__target_exists_with_force__is_overwritten(
        self, tmp_path: Path, date_range: DateRange, archive_name: str
    ) -> None:
        target = tmp_path / archive_name
        target.write_bytes(b"not a real zip")
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise], manifest, {}, output_dir=tmp_path, include_raw=False, include_samples=True, force=True
        )

        assert result.path == target
        assert result.path.read_bytes() != b"not a real zip"
        assert result.size_bytes == target.stat().st_size

    async def test__output_dir_missing__is_created(self, tmp_path: Path, date_range: DateRange) -> None:
        output_dir = tmp_path / "fresh" / "export"
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise], manifest, {}, output_dir=output_dir, include_raw=False, include_samples=True, force=False
        )

        assert result.path.is_file()
        assert result.size_bytes == result.path.stat().st_size

    async def test__raw_entry_skipped_when_id_has_no_matching_payload(
        self, tmp_path: Path, date_range: DateRange
    ) -> None:
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise], manifest, {}, output_dir=tmp_path, include_raw=True, include_samples=True, force=False
        )

        with zipfile.ZipFile(result.path) as zip_file:
            assert "raw/exercise/2026-08-18-54klrKbL.json" not in zip_file.namelist()


class TestZipExerciseArchiverWriteSerializationFailure:
    @pytest.fixture
    def failing_readme_render(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(*args: object, **kwargs: object) -> str:
            raise ValueError("boom")

        monkeypatch.setattr("polarexport.infrastructure.adapters.archivers.zip_exercise._render_readme", _raise)

    async def test__serialisation_fails__no_archive_left_behind(
        self, tmp_path: Path, failing_readme_render: None
    ) -> None:
        date_range = DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18))
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        archiver = ZipExerciseArchiver()

        with pytest.raises(ValueError, match="boom"):
            await archiver.write(
                [exercise], manifest, {}, output_dir=tmp_path, include_raw=False, include_samples=True, force=False
            )

        assert list(tmp_path.iterdir()) == []
