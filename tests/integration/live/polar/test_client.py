from collections.abc import AsyncGenerator
from datetime import date
from datetime import timedelta

import pytest

from polarexport.domain.enums import NightSource
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarNightMapper
from polarexport.infrastructure.config.settings.polar import polar_settings


@pytest.mark.polar_live
class TestPolarAccessLinkClientLive:
    """Live integration tests against the real Polar AccessLink API.

    Requirements:
        - POLAR_ACCESS_TOKEN and POLAR_USER_ID set in .env (see docs/authentication.md).

    Warning:
        These tests hit the real API and are NOT run by default.

    To run:
        uv run pytest ./tests/integration/live/polar --polar-live -m polar_live -v --no-cov
    """

    @pytest.fixture
    async def polar_client_live(self) -> AsyncGenerator[PolarAccessLinkClient]:
        async with PolarAccessLinkClient(
            access_token=polar_settings.ACCESS_TOKEN,
            user_id=polar_settings.USER_ID,
            base_url=polar_settings.BASE_URL,
        ) as client:
            yield client

    @pytest.fixture
    def mapper(self) -> PolarNightMapper:
        return PolarNightMapper()

    @pytest.fixture
    def day(self) -> date:
        return date.today() - timedelta(days=2)

    async def test__fetch__sleep(
        self, polar_client_live: PolarAccessLinkClient, mapper: PolarNightMapper, day: date
    ) -> None:
        result = await polar_client_live.fetch(NightSource.SLEEP, [day])

        payload = result.payloads.get(day)
        if payload is not None:
            mapper.to_sleep(payload)

    async def test__fetch__nightly_recharge(
        self, polar_client_live: PolarAccessLinkClient, mapper: PolarNightMapper, day: date
    ) -> None:
        result = await polar_client_live.fetch(NightSource.RECHARGE, [day])

        payload = result.payloads.get(day)
        if payload is not None:
            mapper.to_nightly_recharge(payload)

    async def test__fetch__continuous_heart_rate(
        self, polar_client_live: PolarAccessLinkClient, mapper: PolarNightMapper, day: date
    ) -> None:
        result = await polar_client_live.fetch(NightSource.HEART_RATE, [day])

        payload = result.payloads.get(day)
        if payload is not None:
            mapper.to_continuous_heart_rate(payload)

    async def test__fetch__skin_temperature(
        self, polar_client_live: PolarAccessLinkClient, mapper: PolarNightMapper, day: date
    ) -> None:
        result = await polar_client_live.fetch(NightSource.SKIN_TEMPERATURE, [day])

        payload = result.payloads.get(day)
        if payload is not None:
            mapper.to_skin_temperature(payload)

    async def test__fetch__sleepwise(
        self, polar_client_live: PolarAccessLinkClient, mapper: PolarNightMapper, day: date
    ) -> None:
        result = await polar_client_live.fetch(NightSource.SLEEPWISE, [day])

        payload = result.payloads.get(day)
        if payload is not None:
            mapper.to_sleepwise(payload)
