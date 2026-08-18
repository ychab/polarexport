from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime

from polarexport.domain.types import AlertnessHour


@dataclass(frozen=True, kw_only=True)
class SleepWise:
    date: date
    alertness_hourly: tuple[AlertnessHour, ...] = field(default_factory=tuple)
    sleep_time: datetime | None = None
    wake_time: datetime | None = None
    bedtime_window_start: datetime | None = None
    bedtime_window_end: datetime | None = None
