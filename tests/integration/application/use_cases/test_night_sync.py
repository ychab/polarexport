from datetime import date
from pathlib import Path

import pytest

from polarexport.application.inputs.night import NightSyncInput
from polarexport.application.use_cases.night_sync import NightSyncUseCase
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore

from tests.integration.utils.wiremock import WireMockContext


@pytest.fixture
def day() -> date:
    return date(2026, 8, 15)


@pytest.fixture
def date_range(day: date) -> DateRange:
    return DateRange(date_min=day, date_max=day)


@pytest.fixture
def night_store(tmp_path: Path) -> FilesystemNightStore:
    return FilesystemNightStore(data_dir=tmp_path / "data")


@pytest.mark.wiremock
class TestNightSyncUseCase:
    async def test__happy_path__fetches_and_persists_to_store(
        self,
        polar_client: PolarAccessLinkClient,
        night_store: FilesystemNightStore,
        date_range: DateRange,
        day: date,
    ) -> None:
        sources = frozenset({NightSource.SLEEP, NightSource.RECHARGE, NightSource.HEART_RATE})
        sync_in = NightSyncInput(date_range=date_range, sources=sources)
        use_case = NightSyncUseCase(night_provider=polar_client, night_store=night_store)

        report = await use_case.sync(sync_in, today=day)

        assert report.stats[NightSource.SLEEP].availability == SourceAvailability.AVAILABLE
        assert report.stats[NightSource.SLEEP].fetched == 1
        stored = await night_store.read(NightSource.SLEEP, date_range)
        payload = stored[day].payload
        assert payload is not None
        assert payload["date"] == day.isoformat()

    async def test__403_on_one_source__other_sources_sync_and_403_leaves_durable_record(
        self,
        polar_client: PolarAccessLinkClient,
        night_store: FilesystemNightStore,
        date_range: DateRange,
        day: date,
        polar_wiremock: WireMockContext,
    ) -> None:
        polar_wiremock.create_mapping(
            method="GET",
            url_path=f"/v3/users/nightly-recharge/{day.isoformat()}",
            status=403,
        )
        sources = frozenset({NightSource.SLEEP, NightSource.RECHARGE})
        sync_in = NightSyncInput(date_range=date_range, sources=sources)
        use_case = NightSyncUseCase(night_provider=polar_client, night_store=night_store)

        report = await use_case.sync(sync_in, today=day)

        assert report.stats[NightSource.SLEEP].availability == SourceAvailability.AVAILABLE
        assert report.stats[NightSource.RECHARGE].availability == SourceAvailability.UNAVAILABLE
        # The record must be durable — readable independently of this sync run, the way a later,
        # separate `export` invocation (possibly under `--no-refresh`) would read it.
        assert await night_store.read_availability(NightSource.RECHARGE) == SourceAvailability.UNAVAILABLE
        assert await night_store.read_availability(NightSource.SLEEP) == SourceAvailability.AVAILABLE

    async def test__second_sync__nothing_re_fetched_from_polar(
        self,
        polar_client: PolarAccessLinkClient,
        night_store: FilesystemNightStore,
        date_range: DateRange,
        day: date,
        polar_wiremock: WireMockContext,
    ) -> None:
        sources = frozenset({NightSource.SLEEP, NightSource.RECHARGE, NightSource.HEART_RATE})
        sync_in = NightSyncInput(date_range=date_range, sources=sources)
        use_case = NightSyncUseCase(night_provider=polar_client, night_store=night_store)
        await use_case.sync(sync_in, today=day)
        request_count_before = polar_wiremock.count_requests()

        report = await use_case.sync(sync_in, today=day)

        assert polar_wiremock.count_requests() == request_count_before
        assert all(stat.fetched == 0 and stat.skipped == 1 for stat in report.stats.values())
