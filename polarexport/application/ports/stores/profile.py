from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, kw_only=True)
class StoredProfile:
    fetched_at: datetime
    api: str
    payload: dict[str, Any]


class ProfileStorePort(ABC):
    """A port for persisting and retrieving the raw Polar user profile on local storage.

    The profile must be stored, not fetched at export time: `--no-refresh` has to build a complete
    archive offline, and that includes the manifest's profile block.
    """

    @abstractmethod
    async def write(self, stored: StoredProfile) -> None:
        """Persist the fetched profile payload, replacing any prior one.

        Args:
            stored: The payload to persist, including its provenance envelope.
        """
        ...

    @abstractmethod
    async def read(self) -> StoredProfile | None:
        """Read the stored profile payload.

        Returns:
            The stored profile, or `None` if it has never been fetched.
        """
        ...
