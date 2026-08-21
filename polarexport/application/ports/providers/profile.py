from abc import ABC
from abc import abstractmethod
from typing import Any


class ProfileProviderPort(ABC):
    """A port for fetching the raw Polar user profile.

    Separate from `ExerciseProviderPort`: a profile is not a training session, and one adapter
    implementing both ports is fine — it is still the transport, not interpretation.
    """

    @abstractmethod
    async def fetch_profile(self) -> dict[str, Any] | None:
        """Fetch the authorizing user's Polar profile.

        Returns the raw payload, not a domain entity — mapping happens at export time, mirroring the
        other providers.

        Returns:
            The raw profile payload, or `None` if Polar reported nothing for this user.
        """
        ...
