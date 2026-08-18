import json
from datetime import date
from datetime import datetime
from typing import Any

from pydantic import ValidationError

import pytest

from polarexport.domain.enums import ContinuityClass
from polarexport.domain.enums import NightlyRechargeStatus
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarNightMapper

from tests import ASSETS_DIR

POLAR_ASSETS_DIR = ASSETS_DIR / "polar"


def _load(name: str) -> dict[str, Any]:
    return json.loads((POLAR_ASSETS_DIR / f"{name}.json").read_text())  # type: ignore[no-any-return]


def _load_list(name: str) -> list[dict[str, Any]]:
    return json.loads((POLAR_ASSETS_DIR / f"{name}.json").read_text())  # type: ignore[no-any-return]


class TestPolarNightMapper:
    @pytest.fixture
    def mapper(self) -> PolarNightMapper:
        return PolarNightMapper()

    # -------------------------------------------------------------------------
    # to_sleep
    # -------------------------------------------------------------------------

    def test__to_sleep__from_live_capture(self, mapper: PolarNightMapper) -> None:
        sleep = mapper.to_sleep(_load("sleep"))

        assert sleep.date == date(2026, 8, 15)
        assert sleep.device_id == "00000000"
        assert sleep.continuity_class is ContinuityClass.FAIRLY_FRAGMENTED
        assert sleep.stages is not None
        assert sleep.stages.light_seconds == 16500
        assert sleep.stages.deep_seconds == 5520
        assert sleep.stages.rem_seconds == 6450
        assert sleep.stages.unrecognized_seconds == 150
        assert sleep.group_duration_score == 100.0
        assert sleep.group_solidity_score == 46.7055
        assert sleep.hypnogram is not None
        assert sleep.hypnogram["00:40"] == 0

    def test__to_sleep__missing_optional_fields__none(self, mapper: PolarNightMapper) -> None:
        sleep = mapper.to_sleep({"polar_user": "https://polaraccesslink.com/v3/users/1", "date": "2026-08-15"})

        assert sleep.date == date(2026, 8, 15)
        assert sleep.stages is None
        assert sleep.continuity_class is None
        assert sleep.device_id is None
        assert sleep.hypnogram is None

    def test__to_sleep__partial_stage_fields__stages_none(self, mapper: PolarNightMapper) -> None:
        sleep = mapper.to_sleep(
            {
                "polar_user": "https://polaraccesslink.com/v3/users/1",
                "date": "2026-08-15",
                "light_sleep": 100,
                # deep_sleep, rem_sleep, unrecognized_sleep_stage all missing
            }
        )

        assert sleep.stages is None

    def test__to_sleep__malformed__raises(self, mapper: PolarNightMapper) -> None:
        with pytest.raises(ValidationError):
            mapper.to_sleep({"polar_user": "https://polaraccesslink.com/v3/users/1"})  # missing date

    # -------------------------------------------------------------------------
    # to_nightly_recharge
    # -------------------------------------------------------------------------

    def test__to_nightly_recharge__from_live_capture(self, mapper: PolarNightMapper) -> None:
        recharge = mapper.to_nightly_recharge(_load("nightly-recharge"))

        assert recharge.date == date(2026, 8, 15)
        assert recharge.nightly_recharge_status is NightlyRechargeStatus.POOR
        assert recharge.ans_charge == -10.0
        assert recharge.ans_charge_status == 1

    def test__to_nightly_recharge__missing_optional_fields__none(self, mapper: PolarNightMapper) -> None:
        recharge = mapper.to_nightly_recharge(
            {"polar_user": "https://polaraccesslink.com/v3/users/1", "date": "2026-08-15"}
        )

        assert recharge.nightly_recharge_status is None
        assert recharge.ans_charge is None

    def test__to_nightly_recharge__malformed__raises(self, mapper: PolarNightMapper) -> None:
        with pytest.raises(ValidationError):
            mapper.to_nightly_recharge({"polar_user": "https://polaraccesslink.com/v3/users/1"})

    # -------------------------------------------------------------------------
    # to_continuous_heart_rate
    # -------------------------------------------------------------------------

    def test__to_continuous_heart_rate__from_live_capture(self, mapper: PolarNightMapper) -> None:
        heart_rate = mapper.to_continuous_heart_rate(_load("continuous-heart-rate"))

        assert heart_rate.date == date(2026, 8, 15)
        assert len(heart_rate.samples) > 0
        first_time, first_bpm = heart_rate.samples[0]
        assert first_time == datetime(2026, 8, 15, 0, 2, 44)
        assert first_bpm == 72

    def test__to_continuous_heart_rate__no_samples__empty(self, mapper: PolarNightMapper) -> None:
        heart_rate = mapper.to_continuous_heart_rate(
            {"polar_user": "https://polaraccesslink.com/v3/users/1", "date": "2026-08-15"}
        )

        assert heart_rate.samples == ()

    def test__to_continuous_heart_rate__malformed__raises(self, mapper: PolarNightMapper) -> None:
        with pytest.raises(ValidationError):
            mapper.to_continuous_heart_rate({"polar_user": "https://polaraccesslink.com/v3/users/1"})

    # -------------------------------------------------------------------------
    # to_skin_temperature (unverified — see schemas.py docstring)
    # -------------------------------------------------------------------------

    def test__to_skin_temperature__from_documented_example(self, mapper: PolarNightMapper) -> None:
        skin_temperature = mapper.to_skin_temperature(_load_list("skin-temperature")[0])

        assert skin_temperature.date == date(2023, 10, 20)
        assert skin_temperature.deviation == 0.5
        assert skin_temperature.samples == ()

    def test__to_skin_temperature__missing_optional_fields__none(self, mapper: PolarNightMapper) -> None:
        skin_temperature = mapper.to_skin_temperature({"sleep_date": "2026-08-15"})

        assert skin_temperature.deviation is None

    def test__to_skin_temperature__malformed__raises(self, mapper: PolarNightMapper) -> None:
        with pytest.raises(ValidationError):
            mapper.to_skin_temperature({"deviation_from_baseline_celsius": 0.5})  # missing sleep_date

    # -------------------------------------------------------------------------
    # to_sleepwise (unverified — see schemas.py docstring)
    # -------------------------------------------------------------------------

    def test__to_sleepwise__both_sides_present(self, mapper: PolarNightMapper) -> None:
        alertness = _load_list("sleepwise-alertness")[0]
        circadian = _load_list("sleepwise-circadian-bedtime")[0]

        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": alertness, "circadian_bedtime": circadian})

        assert sleepwise.date == date(2026, 8, 15)
        assert sleepwise.alertness_hourly == ((4, "ALERTNESS_LEVEL_LOW"),)
        assert sleepwise.sleep_time == datetime.fromisoformat("2022-11-20T20:52:20.57")
        assert sleepwise.wake_time == datetime.fromisoformat("2022-11-21T04:11:20.57")
        assert sleepwise.bedtime_window_start == datetime.fromisoformat("2022-11-20T21:03:30")
        assert sleepwise.bedtime_window_end == datetime.fromisoformat("2022-11-20T21:33:30")

    def test__to_sleepwise__alertness_only(self, mapper: PolarNightMapper) -> None:
        alertness = _load_list("sleepwise-alertness")[0]

        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": alertness, "circadian_bedtime": None})

        assert sleepwise.bedtime_window_start is None
        assert sleepwise.bedtime_window_end is None
        assert sleepwise.sleep_time is not None

    def test__to_sleepwise__circadian_only(self, mapper: PolarNightMapper) -> None:
        circadian = _load_list("sleepwise-circadian-bedtime")[0]

        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": None, "circadian_bedtime": circadian})

        assert sleepwise.alertness_hourly == ()
        assert sleepwise.sleep_time is None
        assert sleepwise.bedtime_window_start is not None

    def test__to_sleepwise__neither_side__empty(self, mapper: PolarNightMapper) -> None:
        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": None, "circadian_bedtime": None})

        assert sleepwise.alertness_hourly == ()
        assert sleepwise.sleep_time is None
        assert sleepwise.bedtime_window_start is None

    def test__to_sleepwise__hourly_entry_without_alertness_level__skipped(self, mapper: PolarNightMapper) -> None:
        alertness = _load_list("sleepwise-alertness")[0]
        alertness["hourly_data"].append({"start_time": "2022-11-21T05:00:00", "alertness_level": None})

        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": alertness, "circadian_bedtime": None})

        assert sleepwise.alertness_hourly == ((4, "ALERTNESS_LEVEL_LOW"),)

    def test__to_sleepwise__malformed__raises(self, mapper: PolarNightMapper) -> None:
        with pytest.raises(ValidationError):
            mapper.to_sleepwise({"date": "2026-08-15", "alertness": {"grade_validity_seconds": "not-a-number"}})
