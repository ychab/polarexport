import asyncio
import os
import tempfile
from pathlib import Path
from typing import Final

from polarexport.application.ports.stores.credentials import CredentialsStorePort
from polarexport.domain.exceptions import CredentialsAlreadyExistError

_ACCESS_TOKEN_KEY: Final[str] = "POLAR_ACCESS_TOKEN"
_USER_ID_KEY: Final[str] = "POLAR_USER_ID"


class DotenvCredentialsStore(CredentialsStorePort):
    """`CredentialsStorePort` implementation backed by a dotenv-style file.

    Preserves every other line — comments, ordering, unrelated keys — rewriting only the two Polar
    token keys, appending them if absent. Creates the file if missing. Every write is atomic (temp
    file in the same directory + `Path.replace()`), consistent with `FilesystemNightStore`, and the
    temp file is created 0600 from the start rather than widened afterwards, since it holds a
    long-lived bearer token.
    """

    async def write(self, *, access_token: str, user_id: str, env_path: Path, force: bool) -> None:
        await asyncio.to_thread(
            self._write_sync, access_token=access_token, user_id=user_id, env_path=env_path, force=force
        )

    def _write_sync(self, *, access_token: str, user_id: str, env_path: Path, force: bool) -> None:
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []

        existing_keys = {self._key_of(line) for line in lines}
        if not force and _ACCESS_TOKEN_KEY in existing_keys:
            raise CredentialsAlreadyExistError(
                f"{env_path} already has {_ACCESS_TOKEN_KEY} set. Re-run with --force to overwrite it."
            )

        updated = self._set_or_append(lines, _ACCESS_TOKEN_KEY, access_token)
        updated = self._set_or_append(updated, _USER_ID_KEY, user_id)

        env_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=env_path.parent, prefix=f".{env_path.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            os.fchmod(fd, 0o600)
            with open(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(updated) + "\n")
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        tmp_path.replace(env_path)

    @staticmethod
    def _key_of(line: str) -> str | None:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            return None
        return stripped.split("=", 1)[0].strip()

    @classmethod
    def _set_or_append(cls, lines: list[str], key: str, value: str) -> list[str]:
        new_line = f"{key}={value}"
        for i, line in enumerate(lines):
            if cls._key_of(line) == key:
                updated = list(lines)
                updated[i] = new_line
                return updated
        return [*lines, new_line]
