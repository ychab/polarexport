import logging
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

from polarexport.application.inputs.exercise import ExerciseSyncInput
from polarexport.application.ports.providers.exercise import ExerciseProviderPort
from polarexport.application.ports.providers.profile import ProfileProviderPort
from polarexport.application.ports.stores.exercise import ExerciseStorePort
from polarexport.application.ports.stores.exercise import StoredExercise
from polarexport.application.ports.stores.profile import ProfileStorePort
from polarexport.application.ports.stores.profile import StoredProfile
from polarexport.domain.const import API_NAME
from polarexport.domain.entities.exercise_export import ExerciseSyncReport

logger = logging.getLogger(__name__)


class ExerciseSyncUseCase:
    def __init__(
        self,
        exercise_provider: ExerciseProviderPort,
        profile_provider: ProfileProviderPort,
        exercise_store: ExerciseStorePort,
        profile_store: ProfileStorePort,
    ) -> None:
        self._exercise_provider = exercise_provider
        self._profile_provider = profile_provider
        self._exercise_store = exercise_store
        self._profile_store = profile_store

    async def sync(self, sync_in: ExerciseSyncInput, *, today: date) -> ExerciseSyncReport:
        result = await self._exercise_provider.fetch_exercises(
            with_samples=sync_in.with_samples, with_zones=sync_in.with_zones
        )
        await self._exercise_store.write_availability(result.availability, observed_at=datetime.now(UTC))

        # `--force-refresh` does not save or cost a single request — the fetch above is the same
        # either way. Treating `known` as empty only decides whether already-stored ids get rewritten.
        known = frozenset[str]() if sync_in.force_refresh else await self._exercise_store.known_ids()

        fetched = skipped = 0
        for exercise_id, payload in result.payloads.items():
            if exercise_id in known:
                skipped += 1
                continue
            await self._exercise_store.write(
                StoredExercise(
                    id=exercise_id,
                    date=self._stored_date(payload, today=today),
                    fetched_at=datetime.now(UTC),
                    api=API_NAME,
                    payload=payload,
                )
            )
            fetched += 1

        profile_fetched = await self._sync_profile()

        return ExerciseSyncReport(
            fetched=fetched,
            skipped=skipped,
            requests=result.request_count,
            availability=result.availability,
            profile_fetched=profile_fetched,
        )

    def _stored_date(self, payload: dict[str, Any], *, today: date) -> date:
        # A plain ISO-date parse of `start_time` — this only needs to pick a stable on-disk partition
        # key, not the offset-aware calendar date the mapper computes at export time.
        try:
            return date.fromisoformat(str(payload["start_time"])[:10])
        except (KeyError, ValueError):
            return today

    async def _sync_profile(self) -> bool:
        try:
            payload = await self._profile_provider.fetch_profile()
        except Exception:
            # A profile failure must not fail the sync: sessions are the point, the profile is context.
            logger.warning("Failed to fetch Polar profile")
            return False

        if payload is None:
            return False

        await self._profile_store.write(StoredProfile(fetched_at=datetime.now(UTC), api=API_NAME, payload=payload))
        return True
