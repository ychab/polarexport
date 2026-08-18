from abc import ABC
from abc import abstractmethod
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Any

from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange


@dataclass(frozen=True, kw_only=True)
class StoredPayload:
    source: NightSource
    date: date
    fetched_at: datetime
    api: str  # "polar-accesslink-v3"
    payload: dict[str, Any] | None  # None = Polar had no data for this night


class NightStorePort(ABC):
    """A port for persisting and retrieving raw Polar night payloads on local storage."""

    @abstractmethod
    async def write(self, stored: StoredPayload) -> None:
        """Persist a single fetched payload for a source and date.

        Args:
            stored: The payload to persist, including its provenance envelope.
        """
        ...

    @abstractmethod
    async def read(self, source: NightSource, date_range: DateRange) -> Mapping[date, StoredPayload]:
        """Read the stored payloads for a source over a date range.

        Args:
            source: The Polar data source to read.
            date_range: The date range to read.

        Returns:
            The stored payloads, keyed by date. Dates with nothing on disk are absent.
        """
        ...

    @abstractmethod
    async def missing(self, source: NightSource, dates: Sequence[date], *, today: date) -> tuple[date, ...]:
        """Return the dates that still need fetching.

        A date already stored with a payload is never re-fetched. A date stored as empty is
        re-fetched only while it remains inside the Polar retention window, since a device may
        sync late; once the date falls outside the window the empty verdict is final.

        Args:
            source: The Polar data source to check.
            dates: The candidate dates.
            today: The current date, used to evaluate the retention window.

        Returns:
            The subset of `dates` that still need fetching.
        """
        ...

    @abstractmethod
    async def write_availability(
        self, source: NightSource, availability: SourceAvailability, *, observed_at: datetime
    ) -> None:
        """Persist the most recently observed availability for a source.

        This is provenance about the source as a whole, distinct from the per-date payloads: it is
        what lets an export tell "consent missing" (`UNAVAILABLE`) apart from "consent fine, nothing
        recorded" (`NO_DATA`) even when the export itself found nothing to map.

        Args:
            source: The Polar data source.
            availability: The availability actually observed on the last real fetch attempt.
            observed_at: When this availability was observed.
        """
        ...

    @abstractmethod
    async def read_availability(self, source: NightSource) -> SourceAvailability | None:
        """Read the most recently observed availability for a source.

        Args:
            source: The Polar data source.

        Returns:
            The last observed availability, or `None` if the source has never been fetched.
        """
        ...
