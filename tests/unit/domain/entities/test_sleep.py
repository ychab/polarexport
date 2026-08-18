from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from polarexport.domain.entities.sleep import Sleep


class TestSleep:
    def test__start_after_end__raises(self) -> None:
        with pytest.raises(ValueError, match="must not be after"):
            Sleep(
                date=date(2026, 7, 20),
                sleep_start_time=datetime(2026, 7, 21, 6, 0, tzinfo=UTC),
                sleep_end_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            )

    def test__start_before_end__valid(self) -> None:
        sleep = Sleep(
            date=date(2026, 7, 20),
            sleep_start_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            sleep_end_time=datetime(2026, 7, 21, 6, 0, tzinfo=UTC),
        )
        assert sleep.sleep_start_time is not None
        assert sleep.sleep_end_time is not None

    def test__no_timing__valid(self) -> None:
        sleep = Sleep(date=date(2026, 7, 20))
        assert sleep.sleep_start_time is None
        assert sleep.sleep_end_time is None
