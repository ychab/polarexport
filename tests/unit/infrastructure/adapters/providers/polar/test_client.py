from collections.abc import Iterable
from datetime import date
from typing import cast
from unittest import mock

import httpx
from httpx import codes

from pydantic import HttpUrl

import pytest
from pytest_httpx import HTTPXMock
from tenacity import stop_after_attempt

from polarexport.application.ports.providers.night import SourceFetchResult
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.providers.polar.exceptions import PolarRateLimitError


class TestPolarAccessLinkClient:
    @pytest.fixture
    async def client(self) -> PolarAccessLinkClient:
        return PolarAccessLinkClient(
            access_token="dummy-access-token",
            user_id="dummy-user",
            base_url=HttpUrl("https://api.example.com"),
            concurrency=2,
        )

    @pytest.fixture
    def mock_tenacity(self) -> Iterable[None]:
        retry_controller = PolarAccessLinkClient._request.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep
        original_stop = retry_controller.stop

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        retry_controller.stop = stop_after_attempt(5)
        yield
        retry_controller.sleep = original_sleep
        retry_controller.stop = original_stop

    @pytest.fixture
    def mock_tenacity_sleep_only(self) -> Iterable[None]:
        # Leaves the real `stop=` in place so it reads `max_retries` from the client instance.
        retry_controller = PolarAccessLinkClient._request.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        yield
        retry_controller.sleep = original_sleep

    # -------------------------------------------------------------------------
    # Per-date sources
    # -------------------------------------------------------------------------

    async def test__fetch__sleep__200(self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
            json={"date": day.isoformat(), "polar_user": "https://polaraccesslink.com/v3/users/1"},
        )

        result = await client.fetch(NightSource.SLEEP, [day])

        assert result == SourceFetchResult(
            payloads={day: {"date": day.isoformat(), "polar_user": "https://polaraccesslink.com/v3/users/1"}},
            availability=SourceAvailability.AVAILABLE,
            request_count=1,
        )

    async def test__fetch__recharge__200(self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/nightly-recharge/{day.isoformat()}",
            json={"date": day.isoformat()},
        )

        result = await client.fetch(NightSource.RECHARGE, [day])

        assert result.payloads == {day: {"date": day.isoformat()}}
        assert result.availability == SourceAvailability.AVAILABLE

    async def test__fetch__heart_rate__200(self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/continuous-heart-rate/{day.isoformat()}",
            json={"date": day.isoformat()},
        )

        result = await client.fetch(NightSource.HEART_RATE, [day])

        assert result.payloads == {day: {"date": day.isoformat()}}

    async def test__fetch__per_date__multiple_dates(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        dates = [date(2026, 8, 15), date(2026, 8, 16), date(2026, 8, 17)]
        for day in dates:
            httpx_mock.add_response(
                url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
                json={"date": day.isoformat()},
            )

        result = await client.fetch(NightSource.SLEEP, dates)

        assert set(result.payloads) == set(dates)
        assert result.request_count == 3

    async def test__fetch__404__gap(self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
            status_code=codes.NOT_FOUND,
        )

        result = await client.fetch(NightSource.SLEEP, [day])

        assert result.payloads == {day: None}
        assert result.availability == SourceAvailability.AVAILABLE

    async def test__fetch__403__unavailable(self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
            status_code=codes.FORBIDDEN,
        )

        result = await client.fetch(NightSource.SLEEP, [day])

        assert result == SourceFetchResult(payloads={}, availability=SourceAvailability.UNAVAILABLE, request_count=1)

    async def test__fetch__429__after_retries(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock, mock_tenacity: None
    ) -> None:
        day = date(2026, 8, 15)
        for _ in range(5):
            httpx_mock.add_response(
                url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
                status_code=codes.TOO_MANY_REQUESTS,
            )

        with pytest.raises(PolarRateLimitError):
            await client.fetch(NightSource.SLEEP, [day])

    async def test__fetch__500__propagates(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock, mock_tenacity: None
    ) -> None:
        day = date(2026, 8, 15)
        for _ in range(5):
            httpx_mock.add_response(
                url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
                status_code=codes.INTERNAL_SERVER_ERROR,
            )

        with pytest.raises(httpx.HTTPStatusError):
            await client.fetch(NightSource.SLEEP, [day])

    async def test__fetch__500__stops_after_the_instance_max_retries(
        self, httpx_mock: HTTPXMock, mock_tenacity_sleep_only: None
    ) -> None:
        # Regression: the stop condition used to read `polar_settings.HTTP_MAX_RETRIES` at
        # class-definition time, so a per-instance `max_retries` was silently ignored.
        client = PolarAccessLinkClient(
            access_token="dummy-access-token",
            user_id="dummy-user",
            base_url=HttpUrl("https://api.example.com"),
            concurrency=1,
            max_retries=2,
        )
        day = date(2026, 8, 15)
        for _ in range(2):
            httpx_mock.add_response(
                url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
                status_code=codes.INTERNAL_SERVER_ERROR,
            )

        with pytest.raises(httpx.HTTPStatusError):
            await client.fetch(NightSource.SLEEP, [day])

        assert len(httpx_mock.get_requests()) == 2

    async def test__fetch__network_error__retries_then_succeeds(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock, mock_tenacity: None
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_exception(httpx.ConnectError("Network down"))
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
            json={"date": day.isoformat()},
        )

        result = await client.fetch(NightSource.SLEEP, [day])

        assert result.payloads == {day: {"date": day.isoformat()}}
        assert len(httpx_mock.get_requests()) == 2

    async def test__fetch__generic_error__not_retried(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_exception(RuntimeError("Unexpected crash"))

        with pytest.raises(RuntimeError, match="Unexpected crash"):
            await client.fetch(NightSource.SLEEP, [day])

        assert len(httpx_mock.get_requests()) == 1

    async def test__fetch__204__gap(self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
            status_code=codes.NO_CONTENT,
        )

        result = await client.fetch(NightSource.SLEEP, [day])

        assert result.payloads == {day: None}

    # -------------------------------------------------------------------------
    # Range sources
    # -------------------------------------------------------------------------

    async def test__fetch__skin_temperature__200(self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/biosensing/skintemperature?from={day.isoformat()}&to={day.isoformat()}",
            json=[{"sleep_date": day.isoformat(), "deviation_from_baseline_celsius": 0.3}],
        )

        result = await client.fetch(NightSource.SKIN_TEMPERATURE, [day])

        assert result.payloads == {day: {"sleep_date": day.isoformat(), "deviation_from_baseline_celsius": 0.3}}
        assert result.request_count == 1

    async def test__fetch__skin_temperature__204__gap(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        dates = [date(2026, 8, 15), date(2026, 8, 16)]
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/biosensing/skintemperature?from={dates[0].isoformat()}&to={dates[1].isoformat()}",
            status_code=codes.NO_CONTENT,
        )

        result = await client.fetch(NightSource.SKIN_TEMPERATURE, dates)

        assert result.payloads == {dates[0]: None, dates[1]: None}

    async def test__fetch__skin_temperature__404__gap(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        dates = [date(2026, 8, 15), date(2026, 8, 16)]
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/biosensing/skintemperature?from={dates[0].isoformat()}&to={dates[1].isoformat()}",
            status_code=codes.NOT_FOUND,
        )

        result = await client.fetch(NightSource.SKIN_TEMPERATURE, dates)

        assert result.payloads == {dates[0]: None, dates[1]: None}

    async def test__fetch__skin_temperature__403__unavailable(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/biosensing/skintemperature?from={day.isoformat()}&to={day.isoformat()}",
            status_code=codes.FORBIDDEN,
        )

        result = await client.fetch(NightSource.SKIN_TEMPERATURE, [day])

        assert result == SourceFetchResult(payloads={}, availability=SourceAvailability.UNAVAILABLE, request_count=1)

    async def test__fetch__sleepwise__200__merges_both(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/alertness/date?from={day.isoformat()}&to={day.isoformat()}",
            json=[{"sleep_period_start_time": f"{day.isoformat()}T22:00:00", "grade": 9.0}],
        )
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/circadian-bedtime/date?from={day.isoformat()}&to={day.isoformat()}",
            json=[{"preferred_sleep_period_start_time": f"{day.isoformat()}T22:00:00", "quality": "OK"}],
        )

        result = await client.fetch(NightSource.SLEEPWISE, [day])

        assert result.payloads[day] == {
            "date": day.isoformat(),
            "alertness": {"sleep_period_start_time": f"{day.isoformat()}T22:00:00", "grade": 9.0},
            "circadian_bedtime": {"preferred_sleep_period_start_time": f"{day.isoformat()}T22:00:00", "quality": "OK"},
        }
        assert result.request_count == 2

    async def test__fetch__sleepwise__204_both__gap(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/alertness/date?from={day.isoformat()}&to={day.isoformat()}",
            status_code=codes.NO_CONTENT,
        )
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/circadian-bedtime/date?from={day.isoformat()}&to={day.isoformat()}",
            status_code=codes.NO_CONTENT,
        )

        result = await client.fetch(NightSource.SLEEPWISE, [day])

        assert result.payloads == {day: None}

    async def test__fetch__sleepwise__alertness_404__then_circadian_200(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/alertness/date?from={day.isoformat()}&to={day.isoformat()}",
            status_code=codes.NOT_FOUND,
        )
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/circadian-bedtime/date?from={day.isoformat()}&to={day.isoformat()}",
            json=[
                {
                    "preferred_sleep_period_start_time": f"{day.isoformat()}T22:00:00",
                    "quality": "OK",
                },
                {"quality": "no timestamp on this one, should be skipped"},
            ],
        )

        result = await client.fetch(NightSource.SLEEPWISE, [day])

        assert result.payloads[day] == {
            "date": day.isoformat(),
            "alertness": None,
            "circadian_bedtime": {
                "preferred_sleep_period_start_time": f"{day.isoformat()}T22:00:00",
                "quality": "OK",
            },
        }

    async def test__fetch__sleepwise__circadian_404__gap_for_that_side(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/alertness/date?from={day.isoformat()}&to={day.isoformat()}",
            json=[{"sleep_period_start_time": f"{day.isoformat()}T22:00:00", "grade": 9.0}],
        )
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/circadian-bedtime/date?from={day.isoformat()}&to={day.isoformat()}",
            status_code=codes.NOT_FOUND,
        )

        result = await client.fetch(NightSource.SLEEPWISE, [day])

        assert result.payloads[day] == {
            "date": day.isoformat(),
            "alertness": {"sleep_period_start_time": f"{day.isoformat()}T22:00:00", "grade": 9.0},
            "circadian_bedtime": None,
        }

    async def test__fetch__sleepwise__alertness_403__unavailable(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/alertness/date?from={day.isoformat()}&to={day.isoformat()}",
            status_code=codes.FORBIDDEN,
        )

        result = await client.fetch(NightSource.SLEEPWISE, [day])

        assert result == SourceFetchResult(payloads={}, availability=SourceAvailability.UNAVAILABLE, request_count=1)

    async def test__fetch__sleepwise__circadian_403__unavailable(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/alertness/date?from={day.isoformat()}&to={day.isoformat()}",
            status_code=codes.NO_CONTENT,
        )
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleepwise/circadian-bedtime/date?from={day.isoformat()}&to={day.isoformat()}",
            status_code=codes.FORBIDDEN,
        )

        result = await client.fetch(NightSource.SLEEPWISE, [day])

        assert result == SourceFetchResult(payloads={}, availability=SourceAvailability.UNAVAILABLE, request_count=2)

    # -------------------------------------------------------------------------
    # Dispatch / cross-cutting
    # -------------------------------------------------------------------------

    async def test__fetch__unsupported_source__raises(self, client: PolarAccessLinkClient) -> None:
        with pytest.raises(ValueError, match="Unsupported night source"):
            await client.fetch(cast(NightSource, "unsupported"), [date(2026, 8, 15)])

    async def test__fetch__authorization_header_sent(
        self, client: PolarAccessLinkClient, httpx_mock: HTTPXMock
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
            json={"date": day.isoformat()},
        )

        await client.fetch(NightSource.SLEEP, [day])

        assert httpx_mock.get_requests()[0].headers["Authorization"] == "Bearer dummy-access-token"

    async def test__fetch__token_never_logged(
        self,
        client: PolarAccessLinkClient,
        httpx_mock: HTTPXMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
            json={"date": day.isoformat()},
        )

        with caplog.at_level("DEBUG"):
            await client.fetch(NightSource.SLEEP, [day])

        assert "dummy-access-token" not in caplog.text

    async def test__fetch__rate_limit_headers_logged(
        self,
        client: PolarAccessLinkClient,
        httpx_mock: HTTPXMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
            json={"date": day.isoformat()},
            headers={"RateLimit-Limit": "500, 5000", "RateLimit-Usage": "1, 2"},
        )

        with caplog.at_level("DEBUG"):
            await client.fetch(NightSource.SLEEP, [day])

        assert "Polar rate limit" in caplog.text

    async def test__fetch__no_rate_limit_headers__not_logged(
        self,
        client: PolarAccessLinkClient,
        httpx_mock: HTTPXMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        day = date(2026, 8, 15)
        httpx_mock.add_response(
            url=f"https://api.example.com/v3/users/sleep/{day.isoformat()}",
            json={"date": day.isoformat()},
        )

        with caplog.at_level("DEBUG"):
            await client.fetch(NightSource.SLEEP, [day])

        assert "Polar rate limit" not in caplog.text
