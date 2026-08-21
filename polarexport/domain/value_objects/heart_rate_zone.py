from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class HeartRateZone:
    index: int
    lower_limit: int | None = None
    upper_limit: int | None = None
    seconds: int | None = None  # parsed from `in_zone`
