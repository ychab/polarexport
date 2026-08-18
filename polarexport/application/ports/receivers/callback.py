from abc import ABC
from abc import abstractmethod


class AuthCallbackReceiverPort(ABC):
    """A port for catching the OAuth redirect that carries the authorization code."""

    @abstractmethod
    async def wait_for_code(self, *, expected_state: str, timeout: float) -> str:
        """Wait for the OAuth callback and return its authorization code.

        Args:
            expected_state: The `state` value sent in the authorization request. The callback's
                `state` must match it exactly before its code is trusted.
            timeout: How long to wait, in seconds, before giving up.

        Returns:
            The authorization code from the callback.

        Raises:
            AuthorizationTimeoutError: No callback arrived within `timeout`.
            AuthorizationStateMismatchError: The callback's `state` did not match `expected_state`.
            AuthorizationDeniedError: The user declined consent (`?error=access_denied`).
        """
        ...
