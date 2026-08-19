from abc import ABC
from abc import abstractmethod
from datetime import datetime
from pathlib import Path

from polarexport.domain.entities.credentials import StoredCredentials


class CredentialsStorePort(ABC):
    """A port for persisting and retrieving Polar OAuth credentials on local storage."""

    @abstractmethod
    async def write(
        self,
        *,
        access_token: str,
        user_id: str,
        obtained_at: datetime,
        expires_in: int,
        path: Path,
        force: bool,
    ) -> None:
        """Write the access token and its provenance into `path`, replacing any prior credentials.

        Args:
            access_token: The bearer token from the OAuth exchange.
            user_id: The Polar user id (`x_user_id`).
            obtained_at: When the token was obtained.
            expires_in: Seconds until the token expires, as reported by Polar.
            path: The credentials file to write into; created if missing.
            force: Overwrite credentials already present at `path`.

        Raises:
            CredentialsAlreadyExistError: `path` already holds credentials and `force` is False.
        """
        ...

    @abstractmethod
    async def read(self, path: Path) -> StoredCredentials | None:
        """Read the credentials stored at `path`.

        Args:
            path: The credentials file to read.

        Returns:
            The stored credentials, or `None` if `path` doesn't exist or can't be parsed.
        """
        ...
