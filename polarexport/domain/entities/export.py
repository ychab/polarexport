from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from pathlib import Path

from polarexport.domain.entities.night import Night
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange


@dataclass(frozen=True, kw_only=True)
class ExportManifest:
    tool_name: str
    tool_version: str
    generated_at: datetime
    date_range: DateRange
    sources_requested: tuple[NightSource, ...]
    source_availability: Mapping[NightSource, SourceAvailability]
    night_count: int
    gaps: tuple[date, ...] = field(default_factory=tuple)
    request_counts: Mapping[NightSource, int]
    history_window_warning: str | None = None


@dataclass(frozen=True, kw_only=True)
class ExportReport:
    archive_path: Path
    archive_size_bytes: int
    manifest: ExportManifest
    nights: tuple[Night, ...] = field(default_factory=tuple)
