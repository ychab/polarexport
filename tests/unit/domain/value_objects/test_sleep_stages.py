import pytest

from polarexport.domain.value_objects.sleep_stages import SleepStages


class TestSleepStages:
    @pytest.mark.parametrize("field_name", ["light_seconds", "deep_seconds", "rem_seconds", "unrecognized_seconds"])
    def test__negative_seconds__raises(self, field_name: str) -> None:
        kwargs = {"light_seconds": 0, "deep_seconds": 0, "rem_seconds": 0, "unrecognized_seconds": 0}
        kwargs[field_name] = -1
        with pytest.raises(ValueError, match=f"{field_name} must be >= 0"):
            SleepStages(**kwargs)

    def test__total_seconds(self) -> None:
        stages = SleepStages(light_seconds=100, deep_seconds=200, rem_seconds=50, unrecognized_seconds=10)
        assert stages.total_seconds == 360

    def test__total_hours(self) -> None:
        stages = SleepStages(light_seconds=3600, deep_seconds=0, rem_seconds=0, unrecognized_seconds=0)
        assert stages.total_hours == 1.0

    def test__ratios__zero_total(self) -> None:
        stages = SleepStages(light_seconds=0, deep_seconds=0, rem_seconds=0, unrecognized_seconds=0)
        assert stages.light_ratio == 0.0
        assert stages.deep_ratio == 0.0
        assert stages.rem_ratio == 0.0

    def test__ratios__nonzero_total(self) -> None:
        stages = SleepStages(light_seconds=100, deep_seconds=200, rem_seconds=100, unrecognized_seconds=0)
        assert stages.light_ratio == pytest.approx(0.25)
        assert stages.deep_ratio == pytest.approx(0.5)
        assert stages.rem_ratio == pytest.approx(0.25)
