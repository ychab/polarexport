from pathlib import Path

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from polarexport.application.inputs.exercise import ExerciseExportInput
from polarexport.application.inputs.exercise import ExerciseSyncInput

from tests.unit.factories.value_objects.date_range import DateRangeFactory


class ExerciseSyncInputFactory(ModelFactory[ExerciseSyncInput]):
    __model__ = ExerciseSyncInput

    with_samples = True
    with_zones = True
    force_refresh = False


class ExerciseExportInputFactory(ModelFactory[ExerciseExportInput]):
    __model__ = ExerciseExportInput

    date_range = Use(DateRangeFactory.build)
    sports = Use(lambda: frozenset[str]())
    include_raw = True
    include_samples = True
    output_dir = Use(lambda: Path("export"))
    force = False
    limit = None
