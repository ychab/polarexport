import json
import os
import zipfile
from datetime import date
from pathlib import Path

from polarexport.domain.entities.exercise_export import SportSummary
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.archivers.zip_exercise import ZipExerciseArchiver

from tests.unit.factories.entities.exercise import ExerciseFactory
from tests.unit.factories.entities.exercise_export import ExerciseManifestFactory
from tests.unit.factories.entities.profile import UserProfileFactory


class TestZipExerciseArchiverWrite:
    async def test__write__with_include_raw__creates_expected_entries(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18))
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18), heart_rate_per_minute=None)
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        raw = {"54klrKbL": {"id": "54klrKbL", "start_time": "2026-08-18T11:32:08"}}
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise],
            manifest,
            raw,
            output_dir=tmp_path,
            include_raw=True,
            include_samples=True,
            force=False,
        )

        with zipfile.ZipFile(result.path) as zip_file:
            assert set(zip_file.namelist()) == {
                "manifest.json",
                "README.md",
                "exercises.json",
                "raw/exercise/2026-08-18-54klrKbL.json",
            }

    async def test__write__without_include_raw__excludes_raw_directory(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18))
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        raw = {"54klrKbL": {"id": "54klrKbL"}}
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise],
            manifest,
            raw,
            output_dir=tmp_path,
            include_raw=False,
            include_samples=True,
            force=False,
        )

        with zipfile.ZipFile(result.path) as zip_file:
            assert set(zip_file.namelist()) == {"manifest.json", "README.md", "exercises.json"}

    async def test__include_samples_false__heart_rate_per_minute_key_entirely_absent(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18))
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18), heart_rate_per_minute=(98, 112, 131))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise], manifest, {}, output_dir=tmp_path, include_raw=False, include_samples=False, force=False
        )

        with zipfile.ZipFile(result.path) as zip_file:
            document = json.loads(zip_file.read("exercises.json"))
            readme = zip_file.read("README.md").decode("utf-8")

        assert "heart_rate_per_minute" not in document["exercises"][0]
        assert "without" in readme

    async def test__manifest_json__matches_exercise_manifest_totals(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 7, 22), date_max=date(2026, 8, 20))
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        sports = (
            SportSummary(sport="Aerobics", session_count=2, total_duration_seconds=7757.8, total_calories=1125),
            SportSummary(
                sport="Kickboxing Martial Arts", session_count=1, total_duration_seconds=5221.5, total_calories=786
            ),
        )
        manifest = ExerciseManifestFactory.build(
            date_range=date_range,
            availability=SourceAvailability.AVAILABLE,
            exercise_count=3,
            total_duration_seconds=12979.3,
            total_calories=1911,
            sports=sports,
            profile=UserProfileFactory.build(
                birthdate=date(1990, 3, 15), gender="MALE", height_cm=175.0, weight_kg=71.0
            ),
            history_window_warning=None,
        )
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise], manifest, {}, output_dir=tmp_path, include_raw=False, include_samples=True, force=False
        )

        with zipfile.ZipFile(result.path) as zip_file:
            manifest_json = json.loads(zip_file.read("manifest.json"))

        assert manifest_json["exercise_count"] == 3
        assert manifest_json["total_duration_seconds"] == 12979.3
        assert manifest_json["total_calories"] == 1911
        assert manifest_json["sports"] == [
            {"sport": "Aerobics", "session_count": 2, "total_duration_seconds": 7757.8, "total_calories": 1125},
            {
                "sport": "Kickboxing Martial Arts",
                "session_count": 1,
                "total_duration_seconds": 5221.5,
                "total_calories": 786,
            },
        ]
        assert manifest_json["profile"] == {
            "birthdate": "1990-03-15",
            "gender": "MALE",
            "height_cm": 175.0,
            "weight_kg": 71.0,
        }

    async def test__readme__mentions_30_day_caveat(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18))
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise], manifest, {}, output_dir=tmp_path, include_raw=False, include_samples=True, force=False
        )

        with zipfile.ZipFile(result.path) as zip_file:
            readme = zip_file.read("README.md").decode("utf-8")

        assert readme.strip()
        assert "30-day" in readme

    async def test__write__archive_mode_is_0600(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18))
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise], manifest, {}, output_dir=tmp_path, include_raw=False, include_samples=True, force=False
        )

        assert (result.path.stat().st_mode & 0o777) == 0o600

    async def test__access_token_never_appears_in_archive(self, tmp_path: Path) -> None:
        access_token = os.environ["POLAR_ACCESS_TOKEN"]
        date_range = DateRange(date_min=date(2026, 8, 18), date_max=date(2026, 8, 18))
        exercise = ExerciseFactory.build(id="54klrKbL", date=date(2026, 8, 18))
        manifest = ExerciseManifestFactory.build(date_range=date_range, exercise_count=1, sports=(), profile=None)
        raw = {"54klrKbL": {"id": "54klrKbL", "start_time": "2026-08-18T11:32:08"}}
        archiver = ZipExerciseArchiver()

        result = await archiver.write(
            [exercise], manifest, raw, output_dir=tmp_path, include_raw=True, include_samples=True, force=False
        )

        with zipfile.ZipFile(result.path) as zip_file:
            for name in zip_file.namelist():
                assert access_token not in zip_file.read(name).decode("utf-8")
