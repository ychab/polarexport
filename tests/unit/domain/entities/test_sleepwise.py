from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.domain.entities.sleepwise import SleepWise


class TestSleepWise:
    def test__fields(self) -> None:
        hour = (23, "high")
        sleepwise = SleepWise(
            date=date(2026, 7, 20),
            alertness_hourly=(hour,),
            sleep_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            wake_time=datetime(2026, 7, 21, 6, 0, tzinfo=UTC),
            bedtime_window_start=datetime(2026, 7, 20, 22, 30, tzinfo=UTC),
            bedtime_window_end=datetime(2026, 7, 20, 23, 30, tzinfo=UTC),
        )
        assert sleepwise.alertness_hourly == (hour,)
        assert sleepwise.sleep_time is not None

    def test__defaults(self) -> None:
        sleepwise = SleepWise(date=date(2026, 7, 20))
        assert sleepwise.alertness_hourly == ()
        assert sleepwise.sleep_time is None
