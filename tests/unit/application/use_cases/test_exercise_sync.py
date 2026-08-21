import logging
from datetime import date
from datetime import datetime
from unittest import mock

import pytest

from polarexport.application.ports.providers.exercise import ExerciseFetchResult
from polarexport.application.use_cases.exercise_sync import ExerciseSyncUseCase
from polarexport.domain.enums import SourceAvailability

from tests.unit.factories.inputs.exercise import ExerciseSyncInputFactory


class TestExerciseSyncUseCase:
    @pytest.fixture
    def today(self) -> date:
        return date(2026, 8, 20)

    @pytest.fixture
    def use_case(
        self,
        mock_exercise_provider: mock.AsyncMock,
        mock_profile_provider: mock.AsyncMock,
        mock_exercise_store: mock.AsyncMock,
        mock_profile_store: mock.AsyncMock,
    ) -> ExerciseSyncUseCase:
        return ExerciseSyncUseCase(
            exercise_provider=mock_exercise_provider,
            profile_provider=mock_profile_provider,
            exercise_store=mock_exercise_store,
            profile_store=mock_profile_store,
        )

    async def test__writes_only_unknown_ids(
        self,
        use_case: ExerciseSyncUseCase,
        mock_exercise_provider: mock.AsyncMock,
        mock_profile_provider: mock.AsyncMock,
        mock_exercise_store: mock.AsyncMock,
        today: date,
    ) -> None:
        mock_exercise_provider.fetch_exercises.return_value = ExerciseFetchResult(
            payloads={
                "a": {"start_time": "2026-08-10T08:00:00"},
                "b": {"start_time": "2026-08-11T08:00:00"},
                "c": {},  # no `start_time` — exercises the fallback-to-`today` branch
            },
            availability=SourceAvailability.AVAILABLE,
            request_count=1,
        )
        mock_exercise_store.known_ids.return_value = frozenset({"b"})
        mock_profile_provider.fetch_profile.return_value = None
        sync_in = ExerciseSyncInputFactory.build()

        report = await use_case.sync(sync_in, today=today)

        assert report.fetched == 2
        assert report.skipped == 1
        assert report.requests == 1
        written_by_id = {call.args[0].id: call.args[0].date for call in mock_exercise_store.write.call_args_list}
        assert written_by_id == {"a": date(2026, 8, 10), "c": today}

    async def test__force_refresh__writes_all_ids_same_provider_call_count(
        self,
        use_case: ExerciseSyncUseCase,
        mock_exercise_provider: mock.AsyncMock,
        mock_profile_provider: mock.AsyncMock,
        mock_exercise_store: mock.AsyncMock,
        today: date,
    ) -> None:
        mock_exercise_provider.fetch_exercises.return_value = ExerciseFetchResult(
            payloads={
                "a": {"start_time": "2026-08-10T08:00:00"},
                "b": {"start_time": "2026-08-11T08:00:00"},
                "c": {"start_time": "2026-08-12T08:00:00"},
            },
            availability=SourceAvailability.AVAILABLE,
            request_count=1,
        )
        mock_exercise_store.known_ids.return_value = frozenset({"b"})
        mock_profile_provider.fetch_profile.return_value = None
        sync_in = ExerciseSyncInputFactory.build(force_refresh=True)

        report = await use_case.sync(sync_in, today=today)

        assert report.fetched == 3
        assert report.skipped == 0
        mock_exercise_store.known_ids.assert_not_awaited()
        mock_exercise_provider.fetch_exercises.assert_awaited_once()
        assert mock_exercise_store.write.call_count == 3

    async def test__write_availability_called_even_when_nothing_new(
        self,
        use_case: ExerciseSyncUseCase,
        mock_exercise_provider: mock.AsyncMock,
        mock_profile_provider: mock.AsyncMock,
        mock_exercise_store: mock.AsyncMock,
        today: date,
    ) -> None:
        mock_exercise_provider.fetch_exercises.return_value = ExerciseFetchResult(
            payloads={}, availability=SourceAvailability.AVAILABLE, request_count=1
        )
        mock_exercise_store.known_ids.return_value = frozenset()
        mock_profile_provider.fetch_profile.return_value = None
        sync_in = ExerciseSyncInputFactory.build()

        report = await use_case.sync(sync_in, today=today)

        assert report.fetched == 0
        mock_exercise_store.write_availability.assert_awaited_once()
        call = mock_exercise_store.write_availability.call_args
        assert call.args == (SourceAvailability.AVAILABLE,)
        assert isinstance(call.kwargs["observed_at"], datetime)

    async def test__profile_fetch_raises__sync_still_succeeds_with_warning(
        self,
        use_case: ExerciseSyncUseCase,
        mock_exercise_provider: mock.AsyncMock,
        mock_profile_provider: mock.AsyncMock,
        mock_exercise_store: mock.AsyncMock,
        mock_profile_store: mock.AsyncMock,
        today: date,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_exercise_provider.fetch_exercises.return_value = ExerciseFetchResult(
            payloads={"a": {"start_time": "2026-08-10T08:00:00"}},
            availability=SourceAvailability.AVAILABLE,
            request_count=1,
        )
        mock_exercise_store.known_ids.return_value = frozenset()
        mock_profile_provider.fetch_profile.side_effect = RuntimeError("boom")

        with caplog.at_level(logging.WARNING):
            report = await use_case.sync(ExerciseSyncInputFactory.build(), today=today)

        assert report.fetched == 1
        assert report.profile_fetched is False
        mock_profile_store.write.assert_not_awaited()
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    async def test__profile_fetch_returns_none__not_fetched(
        self,
        use_case: ExerciseSyncUseCase,
        mock_exercise_provider: mock.AsyncMock,
        mock_profile_provider: mock.AsyncMock,
        mock_exercise_store: mock.AsyncMock,
        mock_profile_store: mock.AsyncMock,
        today: date,
    ) -> None:
        mock_exercise_provider.fetch_exercises.return_value = ExerciseFetchResult(
            payloads={}, availability=SourceAvailability.AVAILABLE, request_count=1
        )
        mock_exercise_store.known_ids.return_value = frozenset()
        mock_profile_provider.fetch_profile.return_value = None

        report = await use_case.sync(ExerciseSyncInputFactory.build(), today=today)

        assert report.profile_fetched is False
        mock_profile_store.write.assert_not_awaited()

    async def test__profile_fetch_succeeds__stored_and_flagged(
        self,
        use_case: ExerciseSyncUseCase,
        mock_exercise_provider: mock.AsyncMock,
        mock_profile_provider: mock.AsyncMock,
        mock_exercise_store: mock.AsyncMock,
        mock_profile_store: mock.AsyncMock,
        today: date,
    ) -> None:
        mock_exercise_provider.fetch_exercises.return_value = ExerciseFetchResult(
            payloads={}, availability=SourceAvailability.AVAILABLE, request_count=1
        )
        mock_exercise_store.known_ids.return_value = frozenset()
        mock_profile_provider.fetch_profile.return_value = {"user-id": "60233839"}

        report = await use_case.sync(ExerciseSyncInputFactory.build(), today=today)

        assert report.profile_fetched is True
        mock_profile_store.write.assert_awaited_once()
        assert mock_profile_store.write.call_args.args[0].payload == {"user-id": "60233839"}
