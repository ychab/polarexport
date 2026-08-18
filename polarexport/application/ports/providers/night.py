from abc import ABC
from abc import abstractmethod
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability


@dataclass(frozen=True, kw_only=True)
class SourceFetchResult:
    payloads: Mapping[date, dict[str, Any] | None]  # None = Polar reported no data for that date
    availability: SourceAvailability
    request_count: int


class NightProviderPort(ABC):
    """A port for fetching raw night data from a Polar data source."""

    @abstractmethod
    async def fetch(self, source: NightSource, dates: Sequence[date]) -> SourceFetchResult:
        """Fetch raw payloads for one source over the given dates.

        Returns raw API payloads, not domain entities — the store keeps them verbatim so that
        archives can be rebuilt after a mapper change. `dict[str, Any]` is the one justified
        `Any` in this codebase: an unmodelled payload is the whole point.

        Args:
            source: The Polar data source to fetch.
            dates: The dates to fetch, already filtered down to what is missing.

        Returns:
            The raw payloads keyed by date, the source's availability, and the request count.

        Raises:
            PolarRateLimitError: Rate limits were still exceeded after retries.
        """
        ...
