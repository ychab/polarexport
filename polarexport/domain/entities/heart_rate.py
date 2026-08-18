from dataclasses import dataclass
from dataclasses import field
from datetime import date

from polarexport.domain.types import HeartRateSample


@dataclass(frozen=True, kw_only=True)
class ContinuousHeartRate:
    date: date
    samples: tuple[HeartRateSample, ...] = field(default_factory=tuple)
