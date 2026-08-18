import os
from collections.abc import AsyncGenerator
from collections.abc import Iterable

from pydantic import HttpUrl

import pytest
from tenacity import stop_after_attempt

from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient

from tests.integration.utils.wiremock import WireMockContext


@pytest.fixture
async def polar_client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[PolarAccessLinkClient]:
    base_url = os.getenv("WIREMOCK_POLAR_BASE_URL", "")

    retry_controller = PolarAccessLinkClient._request.retry  # type: ignore[attr-defined]
    monkeypatch.setattr(retry_controller, "stop", stop_after_attempt(1))

    async with PolarAccessLinkClient(
        access_token="dummy-access-token",
        user_id="dummy-user",
        base_url=HttpUrl(base_url),
        concurrency=2,
        verify_ssl=False,  # WireMock serves a self-signed cert on its https port
    ) as client:
        yield client


@pytest.fixture
def polar_wiremock() -> Iterable[WireMockContext]:
    with WireMockContext(base_url=os.getenv("WIREMOCK_POLAR_ADMIN_URL", "")) as wiremock_context:
        yield wiremock_context
