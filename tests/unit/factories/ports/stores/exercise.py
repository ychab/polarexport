from datetime import UTC
from datetime import date
from datetime import datetime

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.application.ports.stores.exercise import StoredExercise


class StoredExerciseFactory(DataclassFactory[StoredExercise]):
    __model__ = StoredExercise

    id = Use(lambda: "54klrKbL")
    date = Use(lambda: date(2026, 8, 18))
    fetched_at = Use(lambda: datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
    api = "polar-accesslink-v3"
    payload = Use(lambda: {"id": "54klrKbL", "start_time": "2026-08-18T11:32:08"})
