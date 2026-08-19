from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class AlertnessHour:
    start_time: datetime
    end_time: datetime | None = None
    alertness_level: str | None = None
    validity: str | None = None
