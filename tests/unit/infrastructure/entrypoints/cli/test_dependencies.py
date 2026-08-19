import logging
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

from polarexport.domain.exceptions import MissingCredentialsError
from polarexport.infrastructure.adapters.archivers.zip import ZipNightArchiver
from polarexport.infrastructure.adapters.providers.polar.auth import PolarOAuthClient
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarNightMapper
from polarexport.infrastructure.adapters.receivers.local_http import LocalHttpCallbackReceiver
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore
from polarexport.infrastructure.adapters.stores.json_credentials import JsonCredentialsStore
from polarexport.infrastructure.config.settings.app import app_settings
from polarexport.infrastructure.config.settings.polar import polar_settings
from polarexport.infrastructure.entrypoints.cli import dependencies as dependencies_module
from polarexport.infrastructure.entrypoints.cli.dependencies import get_auth_callback_receiver
from polarexport.infrastructure.entrypoints.cli.dependencies import get_credentials_store
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_archiver
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_mapper
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_store
from polarexport.infrastructure.entrypoints.cli.dependencies import get_polar_client
from polarexport.infrastructure.entrypoints.cli.dependencies import get_polar_oauth_client

from tests.unit.factories.entities.credentials import StoredCredentialsFactory


class TestGetPolarClient:
    @pytest.fixture(autouse=True)
    def settings_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(polar_settings, "ACCESS_TOKEN", "settings-access-token")
        monkeypatch.setattr(polar_settings, "USER_ID", "settings-user-id")

    async def test__settings_set__wins__no_store_lookup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_store = mock.AsyncMock(spec=JsonCredentialsStore)
        monkeypatch.setattr(dependencies_module, "get_credentials_store", lambda: mock_store)

        async with get_polar_client() as client:
            assert isinstance(client, PolarAccessLinkClient)

        mock_store.read.assert_not_awaited()

    async def test__settings_unset__falls_back_to_credentials_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(polar_settings, "ACCESS_TOKEN", None)
        monkeypatch.setattr(polar_settings, "USER_ID", None)
        mock_store = mock.AsyncMock(spec=JsonCredentialsStore)
        mock_store.read.return_value = StoredCredentialsFactory.build(
            access_token="file-access-token",
            user_id="file-user-id",
            obtained_at=datetime.now(UTC),
            expires_in=473040000,
        )
        monkeypatch.setattr(dependencies_module, "get_credentials_store", lambda: mock_store)

        async with get_polar_client() as client:
            assert isinstance(client, PolarAccessLinkClient)

        mock_store.read.assert_awaited_once_with(app_settings.AUTH_DIR / "credentials.json")

    async def test__neither_settings_nor_store__raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(polar_settings, "ACCESS_TOKEN", None)
        monkeypatch.setattr(polar_settings, "USER_ID", None)
        mock_store = mock.AsyncMock(spec=JsonCredentialsStore)
        mock_store.read.return_value = None
        monkeypatch.setattr(dependencies_module, "get_credentials_store", lambda: mock_store)

        with pytest.raises(MissingCredentialsError, match="polarexport auth"):
            async with get_polar_client():
                pass

    async def test__only_access_token_set__falls_back_to_credentials_store(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(polar_settings, "USER_ID", None)
        mock_store = mock.AsyncMock(spec=JsonCredentialsStore)
        mock_store.read.return_value = StoredCredentialsFactory.build(
            access_token="file-access-token",
            user_id="file-user-id",
            obtained_at=datetime.now(UTC),
            expires_in=473040000,
        )
        monkeypatch.setattr(dependencies_module, "get_credentials_store", lambda: mock_store)

        async with get_polar_client() as client:
            assert isinstance(client, PolarAccessLinkClient)

        mock_store.read.assert_awaited_once()

    async def test__stored_credentials_expired__warns_but_still_returns(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(polar_settings, "ACCESS_TOKEN", None)
        monkeypatch.setattr(polar_settings, "USER_ID", None)
        mock_store = mock.AsyncMock(spec=JsonCredentialsStore)
        mock_store.read.return_value = StoredCredentialsFactory.build(
            access_token="file-access-token",
            user_id="file-user-id",
            obtained_at=datetime(2020, 1, 1, tzinfo=UTC),
            expires_in=1,
        )
        monkeypatch.setattr(dependencies_module, "get_credentials_store", lambda: mock_store)

        with caplog.at_level(logging.WARNING):
            async with get_polar_client() as client:
                assert isinstance(client, PolarAccessLinkClient)

        assert any(record.levelno == logging.WARNING for record in caplog.records)

    async def test__stored_credentials_not_expired__no_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(polar_settings, "ACCESS_TOKEN", None)
        monkeypatch.setattr(polar_settings, "USER_ID", None)
        mock_store = mock.AsyncMock(spec=JsonCredentialsStore)
        mock_store.read.return_value = StoredCredentialsFactory.build(
            access_token="file-access-token",
            user_id="file-user-id",
            obtained_at=datetime.now(UTC),
            expires_in=473040000,
        )
        monkeypatch.setattr(dependencies_module, "get_credentials_store", lambda: mock_store)

        with caplog.at_level(logging.WARNING):
            async with get_polar_client() as client:
                assert isinstance(client, PolarAccessLinkClient)

        assert not any(record.levelno == logging.WARNING for record in caplog.records)


class TestGetNightStore:
    def test__no_legacy_layout__builds_filesystem_store__no_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(app_settings, "DATA_DIR", tmp_path)

        with caplog.at_level(logging.WARNING):
            store = get_night_store()

        assert isinstance(store, FilesystemNightStore)
        assert not any(record.levelno == logging.WARNING for record in caplog.records)

    def test__legacy_layout_present__warns_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(app_settings, "DATA_DIR", tmp_path)
        (tmp_path / "polar-accesslink-v3").mkdir()

        with caplog.at_level(logging.WARNING):
            store = get_night_store()

        assert isinstance(store, FilesystemNightStore)
        warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "pre-0.2 layout" in warnings[0].message


def test__get_night_mapper__builds_polar_mapper() -> None:
    assert isinstance(get_night_mapper(), PolarNightMapper)


def test__get_night_archiver__builds_zip_archiver() -> None:
    assert isinstance(get_night_archiver(), ZipNightArchiver)


def test__get_polar_oauth_client__builds_from_settings() -> None:
    client = get_polar_oauth_client(client_id="a-client-id", client_secret="a-client-secret")

    assert isinstance(client, PolarOAuthClient)


def test__get_auth_callback_receiver__builds_local_http_receiver() -> None:
    assert isinstance(get_auth_callback_receiver("http://localhost:8000/callback"), LocalHttpCallbackReceiver)


def test__get_credentials_store__builds_json_store() -> None:
    assert isinstance(get_credentials_store(), JsonCredentialsStore)
