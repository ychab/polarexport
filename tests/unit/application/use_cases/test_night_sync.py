import logging
from datetime import date
from datetime import datetime
from unittest import mock

import pytest

from polarexport.application.ports.providers.night import SourceFetchResult
from polarexport.application.use_cases.night_sync import NightSyncUseCase
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.utils.dates import iterate_dates
from polarexport.domain.value_objects.date_range import DateRange

from tests.unit.factories.inputs.night import NightSyncInputFactory


class TestNightSyncUseCase:
    @pytest.fixture
    def today(self) -> date:
        return date(2026, 8, 17)

    @pytest.fixture
    def date_range(self) -> DateRange:
        return DateRange(date_min=date(2026, 8, 10), date_max=date(2026, 8, 11))

    @pytest.fixture
    def use_case(self, mock_night_provider: mock.AsyncMock, mock_night_store: mock.AsyncMock) -> NightSyncUseCase:
        return NightSyncUseCase(night_provider=mock_night_provider, night_store=mock_night_store)

    async def test__everything_missing__fetched_and_written(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        date_range: DateRange,
        today: date,
    ) -> None:
        day1, day2 = date(2026, 8, 10), date(2026, 8, 11)
        mock_night_store.missing.return_value = (day1, day2)
        mock_night_provider.fetch.return_value = SourceFetchResult(
            payloads={day1: {"foo": "bar"}, day2: {"foo": "baz"}},
            availability=SourceAvailability.AVAILABLE,
            request_count=2,
        )
        sync_in = NightSyncInputFactory.build(date_range=date_range, sources=frozenset({NightSource.SLEEP}))

        report = await use_case.sync(sync_in, today=today)

        stat = report.stats[NightSource.SLEEP]
        assert stat.fetched == 2
        assert stat.skipped == 0
        assert stat.empty == 0
        assert stat.requests == 2
        assert mock_night_store.write.call_count == 2
        written_payloads = {call.args[0].date: call.args[0].payload for call in mock_night_store.write.call_args_list}
        assert written_payloads == {day1: {"foo": "bar"}, day2: {"foo": "baz"}}

    async def test__nothing_missing__no_prior_record__defaults_to_available(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        date_range: DateRange,
        today: date,
    ) -> None:
        mock_night_store.missing.return_value = ()
        mock_night_store.read_availability.return_value = None
        sync_in = NightSyncInputFactory.build(date_range=date_range, sources=frozenset({NightSource.SLEEP}))

        report = await use_case.sync(sync_in, today=today)

        mock_night_provider.fetch.assert_not_awaited()
        stat = report.stats[NightSource.SLEEP]
        assert stat.skipped == 2
        assert stat.fetched == 0
        assert stat.availability == SourceAvailability.AVAILABLE

    async def test__nothing_missing__prior_record_unavailable__reports_stored_availability(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        date_range: DateRange,
        today: date,
    ) -> None:
        # Nothing is asked of Polar on this path, so nothing gets measured here — the last real
        # observation (a 403) must still be what gets reported, not a hardcoded AVAILABLE.
        mock_night_store.missing.return_value = ()
        mock_night_store.read_availability.return_value = SourceAvailability.UNAVAILABLE
        sync_in = NightSyncInputFactory.build(date_range=date_range, sources=frozenset({NightSource.SLEEP}))

        report = await use_case.sync(sync_in, today=today)

        mock_night_provider.fetch.assert_not_awaited()
        stat = report.stats[NightSource.SLEEP]
        assert stat.availability == SourceAvailability.UNAVAILABLE

    async def test__source_fetched__availability_written_to_store(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        date_range: DateRange,
        today: date,
    ) -> None:
        mock_night_store.missing.return_value = (date(2026, 8, 10), date(2026, 8, 11))
        mock_night_provider.fetch.return_value = SourceFetchResult(
            payloads={date(2026, 8, 10): {"x": 1}, date(2026, 8, 11): {"x": 2}},
            availability=SourceAvailability.AVAILABLE,
            request_count=2,
        )
        sync_in = NightSyncInputFactory.build(date_range=date_range, sources=frozenset({NightSource.SLEEP}))

        await use_case.sync(sync_in, today=today)

        mock_night_store.write_availability.assert_awaited_once()
        call = mock_night_store.write_availability.call_args
        assert call.args == (NightSource.SLEEP, SourceAvailability.AVAILABLE)
        assert isinstance(call.kwargs["observed_at"], datetime)

    async def test__force_refresh__provider_awaited_even_for_stored_dates(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        date_range: DateRange,
        today: date,
    ) -> None:
        mock_night_provider.fetch.return_value = SourceFetchResult(
            payloads={}, availability=SourceAvailability.AVAILABLE, request_count=0
        )
        sync_in = NightSyncInputFactory.build(
            date_range=date_range, sources=frozenset({NightSource.SLEEP}), force_refresh=True
        )

        await use_case.sync(sync_in, today=today)

        mock_night_store.missing.assert_not_awaited()
        mock_night_provider.fetch.assert_awaited_once()
        called_source, called_dates = mock_night_provider.fetch.call_args.args
        assert called_source == NightSource.SLEEP
        assert called_dates == (date(2026, 8, 10), date(2026, 8, 11))

    async def test__source_unavailable__other_sources_still_synced(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        date_range: DateRange,
        today: date,
    ) -> None:
        mock_night_store.missing.return_value = (date(2026, 8, 10), date(2026, 8, 11))

        def fetch_side_effect(source: NightSource, dates: tuple[date, ...]) -> SourceFetchResult:
            if source == NightSource.SLEEP:
                return SourceFetchResult(payloads={}, availability=SourceAvailability.UNAVAILABLE, request_count=1)
            return SourceFetchResult(
                payloads=dict.fromkeys(dates, {"x": 1}),
                availability=SourceAvailability.AVAILABLE,
                request_count=len(dates),
            )

        mock_night_provider.fetch.side_effect = fetch_side_effect
        sync_in = NightSyncInputFactory.build(
            date_range=date_range, sources=frozenset({NightSource.SLEEP, NightSource.RECHARGE})
        )

        report = await use_case.sync(sync_in, today=today)

        assert report.stats[NightSource.SLEEP].availability == SourceAvailability.UNAVAILABLE
        assert report.stats[NightSource.RECHARGE].availability == SourceAvailability.AVAILABLE

    async def test__source_not_in_sources__never_fetched(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        date_range: DateRange,
        today: date,
    ) -> None:
        mock_night_store.missing.return_value = (date(2026, 8, 10),)
        mock_night_provider.fetch.return_value = SourceFetchResult(
            payloads={date(2026, 8, 10): {"x": 1}}, availability=SourceAvailability.AVAILABLE, request_count=1
        )
        sync_in = NightSyncInputFactory.build(date_range=date_range, sources=frozenset({NightSource.SLEEP}))

        report = await use_case.sync(sync_in, today=today)

        assert NightSource.RECHARGE not in report.stats
        fetched_sources = {call.args[0] for call in mock_night_provider.fetch.call_args_list}
        assert fetched_sources == {NightSource.SLEEP}

    async def test__limit__truncates_before_missing_is_checked(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        today: date,
    ) -> None:
        date_range = DateRange(date_min=date(2026, 8, 5), date_max=date(2026, 8, 11))
        mock_night_store.missing.return_value = ()
        sync_in = NightSyncInputFactory.build(date_range=date_range, sources=frozenset({NightSource.SLEEP}), limit=3)

        await use_case.sync(sync_in, today=today)

        called_dates = mock_night_store.missing.call_args.args[1]
        assert called_dates == tuple(iterate_dates(date_range))[-3:]

    async def test__date_min_outside_window__warns_and_proceeds(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        today: date,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        date_range = DateRange(date_min=date(2026, 7, 1), date_max=date(2026, 7, 2))
        mock_night_store.missing.return_value = ()
        sync_in = NightSyncInputFactory.build(date_range=date_range, sources=frozenset({NightSource.SLEEP}))

        with caplog.at_level(logging.WARNING):
            report = await use_case.sync(sync_in, today=today)

        assert report.history_window_warning is not None
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    async def test__empty_payload__written_as_none(
        self,
        use_case: NightSyncUseCase,
        mock_night_provider: mock.AsyncMock,
        mock_night_store: mock.AsyncMock,
        date_range: DateRange,
        today: date,
    ) -> None:
        mock_night_store.missing.return_value = (date(2026, 8, 10),)
        mock_night_provider.fetch.return_value = SourceFetchResult(
            payloads={date(2026, 8, 10): None}, availability=SourceAvailability.AVAILABLE, request_count=1
        )
        sync_in = NightSyncInputFactory.build(date_range=date_range, sources=frozenset({NightSource.SLEEP}))

        report = await use_case.sync(sync_in, today=today)

        stat = report.stats[NightSource.SLEEP]
        assert stat.empty == 1
        assert stat.fetched == 0
        written = mock_night_store.write.call_args.args[0]
        assert written.payload is None
