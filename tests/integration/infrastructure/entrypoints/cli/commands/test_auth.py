import asyncio
import json
import os
import socket
from datetime import UTC
from datetime import datetime
from pathlib import Path

import httpx

from pydantic import HttpUrl

import pytest

from polarexport.application.inputs.auth import AuthLoginInput
from polarexport.infrastructure.adapters.providers.polar.auth import PolarOAuthClient
from polarexport.infrastructure.entrypoints.cli.commands.auth import auth_logic

from tests.integration.utils.wiremock import WireMockContext


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _wait_until_listening(port: int, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            if asyncio.get_running_loop().time() > deadline:
                raise
            await asyncio.sleep(0.01)
        else:
            writer.close()
            await writer.wait_closed()
            return


@pytest.fixture
def redirect_port() -> int:
    return _free_port()


@pytest.fixture
def oauth_client() -> PolarOAuthClient:
    base_url = os.getenv("WIREMOCK_POLAR_BASE_URL", "")
    return PolarOAuthClient(
        client_id="dummy-client-id",
        client_secret="dummy-client-secret",
        authorization_url=HttpUrl("https://flow.polar.com/oauth2/authorization"),
        token_url=HttpUrl(f"{base_url}/v2/oauth2/token"),
        registration_base_url=HttpUrl(base_url),
        verify_ssl=False,  # WireMock serves a self-signed cert on its https port
    )


@pytest.fixture
def auth_in(redirect_port: int, tmp_path: Path) -> AuthLoginInput:
    return AuthLoginInput(
        member_id="integration-member",
        redirect_uri=f"http://127.0.0.1:{redirect_port}/callback",
        credentials_file=tmp_path / "data" / "auth" / "credentials.json",
        force=False,
        timeout=10.0,
    )


@pytest.fixture
def obtained_at() -> datetime:
    return datetime(2026, 8, 18, 16, 42, 5, tzinfo=UTC)


@pytest.mark.wiremock
class TestAuthLogic:
    async def test__happy_path__fresh_registration__credentials_written(
        self, oauth_client: PolarOAuthClient, auth_in: AuthLoginInput, redirect_port: int, obtained_at: datetime
    ) -> None:
        task = asyncio.create_task(
            auth_logic(auth_in, client=oauth_client, state="expected-state", obtained_at=obtained_at)
        )
        await _wait_until_listening(redirect_port)

        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                f"http://127.0.0.1:{redirect_port}/callback?code=wiremock-code&state=expected-state"
            )
        assert response.status_code == 200

        report = await task

        assert report.member_id == "integration-member"
        assert report.newly_registered is True
        envelope = json.loads(auth_in.credentials_file.read_text(encoding="utf-8"))
        assert envelope["access_token"] == "wiremock-access-token"
        assert envelope["user_id"] == report.user_id
        assert envelope["obtained_at"] == obtained_at.isoformat()

    async def test__already_registered__409_treated_as_success(
        self,
        oauth_client: PolarOAuthClient,
        auth_in: AuthLoginInput,
        redirect_port: int,
        obtained_at: datetime,
        polar_wiremock: WireMockContext,
    ) -> None:
        polar_wiremock.create_mapping(method="POST", url_path="/v3/users", status=409)

        task = asyncio.create_task(
            auth_logic(auth_in, client=oauth_client, state="expected-state", obtained_at=obtained_at)
        )
        await _wait_until_listening(redirect_port)

        async with httpx.AsyncClient() as http_client:
            await http_client.get(f"http://127.0.0.1:{redirect_port}/callback?code=wiremock-code&state=expected-state")

        report = await task

        assert report.newly_registered is False
        assert auth_in.credentials_file.is_file()
