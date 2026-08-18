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
