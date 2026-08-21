from abc import ABC
from abc import abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Any

from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange


@dataclass(frozen=True, kw_only=True)
class StoredExercise:
    id: str
    date: date  # local start date, used for the on-disk path and for range reads
    fetched_at: datetime
    api: str
    payload: dict[str, Any]


class ExerciseStorePort(ABC):
    """A port for persisting and retrieving raw Polar exercise payloads on local storage."""

    @abstractmethod
    async def write(self, stored: StoredExercise) -> None:
        """Persist a single fetched exercise payload.

        Args:
            stored: The payload to persist, including its provenance envelope.
        """
        ...

    @abstractmethod
    async def read(self, date_range: DateRange) -> Mapping[str, StoredExercise]:
        """Read the stored exercises whose date falls within a range.

        Args:
            date_range: The date range to read.

        Returns:
            The stored exercises, keyed by exercise id. Ids outside the range are absent.
        """
        ...

    @abstractmethod
    async def known_ids(self) -> frozenset[str]:
        """Return every exercise id already on disk, across all dates.

        There is no date argument: an id is unique across the whole store, and the sync has no date
        context to narrow the check by — `GET /v3/exercises` returns everything Polar still holds in
        one request, so deduplication happens on id after the fetch, not on date before it.

        Returns:
            Every exercise id currently stored.
        """
        ...

    @abstractmethod
    async def write_availability(self, availability: SourceAvailability, *, observed_at: datetime) -> None:
        """Persist the most recently observed availability of the exercises source.

        This is what lets a later export tell "consent missing" (`UNAVAILABLE`) apart from "consent
        fine, nothing recorded" even when the export itself found nothing to map.

        Args:
            availability: The availability actually observed on the last real fetch attempt.
            observed_at: When this availability was observed.
        """
        ...

    @abstractmethod
    async def read_availability(self) -> SourceAvailability | None:
        """Read the most recently observed availability of the exercises source.

        Returns:
            The last observed availability, or `None` if exercises have never been fetched.
        """
        ...
