import json
import logging
import stat
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest

from polarexport.domain.exceptions import CredentialsAlreadyExistError
from polarexport.infrastructure.adapters.stores.json_credentials import JsonCredentialsStore


class TestJsonCredentialsStore:
    @pytest.fixture
    def store(self) -> JsonCredentialsStore:
        return JsonCredentialsStore()

    @pytest.fixture
    def credentials_path(self, tmp_path: Path) -> Path:
        return tmp_path / "auth" / "credentials.json"

    @pytest.fixture
    def obtained_at(self) -> datetime:
        return datetime(2026, 8, 18, 16, 42, 5, 123456, tzinfo=UTC)

    async def test__write_then_read__round_trips(
        self, store: JsonCredentialsStore, credentials_path: Path, obtained_at: datetime
    ) -> None:
        await store.write(
            access_token="tok",
            user_id="123",
            obtained_at=obtained_at,
            expires_in=473040000,
            path=credentials_path,
            force=False,
        )

        result = await store.read(credentials_path)

        assert result is not None
        assert result.access_token == "tok"
        assert result.user_id == "123"
        assert result.api == "polar-accesslink-v3"
        assert result.obtained_at == obtained_at
        assert result.expires_in == 473040000

    async def test__read__missing_file__returns_none(
        self, store: JsonCredentialsStore, credentials_path: Path
    ) -> None:
        result = await store.read(credentials_path)

        assert result is None

    async def test__read__corrupt_file__logs_warning_and_returns_none(
        self, store: JsonCredentialsStore, credentials_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        credentials_path.parent.mkdir(parents=True)
        credentials_path.write_text("not valid json {", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = await store.read(credentials_path)

        assert result is None
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    async def test__existing_credentials__no_force__refuses(
        self, store: JsonCredentialsStore, credentials_path: Path, obtained_at: datetime
    ) -> None:
        await store.write(
            access_token="old-token",
            user_id="old-id",
            obtained_at=obtained_at,
            expires_in=100,
            path=credentials_path,
            force=False,
        )

        with pytest.raises(CredentialsAlreadyExistError, match="--force"):
            await store.write(
                access_token="new-token",
                user_id="new-id",
                obtained_at=obtained_at,
                expires_in=200,
                path=credentials_path,
                force=False,
            )

        result = json.loads(credentials_path.read_text(encoding="utf-8"))
        assert result["access_token"] == "old-token"

    async def test__existing_credentials__force__overwrites(
        self, store: JsonCredentialsStore, credentials_path: Path, obtained_at: datetime
    ) -> None:
        await store.write(
            access_token="old-token",
            user_id="old-id",
            obtained_at=obtained_at,
            expires_in=100,
            path=credentials_path,
            force=False,
        )

        await store.write(
            access_token="new-token",
            user_id="new-id",
            obtained_at=obtained_at,
            expires_in=200,
            path=credentials_path,
            force=True,
        )

        result = json.loads(credentials_path.read_text(encoding="utf-8"))
        assert result["access_token"] == "new-token"
        assert result["user_id"] == "new-id"

    async def test__result_file_mode_is_0600__and_parent_dir_is_0700(
        self, store: JsonCredentialsStore, credentials_path: Path, obtained_at: datetime
    ) -> None:
        await store.write(
            access_token="tok",
            user_id="123",
            obtained_at=obtained_at,
            expires_in=100,
            path=credentials_path,
            force=False,
        )

        assert stat.S_IMODE(credentials_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(credentials_path.parent.stat().st_mode) == 0o700

    async def test__creates_missing_parent_directories(
        self, store: JsonCredentialsStore, tmp_path: Path, obtained_at: datetime
    ) -> None:
        nested_path = tmp_path / "nested" / "auth" / "credentials.json"

        await store.write(
            access_token="tok",
            user_id="123",
            obtained_at=obtained_at,
            expires_in=100,
            path=nested_path,
            force=False,
        )

        assert nested_path.is_file()

    async def test__write_is_atomic__no_leftover_temp_files(
        self, store: JsonCredentialsStore, credentials_path: Path, obtained_at: datetime
    ) -> None:
        await store.write(
            access_token="tok",
            user_id="123",
            obtained_at=obtained_at,
            expires_in=100,
            path=credentials_path,
            force=False,
        )

        assert list(credentials_path.parent.iterdir()) == [credentials_path]

    async def test__write_fails__temp_file_is_cleaned_up(
        self,
        store: JsonCredentialsStore,
        credentials_path: Path,
        obtained_at: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _raise(*args: object, **kwargs: object) -> None:
            raise ValueError("boom")

        monkeypatch.setattr("polarexport.infrastructure.adapters.stores.json_credentials.os.fchmod", _raise)

        with pytest.raises(ValueError, match="boom"):
            await store.write(
                access_token="tok",
                user_id="123",
                obtained_at=obtained_at,
                expires_in=100,
                path=credentials_path,
                force=False,
            )

        assert list(credentials_path.parent.iterdir()) == []
