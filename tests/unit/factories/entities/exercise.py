from datetime import UTC
from datetime import date
from datetime import datetime

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.entities.exercise import Exercise


class ExerciseFactory(DataclassFactory[Exercise]):
    __model__ = Exercise
    __set_as_default_factory_for_type__ = True

    id = Use(lambda: "54klrKbL")
    start_time = Use(lambda: datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC))
    date = Use(lambda: date(2026, 8, 18))
    duration_seconds = Use(lambda: 5221.533)
