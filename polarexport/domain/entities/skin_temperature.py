from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime

from polarexport.domain.types import SkinTemperatureSample


@dataclass(frozen=True, kw_only=True)
class SkinTemperature:
    date: date
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    samples: tuple[SkinTemperatureSample, ...] = field(default_factory=tuple)
    deviation: float | None = None
