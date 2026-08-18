import asyncio
import logging
from collections.abc import Sequence
from datetime import date
from datetime import datetime
from typing import Any
from typing import cast

import httpx
from httpx import codes

from pydantic import HttpUrl

from tenacity import RetryCallState
from tenacity import retry
from tenacity import retry_if_exception
from tenacity import wait_exponential

from polarexport.application.ports.providers.night import NightProviderPort
from polarexport.application.ports.providers.night import SourceFetchResult
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.infrastructure.adapters.http import HttpClientMixin
from polarexport.infrastructure.adapters.providers.polar import endpoints
from polarexport.infrastructure.adapters.providers.polar.exceptions import PolarForbiddenError
from polarexport.infrastructure.adapters.providers.polar.exceptions import PolarNotFoundError
from polarexport.infrastructure.adapters.providers.polar.exceptions import PolarRateLimitError

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):  # Retry 429 and 5xx only
        return exception.response.status_code == codes.TOO_MANY_REQUESTS or exception.response.status_code >= 500

    if isinstance(exception, httpx.RequestError):  # Retry network errors
        return True

    return False


def _stop_after_max_retries(retry_state: RetryCallState) -> bool:
    # `stop_after_attempt(polar_settings.HTTP_MAX_RETRIES)` would freeze the limit at class-definition
    # (import) time. Reading it from the instance here keeps it overridable per client.
    client = cast("PolarAccessLinkClient", retry_state.args[0])
    return retry_state.attempt_number >= client._max_retries


class PolarAccessLinkClient(HttpClientMixin, NightProviderPort):
    """Adapter for the Polar AccessLink v3 API.

    Transport only — returns raw payloads, never domain entities. Used as
    `async with PolarAccessLinkClient(...) as client:`.
    """

    def __init__(
        self,
        access_token: str,
        user_id: str,
        base_url: HttpUrl,
        timeout: float = 30.0,
        concurrency: int = 5,
        max_retries: int = 5,
        verify_ssl: bool = True,
    ) -> None:
        super().__init__(base_url=base_url, timeout=timeout, verify_ssl=verify_ssl)
        self._access_token = access_token
        self._user_id = user_id
        self._concurrency = concurrency
        self._max_retries = max_retries

    async def fetch(self, source: NightSource, dates: Sequence[date]) -> SourceFetchResult:
        match source:
            case NightSource.SLEEP:
                return await self._fetch_per_date(endpoints.SLEEP, dates)
            case NightSource.RECHARGE:
                return await self._fetch_per_date(endpoints.NIGHTLY_RECHARGE, dates)
            case NightSource.HEART_RATE:
                return await self._fetch_per_date(endpoints.CONTINUOUS_HEART_RATE, dates)
            case NightSource.SKIN_TEMPERATURE:
                return await self._fetch_skin_temperature(dates)
            case NightSource.SLEEPWISE:
                return await self._fetch_sleepwise(dates)
            case _:
                raise ValueError(f"Unsupported night source: {source}")

    # -------------------------------------------------------------------------
    # Per-date sources
    # -------------------------------------------------------------------------

    async def _fetch_per_date(self, endpoint_template: str, dates: Sequence[date]) -> SourceFetchResult:
        semaphore = asyncio.Semaphore(self._concurrency)
        outcomes = await asyncio.gather(
            *(self._fetch_one(endpoint_template, day, semaphore) for day in dates),
            return_exceptions=True,
        )

        payloads: dict[date, dict[str, Any] | None] = {}
        for outcome in outcomes:
            if isinstance(outcome, PolarForbiddenError):
                return SourceFetchResult(
                    payloads={},
                    availability=SourceAvailability.UNAVAILABLE,
                    request_count=len(dates),
                )
            if isinstance(outcome, BaseException):
                raise outcome
            day, payload = outcome
            payloads[day] = payload

        return SourceFetchResult(
            payloads=payloads, availability=SourceAvailability.AVAILABLE, request_count=len(dates)
        )

    async def _fetch_one(
        self, endpoint_template: str, day: date, semaphore: asyncio.Semaphore
    ) -> tuple[date, dict[str, Any] | None]:
        async with semaphore:
            try:
                payload = await self._get(endpoint_template.format(date=day.isoformat()))
            except PolarNotFoundError:
                return day, None
        return day, cast("dict[str, Any] | None", payload)

    # -------------------------------------------------------------------------
    # Range sources
    # -------------------------------------------------------------------------

    async def _fetch_skin_temperature(self, dates: Sequence[date]) -> SourceFetchResult:
        params = {"from": min(dates).isoformat(), "to": max(dates).isoformat()}
        try:
            raw = await self._get(endpoints.SKIN_TEMPERATURE, params=params)
        except PolarForbiddenError:
            return SourceFetchResult(payloads={}, availability=SourceAvailability.UNAVAILABLE, request_count=1)
        except PolarNotFoundError:
            raw = None

        by_date: dict[date, dict[str, Any]] = {}
        for item in cast("list[dict[str, Any]]", raw) if raw else []:
            by_date[date.fromisoformat(item["sleep_date"])] = item

        payloads: dict[date, dict[str, Any] | None] = {day: by_date.get(day) for day in dates}
        return SourceFetchResult(payloads=payloads, availability=SourceAvailability.AVAILABLE, request_count=1)

    async def _fetch_sleepwise(self, dates: Sequence[date]) -> SourceFetchResult:
        params = {"from": min(dates).isoformat(), "to": max(dates).isoformat()}

        try:
            alertness_raw = await self._get(endpoints.SLEEPWISE_ALERTNESS, params=params)
        except PolarForbiddenError:
            return SourceFetchResult(payloads={}, availability=SourceAvailability.UNAVAILABLE, request_count=1)
        except PolarNotFoundError:
            alertness_raw = None

        try:
            circadian_raw = await self._get(endpoints.SLEEPWISE_CIRCADIAN_BEDTIME, params=params)
        except PolarForbiddenError:
            return SourceFetchResult(payloads={}, availability=SourceAvailability.UNAVAILABLE, request_count=2)
        except PolarNotFoundError:
            circadian_raw = None

        alertness_by_date = self._index_by_date(
            cast("list[dict[str, Any]]", alertness_raw) if alertness_raw else [], "sleep_period_start_time"
        )
        circadian_by_date = self._index_by_date(
            cast("list[dict[str, Any]]", circadian_raw) if circadian_raw else [], "preferred_sleep_period_start_time"
        )

        payloads: dict[date, dict[str, Any] | None] = {}
        for day in dates:
            alertness_item = alertness_by_date.get(day)
            circadian_item = circadian_by_date.get(day)
            payloads[day] = (
                None
                if alertness_item is None and circadian_item is None
                else {"date": day.isoformat(), "alertness": alertness_item, "circadian_bedtime": circadian_item}
            )

        return SourceFetchResult(payloads=payloads, availability=SourceAvailability.AVAILABLE, request_count=2)

    @staticmethod
    def _index_by_date(items: list[dict[str, Any]], time_field: str) -> dict[date, dict[str, Any]]:
        indexed: dict[date, dict[str, Any]] = {}
        for item in items:
            timestamp = item.get(time_field)
            if timestamp is None:
                continue
            indexed[datetime.fromisoformat(timestamp).date()] = item
        return indexed

    # -------------------------------------------------------------------------
    # Transport
    # -------------------------------------------------------------------------

    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=_stop_after_max_retries,
        reraise=True,
    )
    async def _request(self, endpoint: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        response = await self._client.request(
            method="GET",
            url=f"{str(self._base_url).rstrip('/')}{endpoint}",
            headers=self._auth_header(),
            params=params,
        )
        response.raise_for_status()
        return response

    async def _get(self, endpoint: str, *, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any] | None:
        logger.debug("Polar API request", extra={"endpoint": endpoint, "user_id": self._user_id})

        try:
            response = await self._request(endpoint, params=params)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == codes.NOT_FOUND:
                raise PolarNotFoundError(f"No data at {endpoint}") from e
            if status == codes.FORBIDDEN:
                raise PolarForbiddenError(f"Consent missing for {endpoint}") from e
            if status == codes.TOO_MANY_REQUESTS:
                raise PolarRateLimitError(f"Rate limit exceeded for {endpoint}") from e
            raise

        limit = response.headers.get("RateLimit-Limit")
        usage = response.headers.get("RateLimit-Usage")
        if limit is not None or usage is not None:
            logger.debug(
                "Polar rate limit",
                extra={"endpoint": endpoint, "ratelimit_limit": limit, "ratelimit_usage": usage},
            )

        if response.status_code == codes.NO_CONTENT or not response.content:
            return None
        return response.json()  # type: ignore[no-any-return]
