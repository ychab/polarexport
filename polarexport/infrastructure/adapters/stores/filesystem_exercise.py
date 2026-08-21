import asyncio
import json
import logging
import tempfile
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

from polarexport.application.ports.stores.exercise import ExerciseStorePort
from polarexport.application.ports.stores.exercise import StoredExercise
from polarexport.domain.const import API_NAME
from polarexport.domain.const import EXERCISE_DIR_NAME
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.utils.dates import iterate_dates
from polarexport.domain.value_objects.date_range import DateRange

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_STATUS_FILENAME = "_status.json"


class FilesystemExerciseStore(ExerciseStorePort):
    """`ExerciseStorePort` implementation backed by plain JSON files under `data_dir`.

    Layout: `<data_dir>/<api>/exercise/<YYYY>/<MM>/<YYYY-MM-DD>-<id>.json`. Unlike
    `FilesystemNightStore`, the date alone cannot be the filename: a day can hold several sessions,
    so the id is appended. Every write is atomic (temp file + `Path.replace()`), same as the night
    store.

    There is no `payload: null` case here. For nights, a null payload records "Polar was asked about
    this date and had nothing", which is what stops endless re-fetching. Exercises have no per-date
    question to ask — an id exists only because Polar returned a session in the first place — so a
    stored record always carries a payload, and `known_ids()` is what stops re-fetching instead.
    """

    def __init__(self, data_dir: Path, api: str = API_NAME) -> None:
        self._data_dir = data_dir
        self._api = api

    async def write(self, stored: StoredExercise) -> None:
        await asyncio.to_thread(self._write_sync, stored)

    async def read(self, date_range: DateRange) -> Mapping[str, StoredExercise]:
        return await asyncio.to_thread(self._read_range_sync, date_range)

    async def known_ids(self) -> frozenset[str]:
        return await asyncio.to_thread(self._known_ids_sync)

    async def write_availability(self, availability: SourceAvailability, *, observed_at: datetime) -> None:
        await asyncio.to_thread(self._write_availability_sync, availability, observed_at)

    async def read_availability(self) -> SourceAvailability | None:
        return await asyncio.to_thread(self._read_availability_sync)

    def _root(self) -> Path:
        return self._data_dir / self._api / EXERCISE_DIR_NAME

    def _status_path(self) -> Path:
        return self._root() / _STATUS_FILENAME

    def _month_dir(self, day: date) -> Path:
        return self._root() / day.strftime("%Y") / day.strftime("%m")

    def _path_for(self, day: date, exercise_id: str) -> Path:
        return self._month_dir(day) / f"{day.isoformat()}-{exercise_id}.json"

    def _write_sync(self, stored: StoredExercise) -> None:
        if stored.api != self._api:
            raise ValueError(f"StoredExercise.api {stored.api!r} does not match store api {self._api!r}")

        envelope: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "api": stored.api,
            "id": stored.id,
            "date": stored.date.isoformat(),
            "fetched_at": stored.fetched_at.isoformat(),
            "payload": stored.payload,
        }
        self._write_json_atomic_sync(self._path_for(stored.date, stored.id), envelope)

    def _write_availability_sync(self, availability: SourceAvailability, observed_at: datetime) -> None:
        envelope: dict[str, Any] = {
            "availability": availability.value,
            "observed_at": observed_at.isoformat(),
        }
        self._write_json_atomic_sync(self._status_path(), envelope)

    def _write_json_atomic_sync(self, path: Path, envelope: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

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

    def _read_range_sync(self, date_range: DateRange) -> dict[str, StoredExercise]:
        months = {(day.year, day.month) for day in iterate_dates(date_range)}
        result: dict[str, StoredExercise] = {}
        for year, month in months:
            month_dir = self._root() / f"{year:04d}" / f"{month:02d}"
            if not month_dir.is_dir():
                continue
            for path in sorted(month_dir.glob("*.json")):
                stored = self._read_file_sync(path)
                if stored is not None and date_range.date_min <= stored.date <= date_range.date_max:
                    result[stored.id] = stored
        return result

    def _read_file_sync(self, path: Path) -> StoredExercise | None:
        try:
            envelope: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return StoredExercise(
                id=envelope["id"],
                date=date.fromisoformat(envelope["date"]),
                fetched_at=datetime.fromisoformat(envelope["fetched_at"]),
                api=envelope["api"],
                payload=envelope["payload"],
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            logger.warning("Failed to parse stored exercise payload, skipping", extra={"path": str(path)})
            return None

    def _known_ids_sync(self) -> frozenset[str]:
        root = self._root()
        if not root.is_dir():
            return frozenset()
        # Ids come from the filename, not from parsing every file: an id is the segment after the
        # first three `-`-separated date parts. Polar ids are alphanumeric and contain no `-`
        # themselves, but `maxsplit=3` keeps the id intact as one token even if that ever changes.
        return frozenset(path.stem.split("-", 3)[3] for path in root.rglob("*.json") if path.name != _STATUS_FILENAME)

    def _read_availability_sync(self) -> SourceAvailability | None:
        path = self._status_path()
        if not path.is_file():
            return None

        try:
            envelope: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Failed to parse stored exercise availability, skipping", extra={"path": str(path)})
            return None

        return SourceAvailability(envelope["availability"])
