import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from polarexport.application.ports.stores.credentials import CredentialsStorePort
from polarexport.domain.const import API_NAME
from polarexport.domain.entities.credentials import StoredCredentials
from polarexport.domain.exceptions import CredentialsAlreadyExistError

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1


class JsonCredentialsStore(CredentialsStorePort):
    """`CredentialsStorePort` implementation backed by a single JSON file.

    Unlike a dotenv file, this file holds nothing but Polar credentials, so every write is a plain
    atomic overwrite (temp file in the same directory + `Path.replace()`) rather than line-preserving
    surgery. The parent directory is set mode 0700 and the file mode 0600 on the temp file descriptor
    before any bytes are written — never widened afterwards — since it holds a long-lived bearer token.
    """

    def __init__(self, api: str = API_NAME) -> None:
        self._api = api

    async def write(
        self,
        *,
        access_token: str,
        user_id: str,
        obtained_at: datetime,
        expires_in: int,
        path: Path,
        force: bool,
    ) -> None:
        await asyncio.to_thread(
            self._write_sync,
            access_token=access_token,
            user_id=user_id,
            obtained_at=obtained_at,
            expires_in=expires_in,
            path=path,
            force=force,
        )

    async def read(self, path: Path) -> StoredCredentials | None:
        return await asyncio.to_thread(self._read_sync, path)

    def _write_sync(
        self,
        *,
        access_token: str,
        user_id: str,
        obtained_at: datetime,
        expires_in: int,
        path: Path,
        force: bool,
    ) -> None:
        if not force and path.is_file():
            raise CredentialsAlreadyExistError(
                f"{path} already has credentials. Re-run with --force to overwrite them."
            )

        envelope: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "api": self._api,
            "user_id": user_id,
            "access_token": access_token,
            "obtained_at": obtained_at.isoformat(),
            "expires_in": expires_in,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            os.fchmod(fd, 0o600)
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2, ensure_ascii=False)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        tmp_path.replace(path)

    def _read_sync(self, path: Path) -> StoredCredentials | None:
        if not path.is_file():
            return None

        try:
            envelope: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

            schema_version = envelope["schema_version"]
            if schema_version != _SCHEMA_VERSION:
                logger.warning(
                    f"Unsupported credentials schema_version {schema_version}, skipping",
                    extra={"path": str(path), "schema_version": schema_version},
                )
                return None

            return StoredCredentials(
                user_id=envelope["user_id"],
                access_token=envelope["access_token"],
                api=envelope["api"],
                obtained_at=datetime.fromisoformat(envelope["obtained_at"]),
                expires_in=envelope["expires_in"],
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            logger.warning("Failed to parse stored credentials, skipping", extra={"path": str(path)})
            return None
