from polarexport.domain.value_objects.heart_rate_stats import HeartRateStats


class TestHeartRateStats:
    def test__fields(self) -> None:
        stats = HeartRateStats(average=121, maximum=175, minimum=70)
        assert stats.average == 121
        assert stats.maximum == 175
        assert stats.minimum == 70

    def test__defaults(self) -> None:
        stats = HeartRateStats()
        assert stats.average is None
        assert stats.maximum is None
        assert stats.minimum is None
