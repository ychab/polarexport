from collections.abc import Mapping
from dataclasses import dataclass

from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange


@dataclass(frozen=True, kw_only=True)
class SourceSyncStat:
    availability: SourceAvailability
    fetched: int
    skipped: int  # already in the store
    empty: int  # Polar had nothing
    requests: int


@dataclass(frozen=True, kw_only=True)
class SyncReport:
    date_range: DateRange
    stats: Mapping[NightSource, SourceSyncStat]
    history_window_warning: str | None = None
