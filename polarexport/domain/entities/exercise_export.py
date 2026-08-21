from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path

from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.profile import UserProfile
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange


@dataclass(frozen=True, kw_only=True)
class SportSummary:
    sport: str
    session_count: int
    total_duration_seconds: float
    total_calories: int


@dataclass(frozen=True, kw_only=True)
class ExerciseManifest:
    tool_name: str
    tool_version: str
    generated_at: datetime
    date_range: DateRange
    availability: SourceAvailability
    exercise_count: int
    total_duration_seconds: float
    total_calories: int
    sports: tuple[SportSummary, ...] = field(default_factory=tuple)
    profile: UserProfile | None = None
    history_window_warning: str | None = None


@dataclass(frozen=True, kw_only=True)
class ExerciseExportReport:
    archive_path: Path
    archive_size_bytes: int
    manifest: ExerciseManifest
    exercises: tuple[Exercise, ...] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class ExerciseSyncReport:
    fetched: int
    skipped: int
    requests: int
    availability: SourceAvailability
    profile_fetched: bool
