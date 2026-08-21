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


class HeartRateDTO(BaseModel):
    """`heart_rate` on an exercise. There is no `minimum` — Polar's swagger doesn't document one and
    the live capture never returns it; the domain derives it from the sample series instead."""

    model_config = ConfigDict(extra="allow")

    average: int | None = None
    maximum: int | None = None


class HeartRateZoneDTO(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int
    lower_limit: int | None = None
    upper_limit: int | None = None
    in_zone: str | None = None  # ISO-8601 duration, e.g. "PT15M41S"


class ExerciseSampleDTO(BaseModel):
    """One entry of the `samples` array on `GET /v3/exercises?samples=true`.

    `sample_type` was captured live on 2026-08-20 as a JSON **integer** (`0`), not the string the
    plan's provisional design expected — Pydantic coerces either shape, so the field stays `int` and
    reality wins per the project's own rule for swagger/reality mismatches.
    """

    model_config = ConfigDict(extra="allow")

    recording_rate: int | None = None
    sample_type: int
    data: str


class TrainingLoadProDTO(BaseModel):
    """`training_load_pro` on an exercise. Every field but `user_rpe` mixes in hyphenated keys."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    cardio_load: float | None = Field(default=None, alias="cardio-load")
    cardio_load_interpretation: str | None = Field(default=None, alias="cardio-load-interpretation")
    muscle_load: float | None = Field(default=None, alias="muscle-load")
    muscle_load_interpretation: str | None = Field(default=None, alias="muscle-load-interpretation")
    perceived_load: float | None = Field(default=None, alias="perceived-load")
    perceived_load_interpretation: str | None = Field(default=None, alias="perceived-load-interpretation")
    user_rpe: str | None = Field(default=None, alias="user-rpe")


class ExerciseDTO(BaseModel):
    """`GET /v3/exercises` — verified against a live capture on 2026-08-20.

    Polar mixes naming conventions inside a single response: sample-series and everything else on the
    exercise use underscores (`start_time`, `detailed_sport_info`), training-load and running-index use
    hyphens (`cardio-load`, `running-index`).
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    upload_time: datetime | None = None
    polar_user: HttpUrl | None = None
    device: str | None = None
    device_id: str | None = None
    start_time: datetime  # naive local wall-clock time — see start_time_utc_offset
    start_time_utc_offset: int | None = None  # minutes
    duration: str | None = None  # ISO-8601, e.g. "PT5221.533S"
    sport: str | None = None
    detailed_sport_info: str | None = None
    has_route: bool | None = None
    calories: int | None = None
    distance: float | None = None  # metres
    fat_percentage: int | None = None
    carbohydrate_percentage: int | None = None
    protein_percentage: int | None = None
    heart_rate: HeartRateDTO | None = None
    heart_rate_zones: list[HeartRateZoneDTO] | None = None  # only present when `?zones=true`
    samples: list[ExerciseSampleDTO] | None = None  # only present when `?samples=true`
    training_load_pro: TrainingLoadProDTO | None = None
    running_index: int | None = Field(default=None, alias="running-index")


class UserProfileDTO(BaseModel):
    """`GET /v3/users/{user_id}` — verified against a live capture on 2026-08-20."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    polar_user_id: int = Field(alias="polar-user-id")
    member_id: str | None = Field(default=None, alias="member-id")
    first_name: str | None = Field(default=None, alias="first-name")
    last_name: str | None = Field(default=None, alias="last-name")
    birthdate: date | None = None
    gender: str | None = None
    height: float | None = None  # cm
    weight: float | None = None  # kg
