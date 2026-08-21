from polarexport.domain.services.exercise_metrics import downsample_per_minute
from polarexport.domain.services.exercise_metrics import heart_rate_stats
from polarexport.domain.services.exercise_metrics import parse_sample_series


class TestParseSampleSeries:
    def test__numeric_values(self) -> None:
        assert parse_sample_series("70,121,175") == (70.0, 121.0, 175.0)

    def test__null_values__become_none(self) -> None:
        assert parse_sample_series("70,null,175") == (70.0, None, 175.0)

    def test__empty_segments__become_none(self) -> None:
        assert parse_sample_series("70,,175") == (70.0, None, 175.0)

    def test__non_numeric_value__becomes_none(self) -> None:
        assert parse_sample_series("70,garbage,175") == (70.0, None, 175.0)


class TestHeartRateStats:
    def test__minimum_derived_from_samples__api_values_win_for_average_and_maximum(self) -> None:
        samples = (121.0, 175.0, 70.0, 130.0)

        stats = heart_rate_stats(samples, api_average=121, api_maximum=175)

        assert stats.average == 121
        assert stats.maximum == 175
        assert stats.minimum == 70

    def test__dropouts_discarded_from_minimum(self) -> None:
        samples = (0.0, None, 70.0, 130.0)

        stats = heart_rate_stats(samples, api_average=121, api_maximum=175)

        assert stats.minimum == 70

    def test__no_positive_samples__minimum_is_none(self) -> None:
        stats = heart_rate_stats((0.0, None), api_average=None, api_maximum=None)

        assert stats.minimum is None


class TestDownsamplePerMinute:
    def test__one_hertz__two_minutes(self) -> None:
        samples = tuple(float(value % 10) for value in range(120))
        result = downsample_per_minute(samples, recording_rate_seconds=1)
        assert len(result) == 2

    def test__five_second_rate__ten_buckets(self) -> None:
        samples = tuple(float(value % 10) for value in range(120))
        result = downsample_per_minute(samples, recording_rate_seconds=5)
        assert len(result) == 10

    def test__trailing_partial_bucket_kept(self) -> None:
        samples = (10.0, 20.0, 30.0)
        result = downsample_per_minute(samples, recording_rate_seconds=1)
        assert result == (20,)

    def test__all_none_bucket__yields_none(self) -> None:
        samples: tuple[float | None, ...] = (None,) * 60
        result = downsample_per_minute(samples, recording_rate_seconds=1)
        assert result == (None,)

    def test__recording_rate_none__returns_empty(self) -> None:
        assert downsample_per_minute((1.0, 2.0), recording_rate_seconds=None) == ()

    def test__recording_rate_zero__returns_empty(self) -> None:
        assert downsample_per_minute((1.0, 2.0), recording_rate_seconds=0) == ()

    def test__recording_rate_above_sixty__returns_empty(self) -> None:
        assert downsample_per_minute((1.0, 2.0), recording_rate_seconds=90) == ()
