import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from polarexport.application.ports.stores.profile import ProfileStorePort
from polarexport.application.ports.stores.profile import StoredProfile
from polarexport.domain.const import API_NAME
from polarexport.domain.const import PROFILE_FILENAME

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1


class JsonProfileStore(ProfileStorePort):
    """`ProfileStorePort` implementation backed by a single JSON file at `<data_dir>/<api>/profile.json`.

    Every write is a plain atomic overwrite (temp file in the same directory + `Path.replace()`),
    same mechanism as `FilesystemNightStore` and `JsonCredentialsStore`.
    """

    def __init__(self, data_dir: Path, api: str = API_NAME) -> None:
        self._path = data_dir / api / PROFILE_FILENAME
        self._api = api

    async def write(self, stored: StoredProfile) -> None:
        await asyncio.to_thread(self._write_sync, stored)

    async def read(self) -> StoredProfile | None:
        return await asyncio.to_thread(self._read_sync)

    def _write_sync(self, stored: StoredProfile) -> None:
        envelope: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "api": stored.api,
            "fetched_at": stored.fetched_at.isoformat(),
            "payload": stored.payload,
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, prefix=f".{self._path.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            # 0600: the profile carries the user's birthdate, gender, height and weight, and Polar's
            # payload also includes their real name — the same sensitivity class as
            # credentials.json. Set on the temp file descriptor before any bytes are written, never
            # widened afterwards.
            os.fchmod(fd, 0o600)
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2, ensure_ascii=False)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        tmp_path.replace(self._path)

    def _read_sync(self) -> StoredProfile | None:
        if not self._path.is_file():
            return None

        try:
            envelope: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
            return StoredProfile(
                fetched_at=datetime.fromisoformat(envelope["fetched_at"]),
                api=envelope["api"],
                payload=envelope["payload"],
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            logger.warning("Failed to parse stored profile, skipping", extra={"path": str(self._path)})
            return None
