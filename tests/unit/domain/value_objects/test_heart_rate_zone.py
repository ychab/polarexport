from polarexport.domain.value_objects.heart_rate_zone import HeartRateZone


class TestHeartRateZone:
    def test__fields(self) -> None:
        zone = HeartRateZone(index=1, lower_limit=100, upper_limit=120, seconds=978)
        assert zone.index == 1
        assert zone.lower_limit == 100
        assert zone.upper_limit == 120
        assert zone.seconds == 978

    def test__defaults(self) -> None:
        zone = HeartRateZone(index=0)
        assert zone.lower_limit is None
        assert zone.upper_limit is None
        assert zone.seconds is None
