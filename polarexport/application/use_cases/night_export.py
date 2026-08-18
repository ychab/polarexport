import logging
from collections.abc import Callable
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from typing import Any
from typing import TypeVar

from polarexport import __project_name__
from polarexport import __version__
from polarexport.application.inputs.night import NightExportInput
from polarexport.application.ports.archivers.night import NightArchiverPort
from polarexport.application.ports.mappers.night import NightMapperPort
from polarexport.application.ports.stores.night import NightStorePort
from polarexport.application.ports.stores.night import StoredPayload
from polarexport.domain.const import POLAR_HISTORY_WINDOW_DAYS
from polarexport.domain.entities.export import ExportManifest
from polarexport.domain.entities.export import ExportReport
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.exceptions import NoNightDataError
from polarexport.domain.services.night_merger import merge_nights
from polarexport.domain.utils.dates import is_outside_history_window

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class NightExportUseCase:
    def __init__(
        self,
        night_store: NightStorePort,
        night_mapper: NightMapperPort,
        night_archiver: NightArchiverPort,
    ) -> None:
        self._night_store = night_store
        self._night_mapper = night_mapper
        self._night_archiver = night_archiver

    async def export(self, night_in: NightExportInput, *, today: date, generated_at: datetime) -> ExportReport:
        stored_by_source: dict[NightSource, Mapping[date, StoredPayload]] = {}
        for source in NightSource:
            if source in night_in.sources:
                stored_by_source[source] = await self._night_store.read(source, night_in.date_range)

        sleeps = self._map_source(NightSource.SLEEP, stored_by_source, self._night_mapper.to_sleep)
        recharges = self._map_source(NightSource.RECHARGE, stored_by_source, self._night_mapper.to_nightly_recharge)
        skin_temperatures = self._map_source(
            NightSource.SKIN_TEMPERATURE, stored_by_source, self._night_mapper.to_skin_temperature
        )
        sleepwises = self._map_source(NightSource.SLEEPWISE, stored_by_source, self._night_mapper.to_sleepwise)
        heart_rates = self._map_source(
            NightSource.HEART_RATE, stored_by_source, self._night_mapper.to_continuous_heart_rate
        )

        nights, gaps = merge_nights(
            night_in.date_range,
            sleeps=sleeps,
            recharges=recharges,
            skin_temperatures=skin_temperatures,
            sleepwises=sleepwises,
            heart_rates=heart_rates,
        )
        if not nights:
            raise NoNightDataError(f"No night data found for {night_in.date_range}")

        if night_in.limit is not None and len(nights) > night_in.limit:
            # Most recent first, mirroring how the sync use case caps its date list.
            nights = nights[-night_in.limit :]
            gaps = tuple(day for day in gaps if day >= nights[0].date)

        history_window_warning: str | None = None
        if is_outside_history_window(night_in.date_range.date_min, today=today):
            history_window_warning = (
                f"date_min ({night_in.date_range.date_min}) is outside the {POLAR_HISTORY_WINDOW_DAYS}-day Polar "
                "retention window; the export reflects only what the local store holds"
            )
            logger.warning(history_window_warning, extra={"date_min": str(night_in.date_range.date_min)})

        sources_requested = tuple(source for source in NightSource if source in night_in.sources)
        mapped_counts: Mapping[NightSource, int] = {
            NightSource.SLEEP: len(sleeps),
            NightSource.RECHARGE: len(recharges),
            NightSource.SKIN_TEMPERATURE: len(skin_temperatures),
            NightSource.SLEEPWISE: len(sleepwises),
            NightSource.HEART_RATE: len(heart_rates),
        }
        manifest = ExportManifest(
            tool_name=__project_name__,
            tool_version=__version__,
            generated_at=generated_at,
            date_range=night_in.date_range,
            sources_requested=sources_requested,
            source_availability={
                source: (SourceAvailability.AVAILABLE if mapped_counts[source] > 0 else SourceAvailability.NO_DATA)
                if source in night_in.sources
                else SourceAvailability.NOT_REQUESTED
                for source in NightSource
            },
            night_count=len(nights),
            gaps=gaps,
            history_window_warning=history_window_warning,
        )

        raw = {
            source: {day: stored.payload for day, stored in stored_payloads.items() if stored.payload is not None}
            for source, stored_payloads in stored_by_source.items()
        }
        archive_path = await self._night_archiver.write(
            nights,
            manifest,
            raw,
            output_dir=night_in.output_dir,
            include_raw=night_in.include_raw,
            force=night_in.force,
        )

        return ExportReport(
            archive_path=archive_path,
            archive_size_bytes=archive_path.stat().st_size,
            manifest=manifest,
            nights=nights,
        )

    def _map_source(
        self,
        source: NightSource,
        stored_by_source: Mapping[NightSource, Mapping[date, StoredPayload]],
        mapper: Callable[[Mapping[str, Any]], _T],
    ) -> dict[date, _T]:
        entities: dict[date, _T] = {}
        for day, stored in stored_by_source.get(source, {}).items():
            if stored.payload is None:
                continue
            try:
                entities[day] = mapper(stored.payload)
            except Exception:
                logger.exception(
                    "Failed to map payload to domain entity", extra={"source": str(source), "date": str(day)}
                )
        return entities
