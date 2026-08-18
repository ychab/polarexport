from datetime import date
from datetime import timedelta

import pytest

from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient

from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock
class TestPolarAccessLinkClient:
    async def test__fetch__sleep__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 8, 15)

        result = await polar_client.fetch(NightSource.SLEEP, [day])

        assert result.availability == SourceAvailability.AVAILABLE
        assert result.request_count == 1
        payload = result.payloads[day]
        assert payload is not None
        assert payload["date"] == day.isoformat()
        assert payload["hypnogram"]

    async def test__fetch__nightly_recharge__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 8, 15)

        result = await polar_client.fetch(NightSource.RECHARGE, [day])

        payload = result.payloads[day]
        assert payload is not None
        assert payload["nightly_recharge_status"] == 2

    async def test__fetch__continuous_heart_rate__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 8, 15)

        result = await polar_client.fetch(NightSource.HEART_RATE, [day])

        payload = result.payloads[day]
        assert payload is not None
        assert len(payload["heart_rate_samples"]) == 3

    async def test__fetch__skin_temperature__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2023, 10, 20)

        result = await polar_client.fetch(NightSource.SKIN_TEMPERATURE, [day])

        payload = result.payloads[day]
        assert payload is not None
        assert payload["sleep_date"] == day.isoformat()

    async def test__fetch__sleepwise__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2022, 11, 20)

        result = await polar_client.fetch(NightSource.SLEEPWISE, [day])

        payload = result.payloads[day]
        assert payload is not None
        assert payload["alertness"] is not None
        assert payload["circadian_bedtime"] is not None

    async def test__fetch__404__recorded_as_gap(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 1, 1)

        result = await polar_client.fetch(NightSource.SLEEP, [day])

        assert result.payloads == {day: None}
        assert result.availability == SourceAvailability.AVAILABLE

    async def test__fetch__403__source_unavailable(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 1, 2)

        result = await polar_client.fetch(NightSource.RECHARGE, [day])

        assert result.availability == SourceAvailability.UNAVAILABLE
        assert result.payloads == {}

    async def test__fetch__semaphore_bounds_concurrency__still_issues_all_requests(
        self, polar_client: PolarAccessLinkClient
    ) -> None:
        dates = [date(2026, 8, 1) + timedelta(days=i) for i in range(10)]

        result = await polar_client.fetch(NightSource.HEART_RATE, dates)

        assert result.request_count == 10
        assert len(result.payloads) == 10
        assert set(result.payloads) == set(dates)

    async def test__fetch__sleep__custom_stub_round_trips_verbatim(
        self,
        polar_client: PolarAccessLinkClient,
        polar_wiremock: WireMockContext,
    ) -> None:
        day = date(2026, 3, 1)
        custom_payload = {
            "date": day.isoformat(),
            "polar_user": "https://polaraccesslink.com/v3/users/1",
            "sleep_score": 42,
        }
        polar_wiremock.create_mapping(
            method="GET",
            url_path=f"/v3/users/sleep/{day.isoformat()}",
            status=200,
            json_body=custom_payload,
        )

        result = await polar_client.fetch(NightSource.SLEEP, [day])

        assert result.payloads[day] == custom_payload

    async def test__fetch__heart_rate__custom_stub_status_only__gap(
        self,
        polar_client: PolarAccessLinkClient,
        polar_wiremock: WireMockContext,
    ) -> None:
        day = date(2026, 5, 1)
        polar_wiremock.create_mapping(
            method="GET",
            url_path=f"/v3/users/continuous-heart-rate/{day.isoformat()}",
            status=404,
        )

        result = await polar_client.fetch(NightSource.HEART_RATE, [day])

        assert result.payloads == {day: None}

    async def test__fetch__skin_temperature__query_params_sent_correctly(
        self,
        polar_client: PolarAccessLinkClient,
        polar_wiremock: WireMockContext,
    ) -> None:
        date_min, date_max = date(2026, 4, 1), date(2026, 4, 2)
        polar_wiremock.create_mapping(
            method="GET",
            url_path="/v3/users/biosensing/skintemperature",
            status=200,
            query_params={"from": date_min.isoformat(), "to": date_max.isoformat()},
            json_body=[{"sleep_date": date_min.isoformat(), "deviation_from_baseline_celsius": 1.0}],
        )

        result = await polar_client.fetch(NightSource.SKIN_TEMPERATURE, [date_min, date_max])

        assert result.payloads[date_min] == {
            "sleep_date": date_min.isoformat(),
            "deviation_from_baseline_celsius": 1.0,
        }
        assert result.payloads[date_max] is None
