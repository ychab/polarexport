from collections.abc import Mapping
from datetime import date

from polarexport.domain.entities.heart_rate import ContinuousHeartRate
from polarexport.domain.entities.night import Night
from polarexport.domain.entities.recharge import NightlyRecharge
from polarexport.domain.entities.skin_temperature import SkinTemperature
from polarexport.domain.entities.sleep import Sleep
from polarexport.domain.entities.sleepwise import SleepWise
from polarexport.domain.utils.dates import iterate_dates
from polarexport.domain.value_objects.date_range import DateRange


def merge_nights(
    date_range: DateRange,
    sleeps: Mapping[date, Sleep],
    recharges: Mapping[date, NightlyRecharge],
    skin_temperatures: Mapping[date, SkinTemperature],
    sleepwises: Mapping[date, SleepWise],
    heart_rates: Mapping[date, ContinuousHeartRate],
) -> tuple[tuple[Night, ...], tuple[date, ...]]:
    nights: list[Night] = []
    gaps: list[date] = []

    for day in iterate_dates(date_range):
        sleep = sleeps.get(day)
        heart_rate = heart_rates.get(day)
        if sleep is not None and heart_rate is not None:
            heart_rate = _clip_heart_rate_to_sleep_window(sleep, heart_rate)

        night = Night(
            date=day,
            sleep=sleep,
            recharge=recharges.get(day),
            skin_temperature=skin_temperatures.get(day),
            sleepwise=sleepwises.get(day),
            heart_rate=heart_rate,
        )
        if night.has_data:
            nights.append(night)
        else:
            gaps.append(day)

    return tuple(nights), tuple(gaps)


def _clip_heart_rate_to_sleep_window(sleep: Sleep, heart_rate: ContinuousHeartRate) -> ContinuousHeartRate:
    if sleep.sleep_start_time is None or sleep.sleep_end_time is None:
        return heart_rate

    # Polar's continuous-heart-rate samples carry no UTC offset (device-local wall-clock only), unlike
    # sleep_start_time/sleep_end_time — compare wall-clock to wall-clock rather than fabricate an offset.
    start = sleep.sleep_start_time.replace(tzinfo=None)
    end = sleep.sleep_end_time.replace(tzinfo=None)
    clipped_samples = tuple(sample for sample in heart_rate.samples if start <= sample[0].replace(tzinfo=None) <= end)
    return ContinuousHeartRate(date=heart_rate.date, samples=clipped_samples)
