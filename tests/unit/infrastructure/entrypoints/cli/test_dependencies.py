import pytest

from polarexport.domain.exceptions import MissingCredentialsError
from polarexport.infrastructure.adapters.archivers.zip import ZipNightArchiver
from polarexport.infrastructure.adapters.providers.polar.auth import PolarOAuthClient
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarNightMapper
from polarexport.infrastructure.adapters.receivers.local_http import LocalHttpCallbackReceiver
from polarexport.infrastructure.adapters.stores.dotenv import DotenvCredentialsStore
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore
from polarexport.infrastructure.config.settings.polar import polar_settings
from polarexport.infrastructure.entrypoints.cli.dependencies import get_auth_callback_receiver
from polarexport.infrastructure.entrypoints.cli.dependencies import get_credentials_store
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_archiver
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_mapper
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_store
from polarexport.infrastructure.entrypoints.cli.dependencies import get_polar_client
from polarexport.infrastructure.entrypoints.cli.dependencies import get_polar_oauth_client


class TestDependencies:
    async def test__get_polar_client__builds_from_settings(self) -> None:
        async with get_polar_client() as client:
            assert isinstance(client, PolarAccessLinkClient)

    async def test__get_polar_client__access_token_missing__raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(polar_settings, "ACCESS_TOKEN", None)

        with pytest.raises(MissingCredentialsError):
            async with get_polar_client():
                pass

    async def test__get_polar_client__user_id_missing__raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(polar_settings, "USER_ID", None)

        with pytest.raises(MissingCredentialsError):
            async with get_polar_client():
                pass

    def test__get_night_store__builds_filesystem_store(self) -> None:
        assert isinstance(get_night_store(), FilesystemNightStore)

    def test__get_night_mapper__builds_polar_mapper(self) -> None:
        assert isinstance(get_night_mapper(), PolarNightMapper)

    def test__get_night_archiver__builds_zip_archiver(self) -> None:
        assert isinstance(get_night_archiver(), ZipNightArchiver)

    def test__get_polar_oauth_client__builds_from_settings(self) -> None:
        client = get_polar_oauth_client(client_id="a-client-id", client_secret="a-client-secret")

        assert isinstance(client, PolarOAuthClient)

    def test__get_auth_callback_receiver__builds_local_http_receiver(self) -> None:
        assert isinstance(get_auth_callback_receiver("http://localhost:8000/callback"), LocalHttpCallbackReceiver)

    def test__get_credentials_store__builds_dotenv_store(self) -> None:
        assert isinstance(get_credentials_store(), DotenvCredentialsStore)
