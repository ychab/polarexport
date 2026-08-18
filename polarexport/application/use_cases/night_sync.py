import logging
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Final

from polarexport.application.inputs.night import NightSyncInput
from polarexport.application.ports.providers.night import NightProviderPort
from polarexport.application.ports.stores.night import NightStorePort
from polarexport.application.ports.stores.night import StoredPayload
from polarexport.domain.const import POLAR_HISTORY_WINDOW_DAYS
from polarexport.domain.entities.sync import SourceSyncStat
from polarexport.domain.entities.sync import SyncReport
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.utils.dates import is_outside_history_window
from polarexport.domain.utils.dates import iterate_dates

logger = logging.getLogger(__name__)

_POLAR_API_NAME: Final[str] = "polar-accesslink-v3"


class NightSyncUseCase:
    def __init__(self, night_provider: NightProviderPort, night_store: NightStorePort) -> None:
        self._night_provider = night_provider
        self._night_store = night_store

    async def sync(self, sync_in: NightSyncInput, *, today: date) -> SyncReport:
        dates = tuple(iterate_dates(sync_in.date_range))
        if sync_in.limit is not None:
            dates = dates[-sync_in.limit :]

        history_window_warning: str | None = None
        if is_outside_history_window(sync_in.date_range.date_min, today=today):
            history_window_warning = (
                f"date_min ({sync_in.date_range.date_min}) is outside the {POLAR_HISTORY_WINDOW_DAYS}-day Polar "
                "retention window; serving what the local store already holds"
            )
            logger.warning(history_window_warning, extra={"date_min": str(sync_in.date_range.date_min)})

        stats: dict[NightSource, SourceSyncStat] = {}
        for source in NightSource:
            if source not in sync_in.sources:
                continue
            stats[source] = await self._sync_source(source, dates, force_refresh=sync_in.force_refresh, today=today)

        return SyncReport(date_range=sync_in.date_range, stats=stats, history_window_warning=history_window_warning)

    async def _sync_source(
        self,
        source: NightSource,
        dates: tuple[date, ...],
        *,
        force_refresh: bool,
        today: date,
    ) -> SourceSyncStat:
        if force_refresh:
            missing = dates
        else:
            missing = await self._night_store.missing(source, dates, today=today)
        skipped = len(dates) - len(missing)

        if not missing:
            return SourceSyncStat(
                availability=SourceAvailability.AVAILABLE, fetched=0, skipped=skipped, empty=0, requests=0
            )

        result = await self._night_provider.fetch(source, missing)

        fetched = empty = 0
        for day, payload in result.payloads.items():
            await self._night_store.write(
                StoredPayload(
                    source=source,
                    date=day,
                    fetched_at=datetime.now(UTC),
                    api=_POLAR_API_NAME,
                    payload=payload,
                )
            )
            if payload is None:
                empty += 1
            else:
                fetched += 1

        return SourceSyncStat(
            availability=result.availability,
            fetched=fetched,
            skipped=skipped,
            empty=empty,
            requests=result.request_count,
        )
