from datetime import date
from datetime import timedelta

from polarexport.domain.const import POLAR_HISTORY_WINDOW_DAYS
from polarexport.domain.utils.dates import history_window_start
from polarexport.domain.utils.dates import is_outside_history_window
from polarexport.domain.utils.dates import iterate_dates
from polarexport.domain.value_objects.date_range import DateRange


class TestIterateDates:
    def test__inclusive_range(self) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 22))
        assert list(iterate_dates(date_range)) == [date(2026, 7, 20), date(2026, 7, 21), date(2026, 7, 22)]

    def test__single_day(self) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 20))
        assert list(iterate_dates(date_range)) == [date(2026, 7, 20)]


class TestHistoryWindowStart:
    def test__window_length(self) -> None:
        today = date(2026, 8, 17)
        assert history_window_start(today) == today - timedelta(days=POLAR_HISTORY_WINDOW_DAYS - 1)


class TestIsOutsideHistoryWindow:
    def test__inside_window(self) -> None:
        today = date(2026, 8, 17)
        assert is_outside_history_window(date(2026, 8, 1), today=today) is False

    def test__on_boundary(self) -> None:
        today = date(2026, 8, 17)
        assert is_outside_history_window(history_window_start(today), today=today) is False

    def test__outside_window(self) -> None:
        today = date(2026, 8, 17)
        assert is_outside_history_window(history_window_start(today) - timedelta(days=1), today=today) is True
