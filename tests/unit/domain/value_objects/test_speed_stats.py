from polarexport.domain.value_objects.speed_stats import SpeedStats


class TestSpeedStats:
    def test__fields(self) -> None:
        speed = SpeedStats(average_kmh=10.0, maximum_kmh=15.5, minimum_kmh=2.0)
        assert speed.average_kmh == 10.0
        assert speed.maximum_kmh == 15.5
        assert speed.minimum_kmh == 2.0

    def test__defaults(self) -> None:
        speed = SpeedStats()
        assert speed.average_kmh is None
        assert speed.maximum_kmh is None
        assert speed.minimum_kmh is None
