from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime

from polarexport.domain.value_objects.alertness_hour import AlertnessHour


@dataclass(frozen=True, kw_only=True)
class SleepWise:
    date: date
    alertness_hourly: tuple[AlertnessHour, ...] = field(default_factory=tuple)
    sleep_time: datetime | None = None
    wake_time: datetime | None = None
    bedtime_window_start: datetime | None = None
    bedtime_window_end: datetime | None = None
    grade: float | None = None
    grade_type: str | None = None
    grade_classification: str | None = None
    grade_validity_seconds: int | None = None
    validity: str | None = None
    sleep_inertia: str | None = None
    sleep_type: str | None = None
    result_type: str | None = None
    period_start_time: datetime | None = None
    period_end_time: datetime | None = None
    sleep_timezone_offset_minutes: int | None = None
    circadian_validity: str | None = None
    circadian_quality: str | None = None
    preferred_sleep_period_start_time: datetime | None = None
    preferred_sleep_period_end_time: datetime | None = None
