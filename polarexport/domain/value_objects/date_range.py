from dataclasses import dataclass
from datetime import date

from polarexport.domain.exceptions import InvalidDateRangeError


@dataclass(frozen=True, kw_only=True)
class DateRange:
    date_min: date
    date_max: date

    def __post_init__(self) -> None:
        if self.date_min > self.date_max:
            raise InvalidDateRangeError(f"date_min ({self.date_min}) must not be after date_max ({self.date_max})")

    @property
    def days(self) -> int:
        return (self.date_max - self.date_min).days + 1
