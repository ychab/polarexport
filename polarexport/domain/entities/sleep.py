from dataclasses import dataclass
from datetime import date
from datetime import datetime

from polarexport.domain.enums import ContinuityClass
from polarexport.domain.types import Hypnogram
from polarexport.domain.value_objects.sleep_stages import SleepStages


@dataclass(frozen=True, kw_only=True)
class Sleep:
    date: date
    sleep_start_time: datetime | None = None
    sleep_end_time: datetime | None = None
    stages: SleepStages | None = None
    continuity: float | None = None
    continuity_class: ContinuityClass | None = None
    short_interruption_duration: int | None = None
    long_interruption_duration: int | None = None
    total_interruption_duration: int | None = None
    sleep_score: int | None = None
    sleep_charge: int | None = None
    sleep_goal: int | None = None
    sleep_rating: int | None = None
    sleep_cycles: int | None = None
    group_duration_score: float | None = None
    group_solidity_score: float | None = None
    group_regeneration_score: float | None = None
    hypnogram: Hypnogram | None = None
    device_id: str | None = None

    def __post_init__(self) -> None:
        if (
            self.sleep_start_time is not None
            and self.sleep_end_time is not None
            and self.sleep_start_time > self.sleep_end_time
        ):
            raise ValueError(
                f"sleep_start_time ({self.sleep_start_time}) must not be after sleep_end_time ({self.sleep_end_time})"
            )
