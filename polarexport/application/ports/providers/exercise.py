from abc import ABC
from abc import abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from polarexport.domain.enums import SourceAvailability


@dataclass(frozen=True, kw_only=True)
class ExerciseFetchResult:
    payloads: Mapping[str, dict[str, Any]]  # keyed by exercise id
    availability: SourceAvailability
    request_count: int


class ExerciseProviderPort(ABC):
    """A port for fetching raw Polar training-session data."""

    @abstractmethod
    async def fetch_exercises(self, *, with_samples: bool, with_zones: bool) -> ExerciseFetchResult:
        """Fetch every training session Polar still holds.

        Polar returns whatever is inside its rolling retention window with no way to narrow the
        request; date filtering is the caller's job, applied to the result. Returns raw payloads, not
        entities — the store keeps them verbatim so archives can be rebuilt after a mapper change.

        Args:
            with_samples: Request the per-second sample series (`?samples=true`).
            with_zones: Request the heart-rate zone breakdown (`?zones=true`).

        Returns:
            The raw payloads keyed by exercise id, the availability observed, and the request count.

        Raises:
            ProviderRateLimitError: Rate limits were still exceeded after retries.
        """
        ...
