from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

import pytest

from polarexport.domain.entities.sleep import Sleep
from polarexport.domain.value_objects.sleep_stages import SleepStages


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


class TestSleepEfficiencyPercent:
    def test__audited_night__reproduces_polars_value_to_four_decimals(self) -> None:
        sleep_start_time = datetime(2026, 7, 20, 23, 0, tzinfo=UTC)
        sleep = Sleep(
            date=date(2026, 7, 20),
            sleep_start_time=sleep_start_time,
            sleep_end_time=sleep_start_time + timedelta(seconds=29370),
            stages=SleepStages(light_seconds=15000, deep_seconds=6000, rem_seconds=6330, unrecognized_seconds=2040),
        )

        assert sleep.efficiency_percent is not None
        assert round(sleep.efficiency_percent, 4) == 93.0541

    def test__no_stages__returns_none(self) -> None:
        sleep = Sleep(
            date=date(2026, 7, 20),
            sleep_start_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            sleep_end_time=datetime(2026, 7, 21, 6, 0, tzinfo=UTC),
            stages=None,
        )

        assert sleep.efficiency_percent is None

    def test__no_sleep_start_time__returns_none(self) -> None:
        sleep = Sleep(
            date=date(2026, 7, 20),
            sleep_start_time=None,
            sleep_end_time=datetime(2026, 7, 21, 6, 0, tzinfo=UTC),
            stages=SleepStages(light_seconds=100, deep_seconds=100, rem_seconds=100, unrecognized_seconds=0),
        )

        assert sleep.efficiency_percent is None

    def test__no_sleep_end_time__returns_none(self) -> None:
        sleep = Sleep(
            date=date(2026, 7, 20),
            sleep_start_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            sleep_end_time=None,
            stages=SleepStages(light_seconds=100, deep_seconds=100, rem_seconds=100, unrecognized_seconds=0),
        )

        assert sleep.efficiency_percent is None

    def test__start_equals_end__returns_none(self) -> None:
        moment = datetime(2026, 7, 20, 23, 0, tzinfo=UTC)
        sleep = Sleep(
            date=date(2026, 7, 20),
            sleep_start_time=moment,
            sleep_end_time=moment,
            stages=SleepStages(light_seconds=100, deep_seconds=100, rem_seconds=100, unrecognized_seconds=0),
        )

        assert sleep.efficiency_percent is None

    def test__unrecognized_seconds__excluded_from_asleep(self) -> None:
        sleep_start_time = datetime(2026, 7, 20, 23, 0, tzinfo=UTC)
        sleep = Sleep(
            date=date(2026, 7, 20),
            sleep_start_time=sleep_start_time,
            sleep_end_time=sleep_start_time + timedelta(seconds=1000),
            stages=SleepStages(light_seconds=500, deep_seconds=0, rem_seconds=0, unrecognized_seconds=500),
        )

        assert sleep.efficiency_percent == 50.0
