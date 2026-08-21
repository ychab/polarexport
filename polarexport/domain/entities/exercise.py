from dataclasses import dataclass
from datetime import date
from datetime import datetime

from polarexport.domain.value_objects.heart_rate_stats import HeartRateStats
from polarexport.domain.value_objects.heart_rate_zone import HeartRateZone
from polarexport.domain.value_objects.speed_stats import SpeedStats
from polarexport.domain.value_objects.training_load import TrainingLoad


@dataclass(frozen=True, kw_only=True)
class Exercise:
    id: str
    start_time: datetime
    date: date
    upload_time: datetime | None = None
    duration_seconds: float | None = None
    sport: str | None = None
    detailed_sport_info: str | None = None
    device: str | None = None
    device_id: str | None = None
    calories: int | None = None
    distance_meters: float | None = None
    heart_rate: HeartRateStats | None = None
    heart_rate_zones: tuple[HeartRateZone, ...] | None = None
    heart_rate_per_minute: tuple[int | None, ...] | None = None
    speed: SpeedStats | None = None
    training_load: TrainingLoad | None = None
    running_index: int | None = None
    fat_percentage: int | None = None
    carbohydrate_percentage: int | None = None
    protein_percentage: int | None = None
    has_route: bool | None = None

    def __post_init__(self) -> None:
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError(f"duration_seconds must be >= 0, got {self.duration_seconds}")

    @property
    def sport_label(self) -> str | None:
        """Human-readable sport name: "Kickboxing Martial Arts" from KICKBOXING_MARTIAL_ARTS.

        Prefers `detailed_sport_info` — `sport` is frequently the useless "OTHER", as it was on all
        three sessions in the phase-21 capture, including the kickboxing one.
        """
        label = self.detailed_sport_info or self.sport
        if label is None:
            return None
        return label.replace("_", " ").title()

    @property
    def distance_km(self) -> float | None:
        if self.distance_meters is None:
            return None
        return self.distance_meters / 1000

    @property
    def average_speed_kmh(self) -> float | None:
        """Derived from distance and duration, not from the speed sample series.

        Both inputs have units confirmed by Polar's swagger (metres, ISO-8601 duration), so this figure
        is trustworthy today. The sample-derived figures in `speed` are not — see phase 23.
        """
        if self.distance_meters is None or not self.duration_seconds:
            return None
        return (self.distance_meters / 1000) / (self.duration_seconds / 3600)

    @property
    def calories_per_hour(self) -> float | None:
        if self.calories is None or not self.duration_seconds:
            return None
        return self.calories / (self.duration_seconds / 3600)
