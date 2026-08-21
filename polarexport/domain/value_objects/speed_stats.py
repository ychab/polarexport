from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class SpeedStats:
    average_kmh: float | None = None
    maximum_kmh: float | None = None
    minimum_kmh: float | None = None
