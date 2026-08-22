import json
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

from pydantic import ValidationError

import pytest

from polarexport.domain.enums import ContinuityClass
from polarexport.domain.enums import LoadInterpretation
from polarexport.domain.enums import NightlyRechargeStatus
from polarexport.domain.value_objects.alertness_hour import AlertnessHour
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarExerciseMapper
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
        assert sleep.heart_rate_samples is not None
        assert sleep.heart_rate_samples["00:41"] == 66

    def test__to_sleep__missing_optional_fields__none(self, mapper: PolarNightMapper) -> None:
        sleep = mapper.to_sleep({"polar_user": "https://polaraccesslink.com/v3/users/1", "date": "2026-08-15"})

        assert sleep.date == date(2026, 8, 15)
        assert sleep.stages is None
        assert sleep.continuity_class is None
        assert sleep.device_id is None
        assert sleep.hypnogram is None
        assert sleep.heart_rate_samples is None

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
        assert recharge.hrv_samples is not None
        assert recharge.hrv_samples["00:43"] == 49
        assert recharge.breathing_samples is not None
        assert recharge.breathing_samples["00:40"] == 15.1

    def test__to_nightly_recharge__missing_optional_fields__none(self, mapper: PolarNightMapper) -> None:
        recharge = mapper.to_nightly_recharge(
            {"polar_user": "https://polaraccesslink.com/v3/users/1", "date": "2026-08-15"}
        )

        assert recharge.nightly_recharge_status is None
        assert recharge.ans_charge is None
        assert recharge.hrv_samples is None
        assert recharge.breathing_samples is None

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
    # to_skin_temperature
    # -------------------------------------------------------------------------

    def test__to_skin_temperature__from_live_capture(self, mapper: PolarNightMapper) -> None:
        skin_temperature = mapper.to_skin_temperature(_load_list("skin-temperature")[0])

        assert skin_temperature.date == date(2026, 8, 5)
        assert skin_temperature.celsius == 33.828125
        assert skin_temperature.deviation == -0.8576766

    def test__to_skin_temperature__missing_optional_fields__none(self, mapper: PolarNightMapper) -> None:
        skin_temperature = mapper.to_skin_temperature({"sleep_date": "2026-08-15"})

        assert skin_temperature.celsius is None
        assert skin_temperature.deviation is None

    def test__to_skin_temperature__malformed__raises(self, mapper: PolarNightMapper) -> None:
        with pytest.raises(ValidationError):
            mapper.to_skin_temperature({"deviation_from_baseline_celsius": 0.5})  # missing sleep_date

    # -------------------------------------------------------------------------
    # to_sleepwise
    # -------------------------------------------------------------------------

    def test__to_sleepwise__both_sides_present(self, mapper: PolarNightMapper) -> None:
        alertness = _load_list("sleepwise-alertness")[0]
        circadian = _load_list("sleepwise-circadian-bedtime")[0]

        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": alertness, "circadian_bedtime": circadian})

        assert sleepwise.date == date(2026, 8, 15)
        assert sleepwise.alertness_hourly == (
            AlertnessHour(
                start_time=datetime.fromisoformat("2026-08-06T04:16:00"),
                end_time=datetime.fromisoformat("2026-08-06T05:00:00"),
                alertness_level="ALERTNESS_LEVEL_LOW",
                validity="VALIDITY_VALID",
            ),
            AlertnessHour(
                start_time=datetime.fromisoformat("2026-08-06T06:00:00"),
                end_time=datetime.fromisoformat("2026-08-06T07:00:00"),
                alertness_level="ALERTNESS_LEVEL_HIGH",
                validity="VALIDITY_VALID",
            ),
        )
        assert sleepwise.sleep_time == datetime.fromisoformat("2026-08-05T21:53:18.763")
        assert sleepwise.wake_time == datetime.fromisoformat("2026-08-06T04:15:18.763")
        assert sleepwise.bedtime_window_start == datetime.fromisoformat("2026-08-05T21:00:00")
        assert sleepwise.bedtime_window_end == datetime.fromisoformat("2026-08-05T21:30:00")
        assert sleepwise.grade == 7.4
        assert sleepwise.grade_type == "GRADE_TYPE_PRIMARY"
        assert sleepwise.grade_classification == "GRADE_CLASSIFICATION_FAIR"
        assert sleepwise.grade_validity_seconds == 57600
        assert sleepwise.validity == "VALIDITY_VALID"
        assert sleepwise.sleep_inertia == "SLEEP_INERTIA_MILD"
        assert sleepwise.sleep_type == "SLEEP_TYPE_PRIMARY"
        assert sleepwise.result_type == "ALERTNESS_TYPE_HISTORY"
        assert sleepwise.period_start_time == datetime.fromisoformat("2026-08-05T21:53:18")
        assert sleepwise.period_end_time == datetime.fromisoformat("2026-08-06T22:05:37")
        assert sleepwise.sleep_timezone_offset_minutes == 120
        assert sleepwise.circadian_validity == "VALIDITY_VALID"
        assert sleepwise.circadian_quality == "CIRCADIAN_BEDTIME_QUALITY_CLEARLY_RECOGNIZABLE"
        assert sleepwise.preferred_sleep_period_start_time == datetime.fromisoformat("2026-08-05T21:15:00")
        assert sleepwise.preferred_sleep_period_end_time == datetime.fromisoformat("2026-08-06T05:15:00")

    def test__to_sleepwise__alertness_only(self, mapper: PolarNightMapper) -> None:
        alertness = _load_list("sleepwise-alertness")[0]

        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": alertness, "circadian_bedtime": None})

        assert sleepwise.bedtime_window_start is None
        assert sleepwise.bedtime_window_end is None
        assert sleepwise.sleep_time is not None
        assert sleepwise.grade == 7.4
        assert sleepwise.circadian_validity is None
        assert sleepwise.circadian_quality is None
        assert sleepwise.preferred_sleep_period_start_time is None

    def test__to_sleepwise__circadian_only(self, mapper: PolarNightMapper) -> None:
        circadian = _load_list("sleepwise-circadian-bedtime")[0]

        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": None, "circadian_bedtime": circadian})

        assert sleepwise.alertness_hourly == ()
        assert sleepwise.sleep_time is None
        assert sleepwise.bedtime_window_start is not None
        assert sleepwise.grade is None
        assert sleepwise.circadian_validity == "VALIDITY_VALID"
        assert sleepwise.circadian_quality == "CIRCADIAN_BEDTIME_QUALITY_CLEARLY_RECOGNIZABLE"
        assert sleepwise.preferred_sleep_period_start_time == datetime.fromisoformat("2026-08-05T21:15:00")

    def test__to_sleepwise__neither_side__empty(self, mapper: PolarNightMapper) -> None:
        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": None, "circadian_bedtime": None})

        assert sleepwise.alertness_hourly == ()
        assert sleepwise.sleep_time is None
        assert sleepwise.bedtime_window_start is None
        assert sleepwise.grade is None
        assert sleepwise.circadian_validity is None

    def test__to_sleepwise__hourly_entry_without_alertness_level__skipped(self, mapper: PolarNightMapper) -> None:
        alertness = _load_list("sleepwise-alertness")[0]
        alertness["hourly_data"].append({"start_time": "2026-08-06T07:00:00", "alertness_level": None})

        sleepwise = mapper.to_sleepwise({"date": "2026-08-15", "alertness": alertness, "circadian_bedtime": None})

        assert len(sleepwise.alertness_hourly) == 2

    def test__to_sleepwise__malformed__raises(self, mapper: PolarNightMapper) -> None:
        with pytest.raises(ValidationError):
            mapper.to_sleepwise({"date": "2026-08-15", "alertness": {"grade_validity_seconds": "not-a-number"}})


class TestPolarExerciseMapper:
    @pytest.fixture
    def mapper(self) -> PolarExerciseMapper:
        return PolarExerciseMapper()

    # -------------------------------------------------------------------------
    # to_exercises
    # -------------------------------------------------------------------------

    def test__to_exercises__not_available_interpretation__nulls_value_and_interpretation(
        self, mapper: PolarExerciseMapper
    ) -> None:
        payload = {
            "id": "abc123",
            "start_time": "2026-08-18T11:32:08",
            "start_time_utc_offset": 120,
            "training_load_pro": {
                "cardio-load": 10.0,
                "cardio-load-interpretation": "NOT_AVAILABLE",
                "muscle-load": -1.0,
                "muscle-load-interpretation": "NOT_AVAILABLE",
                "perceived-load": 0.0,
                "perceived-load-interpretation": "NOT_AVAILABLE",
            },
        }

        exercises = mapper.to_exercises({"abc123": payload})

        training_load = exercises[0].training_load
        assert training_load is not None
        assert training_load.cardio_load is None
        assert training_load.cardio_load_interpretation is None
        assert training_load.muscle_load is None
        assert training_load.muscle_load_interpretation is None
        assert training_load.perceived_load is None
        assert training_load.perceived_load_interpretation is None

    def test__to_exercises__unrecognized_interpretation__none_and_warns(
        self, mapper: PolarExerciseMapper, caplog: pytest.LogCaptureFixture
    ) -> None:
        payload = {
            "id": "abc123",
            "start_time": "2026-08-18T11:32:08",
            "start_time_utc_offset": 120,
            "training_load_pro": {"cardio-load": 5.0, "cardio-load-interpretation": "SOMETHING_NEW"},
        }

        with caplog.at_level("WARNING"):
            exercises = mapper.to_exercises({"abc123": payload})

        training_load = exercises[0].training_load
        assert training_load is not None
        assert training_load.cardio_load is None
        assert training_load.cardio_load_interpretation is None
        assert "Unknown Polar load interpretation" in caplog.text

    def test__to_exercises__known_interpretation__value_and_interpretation_kept(
        self, mapper: PolarExerciseMapper
    ) -> None:
        payload = {
            "id": "abc123",
            "start_time": "2026-08-18T11:32:08",
            "start_time_utc_offset": 120,
            "training_load_pro": {"cardio-load": 81.1622, "cardio-load-interpretation": "HIGH"},
        }

        exercises = mapper.to_exercises({"abc123": payload})

        training_load = exercises[0].training_load
        assert training_load is not None
        assert training_load.cardio_load == 81.1622
        assert training_load.cardio_load_interpretation is LoadInterpretation.HIGH

    def test__to_exercises__missing_utc_offset__treated_as_utc(
        self, mapper: PolarExerciseMapper, caplog: pytest.LogCaptureFixture
    ) -> None:
        payload = {"id": "abc123", "start_time": "2026-08-18T11:32:08"}

        with caplog.at_level("WARNING"):
            exercises = mapper.to_exercises({"abc123": payload})

        exercise = exercises[0]
        assert exercise.start_time == datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC)
        assert exercise.date == date(2026, 8, 18)
        assert "missing start_time_utc_offset" in caplog.text

    def test__to_exercises__malformed_duration__duration_none_rest_maps(self, mapper: PolarExerciseMapper) -> None:
        payload = {
            "id": "abc123",
            "start_time": "2026-08-18T11:32:08",
            "start_time_utc_offset": 120,
            "duration": "not-a-duration",
            "calories": 500,
        }

        exercises = mapper.to_exercises({"abc123": payload})

        exercise = exercises[0]
        assert exercise.duration_seconds is None
        assert exercise.calories == 500

    def test__to_exercises__unknown_sample_type__ignored(self, mapper: PolarExerciseMapper) -> None:
        payload = {
            "id": "abc123",
            "start_time": "2026-08-18T11:32:08",
            "start_time_utc_offset": 120,
            "samples": [{"sample_type": 999, "recording_rate": 1, "data": "1,2,3"}],
        }

        exercises = mapper.to_exercises({"abc123": payload})

        exercise = exercises[0]
        assert exercise.heart_rate is None
        assert exercise.heart_rate_per_minute is None
        assert exercise.speed is None

    def test__to_exercises__no_samples_key__heart_rate_minimum_none(self, mapper: PolarExerciseMapper) -> None:
        payload = {
            "id": "abc123",
            "start_time": "2026-08-18T11:32:08",
            "start_time_utc_offset": 120,
            "heart_rate": {"average": 100, "maximum": 150},
        }

        exercises = mapper.to_exercises({"abc123": payload})

        heart_rate = exercises[0].heart_rate
        assert heart_rate is not None
        assert heart_rate.average == 100
        assert heart_rate.maximum == 150
        assert heart_rate.minimum is None

    def test__to_exercises__all_zero_speed_samples__speed_none(self, mapper: PolarExerciseMapper) -> None:
        payload = {
            "id": "abc123",
            "start_time": "2026-08-18T11:32:08",
            "start_time_utc_offset": 120,
            "samples": [{"sample_type": 1, "recording_rate": 1, "data": "0,0,0,0"}],
        }

        exercises = mapper.to_exercises({"abc123": payload})

        assert exercises[0].speed is None

    def test__to_exercises__real_speed_samples__speed_populated(self, mapper: PolarExerciseMapper) -> None:
        payload = {
            "id": "abc123",
            "start_time": "2026-08-20T17:18:33",
            "start_time_utc_offset": 120,
            "samples": [{"sample_type": 1, "recording_rate": 1, "data": "0,2.5,5.0,0"}],
        }

        exercises = mapper.to_exercises({"abc123": payload})

        speed = exercises[0].speed
        assert speed is not None
        assert speed.average_kmh == 1.875
        assert speed.maximum_kmh == 5.0
        assert speed.minimum_kmh == 2.5

    def test__to_exercises__speed_samples_with_zeros__minimum_excludes_zeros(
        self, mapper: PolarExerciseMapper
    ) -> None:
        # Regression: the walking session in tests/assets/polar/exercises.json has 305 zero samples
        # out of 4 257 (pauses, traffic lights, GPS dropouts) — a naive min() would report 0.0 km/h.
        payload = {
            "id": "abc123",
            "start_time": "2026-08-20T17:18:33",
            "start_time_utc_offset": 120,
            "samples": [{"sample_type": 1, "recording_rate": 1, "data": "0,0,1.5,3.0,0"}],
        }

        exercises = mapper.to_exercises({"abc123": payload})

        speed = exercises[0].speed
        assert speed is not None
        assert speed.minimum_kmh == 1.5
        assert speed.minimum_kmh > 0

    def test__to_exercises__malformed_payload__skipped(
        self, mapper: PolarExerciseMapper, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING"):
            exercises = mapper.to_exercises({"bad-id": {"id": "bad-id"}})  # missing start_time

        assert exercises == ()
        assert "Failed to map Polar exercise" in caplog.text

    # -------------------------------------------------------------------------
    # to_profile
    # -------------------------------------------------------------------------

    def test__to_profile__malformed__returns_none(
        self, mapper: PolarExerciseMapper, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING"):
            profile = mapper.to_profile({"member-id": "redacted-member"})  # missing polar-user-id

        assert profile is None
        assert "Failed to map Polar user profile" in caplog.text
