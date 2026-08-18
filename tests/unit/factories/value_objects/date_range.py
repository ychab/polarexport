from datetime import date
from datetime import timedelta

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.value_objects.date_range import DateRange


class DateRangeFactory(DataclassFactory[DateRange]):
    __model__ = DateRange
    __set_as_default_factory_for_type__ = True

    date_min = Use(lambda: date(2026, 7, 20))
    date_max = Use(lambda: date(2026, 7, 20) + timedelta(days=7))
