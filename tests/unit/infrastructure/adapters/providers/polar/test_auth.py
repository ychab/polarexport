from collections.abc import Iterable
from unittest import mock

import httpx
from httpx import codes

from pydantic import HttpUrl

import pytest
from pytest_httpx import HTTPXMock
from tenacity import stop_after_attempt

from polarexport.domain.entities.auth import OAuthTokens
from polarexport.infrastructure.adapters.providers.polar.auth import PolarOAuthClient

_TOKEN_URL = "https://polarremote.com/v2/oauth2/token"
_USERS_URL = "https://www.polaraccesslink.com/v3/users"


class TestPolarOAuthClient:
    @pytest.fixture
    def client(self) -> PolarOAuthClient:
        return PolarOAuthClient(
            client_id="dummy-client-id",
            client_secret="dummy-client-secret",
            authorization_url=HttpUrl("https://flow.polar.com/oauth2/authorization"),
            token_url=HttpUrl(_TOKEN_URL),
            registration_base_url=HttpUrl("https://www.polaraccesslink.com"),
        )

    @pytest.fixture
    def mock_tenacity(self) -> Iterable[None]:
        retry_controller = PolarOAuthClient._post.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep
        original_stop = retry_controller.stop

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        retry_controller.stop = stop_after_attempt(5)
        yield
        retry_controller.sleep = original_sleep
        retry_controller.stop = original_stop

    @pytest.fixture
    def mock_tenacity_sleep_only(self) -> Iterable[None]:
        retry_controller = PolarOAuthClient._post.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        yield
        retry_controller.sleep = original_sleep

    def test__authorization_url__builds_expected_query(self, client: PolarOAuthClient) -> None:
        url = client.authorization_url(redirect_uri="http://localhost:8000/callback", state="abc123")

        assert url.startswith("https://flow.polar.com/oauth2/authorization?")
        assert "client_id=dummy-client-id" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback" in url
        assert "scope=accesslink.read_all" in url
        assert "state=abc123" in url
        assert "response_type=code" in url

    async def test__exchange_code__nominal(self, client: PolarOAuthClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=_TOKEN_URL,
            method="POST",
            json={
                "access_token": "tok-must-never-be-logged",
                "token_type": "bearer",
                "expires_in": 473039999,
                "x_user_id": 12345678,
            },
        )

        tokens = await client.exchange_code("auth-code", redirect_uri="http://localhost:8000/callback")

        assert tokens == OAuthTokens(access_token="tok-must-never-be-logged", user_id="12345678", expires_in=473039999)

    async def test__token_never_logged(
        self, client: PolarOAuthClient, httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        httpx_mock.add_response(
            url=_TOKEN_URL,
            method="POST",
            json={"access_token": "tok-must-never-be-logged", "expires_in": 1, "x_user_id": 1},
        )
        httpx_mock.add_response(url=_USERS_URL, method="POST", status_code=codes.OK)

        with caplog.at_level("DEBUG"):
            tokens = await client.exchange_code("auth-code", redirect_uri="http://localhost:8000/callback")
            await client.register_user(access_token=tokens.access_token, member_id="yannick")

        assert "tok-must-never-be-logged" not in caplog.text

    async def test__exchange_code__sends_basic_auth_and_form_body(
        self, client: PolarOAuthClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url=_TOKEN_URL, method="POST", json={"access_token": "tok", "expires_in": 1, "x_user_id": 1}
        )

        await client.exchange_code("auth-code", redirect_uri="http://localhost:8000/callback")

        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"].startswith("Basic ")
        assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
        body = request.content.decode()
        assert "grant_type=authorization_code" in body
        assert "code=auth-code" in body
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback" in body

    async def test__exchange_code__invalid_grant__raises(
        self, client: PolarOAuthClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url=_TOKEN_URL, method="POST", status_code=codes.BAD_REQUEST, json={"error": "invalid_grant"}
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.exchange_code("auth-code", redirect_uri="http://localhost:8000/callback")
        assert exc_info.value.response.status_code == codes.BAD_REQUEST

    async def test__exchange_code__401__raises(self, client: PolarOAuthClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url=_TOKEN_URL, method="POST", status_code=codes.UNAUTHORIZED)

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.exchange_code("auth-code", redirect_uri="http://localhost:8000/callback")
        assert exc_info.value.response.status_code == codes.UNAUTHORIZED

    async def test__exchange_code__malformed_response__raises_key_error(
        self, client: PolarOAuthClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(url=_TOKEN_URL, method="POST", json={"token_type": "bearer"})

        with pytest.raises(KeyError):
            await client.exchange_code("auth-code", redirect_uri="http://localhost:8000/callback")

    async def test__register_user__200__newly_registered(
        self, client: PolarOAuthClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(url=_USERS_URL, method="POST", status_code=codes.OK)

        result = await client.register_user(access_token="tok", member_id="yannick")

        assert result is True

    async def test__register_user__sends_bearer_and_member_id(
        self, client: PolarOAuthClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(url=_USERS_URL, method="POST", status_code=codes.OK)

        await client.register_user(access_token="tok-must-never-be-logged", member_id="yannick")

        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"] == "Bearer tok-must-never-be-logged"
        assert b"yannick" in request.content

    async def test__register_user__409__already_registered__not_an_error(
        self, client: PolarOAuthClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(url=_USERS_URL, method="POST", status_code=codes.CONFLICT)

        result = await client.register_user(access_token="tok", member_id="yannick")

        assert result is False

    async def test__register_user__403__raises(self, client: PolarOAuthClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url=_USERS_URL, method="POST", status_code=codes.FORBIDDEN)

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.register_user(access_token="tok", member_id="yannick")
        assert exc_info.value.response.status_code == codes.FORBIDDEN

    async def test__post__retries_5xx_then_succeeds(
        self, client: PolarOAuthClient, httpx_mock: HTTPXMock, mock_tenacity: None
    ) -> None:
        httpx_mock.add_response(url=_USERS_URL, method="POST", status_code=codes.INTERNAL_SERVER_ERROR)
        httpx_mock.add_response(url=_USERS_URL, method="POST", status_code=codes.OK)

        result = await client.register_user(access_token="tok", member_id="yannick")

        assert result is True
        assert len(httpx_mock.get_requests()) == 2

    async def test__post__retries_network_error_then_succeeds(
        self, client: PolarOAuthClient, httpx_mock: HTTPXMock, mock_tenacity: None
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectError("Network down"))
        httpx_mock.add_response(url=_USERS_URL, method="POST", status_code=codes.OK)

        result = await client.register_user(access_token="tok", member_id="yannick")

        assert result is True
        assert len(httpx_mock.get_requests()) == 2

    async def test__post__generic_error__not_retried(self, client: PolarOAuthClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_exception(RuntimeError("Unexpected crash"))

        with pytest.raises(RuntimeError, match="Unexpected crash"):
            await client.register_user(access_token="tok", member_id="yannick")

        assert len(httpx_mock.get_requests()) == 1

    async def test__post__stops_after_the_instance_max_retries(
        self, httpx_mock: HTTPXMock, mock_tenacity_sleep_only: None
    ) -> None:
        client = PolarOAuthClient(
            client_id="dummy-client-id",
            client_secret="dummy-client-secret",
            authorization_url=HttpUrl("https://flow.polar.com/oauth2/authorization"),
            token_url=HttpUrl(_TOKEN_URL),
            registration_base_url=HttpUrl("https://www.polaraccesslink.com"),
            max_retries=2,
        )
        for _ in range(2):
            httpx_mock.add_response(url=_USERS_URL, method="POST", status_code=codes.INTERNAL_SERVER_ERROR)

        with pytest.raises(httpx.HTTPStatusError):
            await client.register_user(access_token="tok", member_id="yannick")

        assert len(httpx_mock.get_requests()) == 2
