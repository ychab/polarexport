import asyncio
import json
import logging
import tempfile
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

from polarexport.application.ports.stores.night import NightStorePort
from polarexport.application.ports.stores.night import StoredPayload
from polarexport.domain.const import API_NAME
from polarexport.domain.enums import NightSource
from polarexport.domain.utils.dates import is_outside_history_window
from polarexport.domain.utils.dates import iterate_dates
from polarexport.domain.value_objects.date_range import DateRange

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1


class FilesystemNightStore(NightStorePort):
    """`NightStorePort` implementation backed by plain JSON files under `data_dir`.

    Layout: `<data_dir>/<api>/<source>/<YYYY>/<MM>/<YYYY-MM-DD>.json`. Every write is atomic
    (temp file + `Path.replace()`) so a killed run never leaves a truncated, unparsable file
    behind — a missing night is recoverable, a corrupt one just sits there confusing `cat`.
    """

    def __init__(self, data_dir: Path, api: str = API_NAME) -> None:
        self._data_dir = data_dir
        self._api = api

    async def write(self, stored: StoredPayload) -> None:
        await asyncio.to_thread(self._write_sync, stored)

    async def read(self, source: NightSource, date_range: DateRange) -> Mapping[date, StoredPayload]:
        return await asyncio.to_thread(self._read_many_sync, source, iterate_dates(date_range))

    async def missing(self, source: NightSource, dates: Sequence[date], *, today: date) -> tuple[date, ...]:
        stored = await asyncio.to_thread(self._read_many_sync, source, dates)
        return tuple(
            day
            for day in dates
            if day not in stored or (stored[day].payload is None and not is_outside_history_window(day, today=today))
        )

    def _path_for(self, source: NightSource, day: date) -> Path:
        return (
            self._data_dir
            / self._api
            / source.value
            / day.strftime("%Y")
            / day.strftime("%m")
            / f"{day.isoformat()}.json"
        )

    def _write_sync(self, stored: StoredPayload) -> None:
        if stored.api != self._api:
            raise ValueError(f"StoredPayload.api {stored.api!r} does not match store api {self._api!r}")

        path = self._path_for(stored.source, stored.date)
        path.parent.mkdir(parents=True, exist_ok=True)

        envelope: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "api": stored.api,
            "source": stored.source.value,
            "date": stored.date.isoformat(),
            "fetched_at": stored.fetched_at.isoformat(),
            "payload": stored.payload,
        }

        # pathlib is synchronous while the port is async — offloaded to a thread by the callers above.
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2, ensure_ascii=False)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        tmp_path.replace(path)

    def _read_many_sync(self, source: NightSource, dates: Iterable[date]) -> dict[date, StoredPayload]:
        result: dict[date, StoredPayload] = {}
        for day in dates:
            stored = self._read_one_sync(source, day)
            if stored is not None:
                result[day] = stored
        return result

    def _read_one_sync(self, source: NightSource, day: date) -> StoredPayload | None:
        path = self._path_for(source, day)
        if not path.is_file():
            return None

        try:
            envelope: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Failed to parse stored night payload, skipping", extra={"path": str(path)})
            return None

        return StoredPayload(
            source=source,
            date=date.fromisoformat(envelope["date"]),
            fetched_at=datetime.fromisoformat(envelope["fetched_at"]),
            api=envelope["api"],
            payload=envelope["payload"],
        )
