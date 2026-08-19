from datetime import date

import pytest

from polarexport.domain.exceptions import InvalidDateRangeError
from polarexport.domain.value_objects.date_range import DateRange


class TestDateRange:
    def test__date_min_after_date_max__raises(self) -> None:
        with pytest.raises(InvalidDateRangeError):
            DateRange(date_min=date(2026, 7, 21), date_max=date(2026, 7, 20))

    def test__date_min_equal_date_max__valid(self) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 20))
        assert date_range.days == 1

    def test__days__inclusive_count(self) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 27))
        assert date_range.days == 8

    def test__str__renders_both_dates_iso(self) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 27))
        assert str(date_range) == "2026-07-20 to 2026-07-27"

    def test__repr__still_carries_field_names(self) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 27))
        assert "date_min=" in repr(date_range)
        assert "date_max=" in repr(date_range)
