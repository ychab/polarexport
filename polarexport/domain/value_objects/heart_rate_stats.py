from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class HeartRateStats:
    average: int | None = None
    maximum: int | None = None
    minimum: int | None = None  # never returned by Polar — derived from the sample series
