from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, kw_only=True)
class SkinTemperature:
    date: date
    celsius: float | None = None
    deviation: float | None = None
