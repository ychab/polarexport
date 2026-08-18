import base64
import logging
from typing import cast
from urllib.parse import urlencode

import httpx
from httpx import codes

from pydantic import HttpUrl

from tenacity import RetryCallState
from tenacity import retry
from tenacity import retry_if_exception
from tenacity import wait_exponential

from polarexport.application.ports.providers.auth import AuthProviderPort
from polarexport.domain.entities.auth import OAuthTokens
from polarexport.infrastructure.adapters.http import HttpClientMixin

logger = logging.getLogger(__name__)

_SCOPE = "accesslink.read_all"


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):  # Retry 429 and 5xx only
        return exception.response.status_code == codes.TOO_MANY_REQUESTS or exception.response.status_code >= 500

    if isinstance(exception, httpx.RequestError):  # Retry network errors
        return True

    return False


def _stop_after_max_retries(retry_state: RetryCallState) -> bool:
    # See PolarAccessLinkClient._stop_after_max_retries: reading from the instance here keeps the
    # limit overridable per client instead of freezing it at import time.
    client = cast("PolarOAuthClient", retry_state.args[0])
    return retry_state.attempt_number >= client._max_retries


class PolarOAuthClient(HttpClientMixin, AuthProviderPort):
    """Adapter for the Polar OAuth2 flow: authorization URL, token exchange, user registration.

    The token exchange (`polarremote.com`) and user registration (`www.polaraccesslink.com`) live on
    different hosts, so full URLs are used for each request rather than the mixin's single `base_url`.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        authorization_url: HttpUrl,
        token_url: HttpUrl,
        registration_base_url: HttpUrl,
        timeout: float = 30.0,
        max_retries: int = 5,
        verify_ssl: bool = True,
    ) -> None:
        super().__init__(base_url=registration_base_url, timeout=timeout, verify_ssl=verify_ssl)
        self._client_id = client_id
        self._client_secret = client_secret
        self._authorization_url = authorization_url
        self._token_url = token_url
        self._max_retries = max_retries

    def authorization_url(self, *, redirect_uri: str, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": _SCOPE,
            "state": state,
        }
        return f"{self._authorization_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, *, redirect_uri: str) -> OAuthTokens:
        response = await self._post(
            str(self._token_url),
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json;charset=UTF-8",
            },
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        )
        payload = response.json()
        return OAuthTokens(
            access_token=payload["access_token"], user_id=str(payload["x_user_id"]), expires_in=payload["expires_in"]
        )

    async def register_user(self, *, access_token: str, member_id: str) -> bool:
        try:
            await self._post(
                f"{str(self._base_url).rstrip('/')}/v3/users",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json_data={"member-id": member_id},
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == codes.CONFLICT:
                return False
            raise
        return True

    def _basic_auth_header(self) -> str:
        credentials = f"{self._client_id}:{self._client_secret}".encode()
        return f"Basic {base64.b64encode(credentials).decode()}"

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=_stop_after_max_retries,
        reraise=True,
    )
    async def _post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        data: dict[str, str] | None = None,
        json_data: dict[str, str] | None = None,
    ) -> httpx.Response:
        response = await self._client.post(url=url, headers=headers, data=data, json=json_data)
        response.raise_for_status()
        return response
