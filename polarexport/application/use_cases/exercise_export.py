import logging
from collections.abc import Sequence
from datetime import date
from datetime import datetime

from polarexport import __project_name__
from polarexport import __version__
from polarexport.application.inputs.exercise import ExerciseExportInput
from polarexport.application.ports.archivers.exercise import ExerciseArchiverPort
from polarexport.application.ports.mappers.exercise import ExerciseMapperPort
from polarexport.application.ports.stores.exercise import ExerciseStorePort
from polarexport.application.ports.stores.profile import ProfileStorePort
from polarexport.domain.const import POLAR_EXERCISE_WINDOW_DAYS
from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.exercise_export import ExerciseExportReport
from polarexport.domain.entities.exercise_export import ExerciseManifest
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.exceptions import NoExerciseDataError
from polarexport.domain.services.exercise_summary import summarize_by_sport
from polarexport.domain.utils.dates import is_outside_history_window

logger = logging.getLogger(__name__)


class ExerciseExportUseCase:
    def __init__(
        self,
        exercise_store: ExerciseStorePort,
        profile_store: ProfileStorePort,
        exercise_mapper: ExerciseMapperPort,
        exercise_archiver: ExerciseArchiverPort,
    ) -> None:
        self._exercise_store = exercise_store
        self._profile_store = profile_store
        self._exercise_mapper = exercise_mapper
        self._exercise_archiver = exercise_archiver

    async def export(
        self, export_in: ExerciseExportInput, *, today: date, generated_at: datetime
    ) -> ExerciseExportReport:
        stored = await self._exercise_store.read(export_in.date_range)
        payloads = {exercise_id: stored_exercise.payload for exercise_id, stored_exercise in stored.items()}
        exercises = self._exercise_mapper.to_exercises(payloads)

        sports_filtered = self._filter_by_sports(exercises, export_in.sports) if export_in.sports else exercises
        if not sports_filtered:
            raise NoExerciseDataError(self._no_data_message(export_in))

        ordered = tuple(sorted(sports_filtered, key=lambda exercise: exercise.start_time))
        if export_in.limit is not None and len(ordered) > export_in.limit:
            ordered = ordered[-export_in.limit :]

        history_window_warning: str | None = None
        if is_outside_history_window(
            export_in.date_range.date_min, today=today, window_days=POLAR_EXERCISE_WINDOW_DAYS
        ):
            history_window_warning = (
                f"date_min ({export_in.date_range.date_min}) is outside the {POLAR_EXERCISE_WINDOW_DAYS}-day "
                "Polar retention window; the export reflects only what the local store holds"
            )
            logger.warning(history_window_warning, extra={"date_min": str(export_in.date_range.date_min)})

        stored_availability = await self._exercise_store.read_availability()
        availability = stored_availability if stored_availability is not None else SourceAvailability.AVAILABLE

        stored_profile = await self._profile_store.read()
        profile = self._exercise_mapper.to_profile(stored_profile.payload) if stored_profile is not None else None

        sports_summary = summarize_by_sport(ordered)
        manifest = ExerciseManifest(
            tool_name=__project_name__,
            tool_version=__version__,
            generated_at=generated_at,
            date_range=export_in.date_range,
            availability=availability,
            exercise_count=len(ordered),
            total_duration_seconds=sum(summary.total_duration_seconds for summary in sports_summary),
            total_calories=sum(summary.total_calories for summary in sports_summary),
            sports=sports_summary,
            profile=profile,
            history_window_warning=history_window_warning,
        )

        archive_result = await self._exercise_archiver.write(
            ordered,
            manifest,
            payloads,
            output_dir=export_in.output_dir,
            include_raw=export_in.include_raw,
            include_samples=export_in.include_samples,
            force=export_in.force,
        )

        return ExerciseExportReport(
            archive_path=archive_result.path,
            archive_size_bytes=archive_result.size_bytes,
            manifest=manifest,
            exercises=ordered,
        )

    def _filter_by_sports(self, exercises: Sequence[Exercise], sports: frozenset[str]) -> tuple[Exercise, ...]:
        normalized_sports = {sport.upper().replace("-", "_") for sport in sports}
        return tuple(exercise for exercise in exercises if self._matches_sports(exercise, normalized_sports))

    def _matches_sports(self, exercise: Exercise, normalized_sports: set[str]) -> bool:
        if exercise.detailed_sport_info is None:
            return False
        return exercise.detailed_sport_info.upper().replace("-", "_") in normalized_sports

    def _no_data_message(self, export_in: ExerciseExportInput) -> str:
        if not export_in.sports:
            return f"No exercise data found for {export_in.date_range}."
        sports_label = ", ".join(sorted(export_in.sports))
        return f"No exercise data found for {export_in.date_range} matching sport filter: {sports_label}."
