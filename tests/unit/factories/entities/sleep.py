from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

from polyfactory import Use
from polyfactory.decorators import post_generated
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.entities.sleep import Sleep


class SleepFactory(DataclassFactory[Sleep]):
    __model__ = Sleep
    __set_as_default_factory_for_type__ = True

    date = Use(lambda: date(2026, 7, 20))
    sleep_start_time = Use(lambda: datetime(2026, 7, 20, 23, 0, tzinfo=UTC))

    @post_generated
    @classmethod
    def sleep_end_time(cls, sleep_start_time: datetime | None) -> datetime | None:
        if sleep_start_time is None:
            return None
        return sleep_start_time + timedelta(hours=7)
