from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.domain.entities.sleepwise import SleepWise
from polarexport.domain.value_objects.alertness_hour import AlertnessHour


class TestSleepWise:
    def test__fields(self) -> None:
        hour = AlertnessHour(
            start_time=datetime(2026, 7, 21, 4, 0, tzinfo=UTC),
            end_time=datetime(2026, 7, 21, 5, 0, tzinfo=UTC),
            alertness_level="ALERTNESS_LEVEL_HIGH",
            validity="VALIDITY_VALID",
        )
        sleepwise = SleepWise(
            date=date(2026, 7, 20),
            alertness_hourly=(hour,),
            sleep_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            wake_time=datetime(2026, 7, 21, 6, 0, tzinfo=UTC),
            bedtime_window_start=datetime(2026, 7, 20, 22, 30, tzinfo=UTC),
            bedtime_window_end=datetime(2026, 7, 20, 23, 30, tzinfo=UTC),
            grade=7.4,
            grade_type="GRADE_TYPE_PRIMARY",
            grade_classification="GRADE_CLASSIFICATION_FAIR",
            grade_validity_seconds=57600,
            validity="VALIDITY_VALID",
            sleep_inertia="SLEEP_INERTIA_MILD",
            sleep_type="SLEEP_TYPE_PRIMARY",
            result_type="ALERTNESS_TYPE_HISTORY",
            period_start_time=datetime(2026, 7, 20, 21, 53, tzinfo=UTC),
            period_end_time=datetime(2026, 7, 21, 22, 5, tzinfo=UTC),
            sleep_timezone_offset_minutes=120,
            circadian_validity="VALIDITY_VALID",
            circadian_quality="CIRCADIAN_BEDTIME_QUALITY_CLEARLY_RECOGNIZABLE",
            preferred_sleep_period_start_time=datetime(2026, 7, 20, 21, 15, tzinfo=UTC),
            preferred_sleep_period_end_time=datetime(2026, 7, 21, 5, 15, tzinfo=UTC),
        )
        assert sleepwise.alertness_hourly == (hour,)
        assert sleepwise.sleep_time is not None
        assert sleepwise.grade == 7.4
        assert sleepwise.circadian_quality == "CIRCADIAN_BEDTIME_QUALITY_CLEARLY_RECOGNIZABLE"

    def test__defaults(self) -> None:
        sleepwise = SleepWise(date=date(2026, 7, 20))
        assert sleepwise.alertness_hourly == ()
        assert sleepwise.sleep_time is None
        assert sleepwise.grade is None
        assert sleepwise.circadian_validity is None
