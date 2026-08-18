from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.domain.services.night_merger import merge_nights
from polarexport.domain.value_objects.date_range import DateRange

from tests.unit.factories.entities.heart_rate import ContinuousHeartRateFactory
from tests.unit.factories.entities.recharge import NightlyRechargeFactory
from tests.unit.factories.entities.skin_temperature import SkinTemperatureFactory
from tests.unit.factories.entities.sleep import SleepFactory
from tests.unit.factories.entities.sleepwise import SleepWiseFactory


class TestMergeNights:
    def test__all_sources_present(self) -> None:
        day = date(2026, 7, 20)
        date_range = DateRange(date_min=day, date_max=day)

        sleep = SleepFactory.build(date=day)
        recharge = NightlyRechargeFactory.build(date=day)
        skin_temperature = SkinTemperatureFactory.build(date=day)
        sleepwise = SleepWiseFactory.build(date=day)
        heart_rate = ContinuousHeartRateFactory.build(date=day, samples=())

        nights, gaps = merge_nights(
            date_range,
            sleeps={day: sleep},
            recharges={day: recharge},
            skin_temperatures={day: skin_temperature},
            sleepwises={day: sleepwise},
            heart_rates={day: heart_rate},
        )

        assert gaps == ()
        assert len(nights) == 1
        night = nights[0]
        assert night.sleep is sleep
        assert night.recharge is recharge
        assert night.skin_temperature is skin_temperature
        assert night.sleepwise is sleepwise
        assert night.heart_rate is not None

    def test__missing_dates_become_gaps(self) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 21))

        nights, gaps = merge_nights(
            date_range, sleeps={}, recharges={}, skin_temperatures={}, sleepwises={}, heart_rates={}
        )

        assert nights == ()
        assert gaps == (date(2026, 7, 20), date(2026, 7, 21))

    def test__heart_rate_clipped_to_sleep_window(self) -> None:
        day = date(2026, 7, 20)
        date_range = DateRange(date_min=day, date_max=day)

        sleep = SleepFactory.build(
            date=day,
            sleep_start_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            sleep_end_time=datetime(2026, 7, 21, 6, 0, tzinfo=UTC),
        )
        in_window = (datetime(2026, 7, 21, 1, 0, tzinfo=UTC), 55)
        out_of_window = (datetime(2026, 7, 20, 20, 0, tzinfo=UTC), 80)
        heart_rate = ContinuousHeartRateFactory.build(date=day, samples=(in_window, out_of_window))

        nights, _ = merge_nights(
            date_range,
            sleeps={day: sleep},
            recharges={},
            skin_temperatures={},
            sleepwises={},
            heart_rates={day: heart_rate},
        )

        assert nights[0].heart_rate is not None
        assert nights[0].heart_rate.samples == (in_window,)

    def test__heart_rate_unclipped_without_sleep(self) -> None:
        day = date(2026, 7, 20)
        date_range = DateRange(date_min=day, date_max=day)

        samples = ((datetime(2026, 7, 20, 20, 0, tzinfo=UTC), 80),)
        heart_rate = ContinuousHeartRateFactory.build(date=day, samples=samples)

        nights, _ = merge_nights(
            date_range, sleeps={}, recharges={}, skin_temperatures={}, sleepwises={}, heart_rates={day: heart_rate}
        )

        assert nights[0].heart_rate is heart_rate

    def test__heart_rate_unclipped_when_sleep_has_no_timing(self) -> None:
        day = date(2026, 7, 20)
        date_range = DateRange(date_min=day, date_max=day)

        sleep = SleepFactory.build(date=day, sleep_start_time=None, sleep_end_time=None)
        samples = ((datetime(2026, 7, 20, 20, 0, tzinfo=UTC), 80),)
        heart_rate = ContinuousHeartRateFactory.build(date=day, samples=samples)

        nights, _ = merge_nights(
            date_range,
            sleeps={day: sleep},
            recharges={},
            skin_temperatures={},
            sleepwises={},
            heart_rates={day: heart_rate},
        )

        assert nights[0].heart_rate is heart_rate
