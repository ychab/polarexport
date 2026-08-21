from datetime import UTC
from datetime import datetime
from pathlib import Path

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.entities.exercise_export import ExerciseExportReport
from polarexport.domain.entities.exercise_export import ExerciseManifest
from polarexport.domain.entities.exercise_export import ExerciseSyncReport
from polarexport.domain.entities.exercise_export import SportSummary
from polarexport.domain.enums import SourceAvailability

from tests.unit.factories.value_objects.date_range import DateRangeFactory


class SportSummaryFactory(DataclassFactory[SportSummary]):
    __model__ = SportSummary
    __set_as_default_factory_for_type__ = True

    sport = Use(lambda: "Kickboxing Martial Arts")


class ExerciseManifestFactory(DataclassFactory[ExerciseManifest]):
    __model__ = ExerciseManifest

    generated_at = Use(lambda: datetime(2026, 8, 18, tzinfo=UTC))
    date_range = Use(DateRangeFactory.build)
    availability = Use(lambda: SourceAvailability.AVAILABLE)
    sports = Use(lambda: ())


class ExerciseExportReportFactory(DataclassFactory[ExerciseExportReport]):
    __model__ = ExerciseExportReport

    archive_path = Use(lambda: Path("data/export/polarexport-exercises-2026-07-20_2026-08-18.zip"))
    archive_size_bytes = Use(DataclassFactory.__faker__.random_int, min=0, max=1_000_000)
    manifest = Use(ExerciseManifestFactory.build)
    # Randomly-generated Exercise entities can violate cross-field invariants (a negative duration)
    # since nested union factories don't inherit those constructors' validation awareness. Nothing
    # here asserts on `exercises`, so default to the same empty tuple as the entity.
    exercises = Use(lambda: ())


class ExerciseSyncReportFactory(DataclassFactory[ExerciseSyncReport]):
    __model__ = ExerciseSyncReport

    availability = Use(lambda: SourceAvailability.AVAILABLE)
