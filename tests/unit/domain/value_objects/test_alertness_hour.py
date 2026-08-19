from datetime import UTC
from datetime import datetime

from polarexport.domain.value_objects.alertness_hour import AlertnessHour


class TestAlertnessHour:
    def test__fields(self) -> None:
        hour = AlertnessHour(
            start_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            end_time=datetime(2026, 7, 21, 0, 0, tzinfo=UTC),
            alertness_level="ALERTNESS_LEVEL_HIGH",
            validity="VALIDITY_VALID",
        )
        assert hour.alertness_level == "ALERTNESS_LEVEL_HIGH"
        assert hour.validity == "VALIDITY_VALID"

    def test__defaults(self) -> None:
        hour = AlertnessHour(start_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC))
        assert hour.end_time is None
        assert hour.alertness_level is None
        assert hour.validity is None
