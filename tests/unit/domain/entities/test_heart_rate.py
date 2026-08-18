from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.domain.entities.heart_rate import ContinuousHeartRate


class TestContinuousHeartRate:
    def test__fields(self) -> None:
        sample = (datetime(2026, 7, 21, 2, 0, tzinfo=UTC), 55)
        heart_rate = ContinuousHeartRate(date=date(2026, 7, 20), samples=(sample,))
        assert heart_rate.samples == (sample,)

    def test__defaults(self) -> None:
        heart_rate = ContinuousHeartRate(date=date(2026, 7, 20))
        assert heart_rate.samples == ()
