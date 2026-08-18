from abc import ABC
from abc import abstractmethod

from polarexport.domain.entities.auth import OAuthTokens


class AuthProviderPort(ABC):
    """A port for the Polar OAuth2 flow: authorization URL, token exchange, user registration."""

    @abstractmethod
    def authorization_url(self, *, redirect_uri: str, state: str) -> str:
        """Build the URL the user's browser is sent to for the authorization step.

        Deliberately synchronous — it only assembles a URL, it performs no I/O.

        Args:
            redirect_uri: Where Polar redirects back to after the user consents. Must match the URI
                registered for this client at admin.polaraccesslink.com, character for character.
            state: An opaque, unguessable value echoed back on the callback, used to detect a stray
                request landing on the local callback listener.

        Returns:
            The full authorization URL.
        """
        ...

    @abstractmethod
    async def exchange_code(self, code: str, *, redirect_uri: str) -> OAuthTokens:
        """Exchange a single-use authorization code for an access token.

        Args:
            code: The authorization code from the callback. Expires in 10 minutes and is single-use.
            redirect_uri: Must match the one used to obtain `code`.

        Returns:
            The resulting access token, user id, and expiry.

        Raises:
            httpx.HTTPStatusError: On a non-2xx response — notably 400 with body `{"error":
                "invalid_grant"}` (code expired, already used, or a redirect URI mismatch), or 401
                (wrong client id/secret).
        """
        ...

    @abstractmethod
    async def register_user(self, *, access_token: str, member_id: str) -> bool:
        """Register the authorizing account with this application.

        Required once before any data endpoint will serve this user.

        Args:
            access_token: The token from `exchange_code`.
            member_id: An arbitrary stable identifier for the user within this application.

        Returns:
            True if this call newly registered the account, False if it was already registered
            (Polar returns 409, which is success, not an error).

        Raises:
            httpx.HTTPStatusError: On a non-2xx, non-409 response — notably 403 if a consent is
                missing.
        """
        ...
