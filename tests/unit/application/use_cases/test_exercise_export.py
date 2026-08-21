import logging
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest

from polarexport.application.ports.archivers.exercise import ArchiveResult
from polarexport.application.use_cases.exercise_export import ExerciseExportUseCase
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.exceptions import NoExerciseDataError
from polarexport.domain.value_objects.date_range import DateRange

from tests.unit.factories.entities.exercise import ExerciseFactory
from tests.unit.factories.entities.profile import UserProfileFactory
from tests.unit.factories.inputs.exercise import ExerciseExportInputFactory
from tests.unit.factories.ports.stores.exercise import StoredExerciseFactory
from tests.unit.factories.ports.stores.profile import StoredProfileFactory


class TestExerciseExportUseCase:
    @pytest.fixture
    def today(self) -> date:
        return date(2026, 8, 20)

    @pytest.fixture
    def generated_at(self) -> datetime:
        return datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

    @pytest.fixture
    def date_range(self) -> DateRange:
        return DateRange(date_min=date(2026, 8, 1), date_max=date(2026, 8, 20))

    @pytest.fixture
    def archive_result(self, tmp_path: Path) -> ArchiveResult:
        return ArchiveResult(path=tmp_path / "polarexport-exercises-2026-08-01_2026-08-20.zip", size_bytes=16)

    @pytest.fixture(autouse=True)
    def default_availability(self, mock_exercise_store: mock.AsyncMock) -> None:
        # `None` means "never observed" — most tests care about mapping/filtering, not this branch.
        mock_exercise_store.read_availability.return_value = None

    @pytest.fixture(autouse=True)
    def default_profile(self, mock_profile_store: mock.AsyncMock) -> None:
        mock_profile_store.read.return_value = None

    @pytest.fixture
    def use_case(
        self,
        mock_exercise_store: mock.AsyncMock,
        mock_profile_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
    ) -> ExerciseExportUseCase:
        return ExerciseExportUseCase(
            exercise_store=mock_exercise_store,
            profile_store=mock_profile_store,
            exercise_mapper=mock_exercise_mapper,
            exercise_archiver=mock_exercise_archiver,
        )

    async def test__store_empty__raises_range_only_message(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        tmp_path: Path,
    ) -> None:
        mock_exercise_store.read.return_value = {}
        mock_exercise_mapper.to_exercises.return_value = ()
        export_in = ExerciseExportInputFactory.build(date_range=date_range, output_dir=tmp_path)

        with pytest.raises(NoExerciseDataError) as exc_info:
            await use_case.export(export_in, today=today, generated_at=generated_at)

        assert str(exc_info.value) == f"No exercise data found for {date_range}."

    async def test__sports_filter_excludes_everything__raises_sport_specific_message_that_differs(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        tmp_path: Path,
    ) -> None:
        stored = {"a": StoredExerciseFactory.build(id="a")}
        mock_exercise_store.read.return_value = stored
        mock_exercise_mapper.to_exercises.return_value = (ExerciseFactory.build(detailed_sport_info="AEROBICS"),)
        export_in = ExerciseExportInputFactory.build(
            date_range=date_range, sports=frozenset({"kickboxing-martial-arts"}), output_dir=tmp_path
        )

        with pytest.raises(NoExerciseDataError) as exc_info:
            await use_case.export(export_in, today=today, generated_at=generated_at)

        empty_store_message = f"No exercise data found for {date_range}."
        sport_filtered_message = (
            f"No exercise data found for {date_range} matching sport filter: kickboxing-martial-arts."
        )
        assert str(exc_info.value) != empty_store_message
        assert str(exc_info.value) == sport_filtered_message
        mock_exercise_archiver.write.assert_not_awaited()

    async def test__sports_filter_case_and_separator_insensitive(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        archive_result: ArchiveResult,
        tmp_path: Path,
    ) -> None:
        matching = ExerciseFactory.build(id="a", detailed_sport_info="KICKBOXING_MARTIAL_ARTS")
        unrelated_sport = ExerciseFactory.build(id="b", detailed_sport_info="AEROBICS")
        no_sport_info = ExerciseFactory.build(id="c", detailed_sport_info=None, sport=None)
        mock_exercise_store.read.return_value = {
            exercise.id: StoredExerciseFactory.build(id=exercise.id)
            for exercise in (matching, unrelated_sport, no_sport_info)
        }
        mock_exercise_mapper.to_exercises.return_value = (matching, unrelated_sport, no_sport_info)
        mock_exercise_archiver.write.return_value = archive_result
        export_in = ExerciseExportInputFactory.build(
            date_range=date_range, sports=frozenset({"kickboxing-martial-arts"}), output_dir=tmp_path
        )

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.exercise_count == 1
        assert report.exercises == (matching,)

    async def test__limit_keeps_most_recent_sessions_not_oldest(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        archive_result: ArchiveResult,
        tmp_path: Path,
    ) -> None:
        oldest = ExerciseFactory.build(id="a", start_time=datetime(2026, 8, 1, tzinfo=UTC))
        middle = ExerciseFactory.build(id="b", start_time=datetime(2026, 8, 10, tzinfo=UTC))
        newest = ExerciseFactory.build(id="c", start_time=datetime(2026, 8, 20, tzinfo=UTC))
        mock_exercise_store.read.return_value = {
            exercise.id: StoredExerciseFactory.build(id=exercise.id) for exercise in (newest, oldest, middle)
        }
        mock_exercise_mapper.to_exercises.return_value = (oldest, middle, newest)
        mock_exercise_archiver.write.return_value = archive_result
        export_in = ExerciseExportInputFactory.build(date_range=date_range, output_dir=tmp_path, limit=2)

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.exercises == (middle, newest)

    async def test__include_samples_false__passed_to_archiver_entities_untouched(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        archive_result: ArchiveResult,
        tmp_path: Path,
    ) -> None:
        exercise = ExerciseFactory.build(heart_rate_per_minute=(120, 130, 125))
        mock_exercise_store.read.return_value = {"a": StoredExerciseFactory.build(id="a")}
        mock_exercise_mapper.to_exercises.return_value = (exercise,)
        mock_exercise_archiver.write.return_value = archive_result
        export_in = ExerciseExportInputFactory.build(date_range=date_range, output_dir=tmp_path, include_samples=False)

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert mock_exercise_archiver.write.call_args.kwargs["include_samples"] is False
        assert report.exercises[0].heart_rate_per_minute == (120, 130, 125)

    async def test__date_min_31_days_out__history_window_warning_fires(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        today: date,
        generated_at: datetime,
        archive_result: ArchiveResult,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        date_range = DateRange(date_min=today - timedelta(days=31), date_max=today)
        mock_exercise_store.read.return_value = {"a": StoredExerciseFactory.build(id="a")}
        mock_exercise_mapper.to_exercises.return_value = (ExerciseFactory.build(),)
        mock_exercise_archiver.write.return_value = archive_result
        export_in = ExerciseExportInputFactory.build(date_range=date_range, output_dir=tmp_path)

        with caplog.at_level(logging.WARNING):
            report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.history_window_warning is not None
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    async def test__date_min_29_days_out__no_history_window_warning(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        today: date,
        generated_at: datetime,
        archive_result: ArchiveResult,
        tmp_path: Path,
    ) -> None:
        date_range = DateRange(date_min=today - timedelta(days=29), date_max=today)
        mock_exercise_store.read.return_value = {"a": StoredExerciseFactory.build(id="a")}
        mock_exercise_mapper.to_exercises.return_value = (ExerciseFactory.build(),)
        mock_exercise_archiver.write.return_value = archive_result
        export_in = ExerciseExportInputFactory.build(date_range=date_range, output_dir=tmp_path)

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.history_window_warning is None

    async def test__availability_observed__reported_as_observed(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        archive_result: ArchiveResult,
        tmp_path: Path,
    ) -> None:
        mock_exercise_store.read_availability.return_value = SourceAvailability.UNAVAILABLE
        mock_exercise_store.read.return_value = {"a": StoredExerciseFactory.build(id="a")}
        mock_exercise_mapper.to_exercises.return_value = (ExerciseFactory.build(),)
        mock_exercise_archiver.write.return_value = archive_result
        export_in = ExerciseExportInputFactory.build(date_range=date_range, output_dir=tmp_path)

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.availability == SourceAvailability.UNAVAILABLE

    async def test__availability_never_observed__defaults_to_available(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        archive_result: ArchiveResult,
        tmp_path: Path,
    ) -> None:
        mock_exercise_store.read.return_value = {"a": StoredExerciseFactory.build(id="a")}
        mock_exercise_mapper.to_exercises.return_value = (ExerciseFactory.build(),)
        mock_exercise_archiver.write.return_value = archive_result
        export_in = ExerciseExportInputFactory.build(date_range=date_range, output_dir=tmp_path)

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.availability == SourceAvailability.AVAILABLE

    async def test__profile_stored__mapped_into_manifest(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_profile_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        archive_result: ArchiveResult,
        tmp_path: Path,
    ) -> None:
        stored_profile = StoredProfileFactory.build()
        profile = UserProfileFactory.build()
        mock_profile_store.read.return_value = stored_profile
        mock_exercise_mapper.to_profile.return_value = profile
        mock_exercise_store.read.return_value = {"a": StoredExerciseFactory.build(id="a")}
        mock_exercise_mapper.to_exercises.return_value = (ExerciseFactory.build(),)
        mock_exercise_archiver.write.return_value = archive_result
        export_in = ExerciseExportInputFactory.build(date_range=date_range, output_dir=tmp_path)

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.profile is profile
        mock_exercise_mapper.to_profile.assert_called_once_with(stored_profile.payload)

    async def test__profile_never_synced__manifest_profile_is_none(
        self,
        use_case: ExerciseExportUseCase,
        mock_exercise_store: mock.AsyncMock,
        mock_exercise_mapper: mock.Mock,
        mock_exercise_archiver: mock.AsyncMock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        archive_result: ArchiveResult,
        tmp_path: Path,
    ) -> None:
        mock_exercise_store.read.return_value = {"a": StoredExerciseFactory.build(id="a")}
        mock_exercise_mapper.to_exercises.return_value = (ExerciseFactory.build(),)
        mock_exercise_archiver.write.return_value = archive_result
        export_in = ExerciseExportInputFactory.build(date_range=date_range, output_dir=tmp_path)

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.profile is None
        mock_exercise_mapper.to_profile.assert_not_called()
