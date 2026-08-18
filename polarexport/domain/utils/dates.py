from collections.abc import Iterator
from datetime import date
from datetime import timedelta

from polarexport.domain.const import POLAR_HISTORY_WINDOW_DAYS
from polarexport.domain.value_objects.date_range import DateRange


def iterate_dates(date_range: DateRange) -> Iterator[date]:
    current = date_range.date_min
    while current <= date_range.date_max:
        yield current
        current += timedelta(days=1)


def history_window_start(today: date) -> date:
    return today - timedelta(days=POLAR_HISTORY_WINDOW_DAYS - 1)


def is_outside_history_window(day: date, *, today: date) -> bool:
    return day < history_window_start(today)
