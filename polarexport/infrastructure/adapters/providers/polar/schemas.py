from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl


class SleepDTO(BaseModel):
    model_config = ConfigDict(extra="allow")

    polar_user: HttpUrl
    date: date
    sleep_start_time: datetime | None = None
    sleep_end_time: datetime | None = None
    device_id: str | None = None
    continuity: float | None = None
    continuity_class: int | None = None
    light_sleep: int | None = None
    deep_sleep: int | None = None
    rem_sleep: int | None = None
    unrecognized_sleep_stage: int | None = None
    sleep_score: int | None = None
    total_interruption_duration: int | None = None
    sleep_charge: int | None = None
    sleep_goal: int | None = None
    sleep_rating: int | None = None
    short_interruption_duration: int | None = None
    long_interruption_duration: int | None = None
    sleep_cycles: int | None = None
    group_duration_score: float | None = None
    group_solidity_score: float | None = None
    group_regeneration_score: float | None = None
    hypnogram: dict[str, int] | None = None
    heart_rate_samples: dict[str, int] | None = None


class NightlyRechargeDTO(BaseModel):
    model_config = ConfigDict(extra="allow")

    polar_user: HttpUrl
    date: date
    heart_rate_avg: int | None = None
    beat_to_beat_avg: int | None = None
    heart_rate_variability_avg: int | None = None
    breathing_rate_avg: float | None = None
    nightly_recharge_status: int | None = None
    ans_charge: float | None = None
    ans_charge_status: int | None = None
    hrv_samples: dict[str, int] | None = None
    breathing_samples: dict[str, float] | None = None


class ContinuousHeartRateSampleDTO(BaseModel):
    model_config = ConfigDict(extra="allow")

    heart_rate: int
    sample_time: str  # "HH:MM:SS", device time


class ContinuousHeartRateDTO(BaseModel):
    model_config = ConfigDict(extra="allow")

    polar_user: HttpUrl
    date: date
    heart_rate_samples: list[ContinuousHeartRateSampleDTO] = Field(default_factory=list)


class SkinTemperatureDTO(BaseModel):
    """`GET /v3/users/biosensing/skintemperature` — verified against a live capture on 2026-08-18.

    AccessLink returns one nightly aggregate per date; it has no per-sample skin-temperature endpoint
    (the account export's 5-minute series is not reachable via the API).
    """

    model_config = ConfigDict(extra="allow")

    sleep_date: date
    sleep_time_skin_temperature_celsius: float | None = None
    deviation_from_baseline_celsius: float | None = None


class AlertnessHourlyDataDTO(BaseModel):
    model_config = ConfigDict(extra="allow")

    validity: str | None = None
    alertness_level: str | None = None
    start_time: datetime
    end_time: datetime | None = None


class AlertnessDTO(BaseModel):
    """`GET /v3/users/sleepwise/alertness/date` — verified against a live capture on 2026-08-18."""

    model_config = ConfigDict(extra="allow")

    grade: float | None = None
    grade_validity_seconds: int | None = None
    grade_type: str | None = None
    grade_classification: str | None = None
    validity: str | None = None
    sleep_inertia: str | None = None
    sleep_type: str | None = None
    result_type: str | None = None
    period_start_time: datetime | None = None
    period_end_time: datetime | None = None
    sleep_period_start_time: datetime | None = None
    sleep_period_end_time: datetime | None = None
    sleep_timezone_offset_minutes: int | None = None
    hourly_data: list[AlertnessHourlyDataDTO] = Field(default_factory=list)


class CircadianBedtimeDTO(BaseModel):
    """`GET /v3/users/sleepwise/circadian-bedtime/date` — verified against a live capture on 2026-08-18."""

    model_config = ConfigDict(extra="allow")

    validity: str | None = None
    quality: str | None = None
    result_type: str | None = None
    period_start_time: datetime | None = None
    period_end_time: datetime | None = None
    preferred_sleep_period_start_time: datetime | None = None
    preferred_sleep_period_end_time: datetime | None = None
    sleep_gate_start_time: datetime | None = None
    sleep_gate_end_time: datetime | None = None
    sleep_timezone_offset_minutes: int | None = None
