from abc import ABC
from abc import abstractmethod
from pathlib import Path


class CredentialsStorePort(ABC):
    """A port for persisting Polar OAuth credentials into a local env file."""

    @abstractmethod
    async def write(self, *, access_token: str, user_id: str, env_path: Path, force: bool) -> None:
        """Write the access token and user id into `env_path`, preserving everything else in it.

        Args:
            access_token: The bearer token from the OAuth exchange.
            user_id: The Polar user id (`x_user_id`).
            env_path: The env file to write into; created if missing.
            force: Overwrite an existing token pair if one is already present.

        Raises:
            CredentialsAlreadyExistError: `env_path` already has an access token and `force` is False.
        """
        ...
