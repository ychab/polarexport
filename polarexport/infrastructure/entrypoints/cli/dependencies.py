from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from polarexport.domain.exceptions import MissingCredentialsError
from polarexport.infrastructure.adapters.archivers.zip import ZipNightArchiver
from polarexport.infrastructure.adapters.providers.polar.auth import PolarOAuthClient
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarNightMapper
from polarexport.infrastructure.adapters.receivers.local_http import LocalHttpCallbackReceiver
from polarexport.infrastructure.adapters.stores.dotenv import DotenvCredentialsStore
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore
from polarexport.infrastructure.config.settings.app import app_settings
from polarexport.infrastructure.config.settings.polar import polar_settings


@asynccontextmanager
async def get_polar_client() -> AsyncIterator[PolarAccessLinkClient]:
    if polar_settings.ACCESS_TOKEN is None:
        raise MissingCredentialsError("POLAR_ACCESS_TOKEN is not set.")
    if polar_settings.USER_ID is None:
        raise MissingCredentialsError("POLAR_USER_ID is not set.")

    async with PolarAccessLinkClient(
        access_token=polar_settings.ACCESS_TOKEN,
        user_id=polar_settings.USER_ID,
        base_url=polar_settings.BASE_URL,
        timeout=polar_settings.HTTP_TIMEOUT,
        concurrency=app_settings.EXPORT_CONCURRENCY,
        max_retries=polar_settings.HTTP_MAX_RETRIES,
    ) as client:
        yield client


def get_night_store() -> FilesystemNightStore:
    return FilesystemNightStore(data_dir=app_settings.DATA_DIR)


def get_night_mapper() -> PolarNightMapper:
    return PolarNightMapper()


def get_night_archiver() -> ZipNightArchiver:
    return ZipNightArchiver()


def get_polar_oauth_client(client_id: str, client_secret: str) -> PolarOAuthClient:
    return PolarOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        authorization_url=polar_settings.OAUTH_AUTHORIZATION_URL,
        token_url=polar_settings.OAUTH_TOKEN_URL,
        registration_base_url=polar_settings.BASE_URL,
        timeout=polar_settings.HTTP_TIMEOUT,
        max_retries=polar_settings.HTTP_MAX_RETRIES,
    )


def get_auth_callback_receiver(redirect_uri: str) -> LocalHttpCallbackReceiver:
    return LocalHttpCallbackReceiver(redirect_uri=redirect_uri)


def get_credentials_store() -> DotenvCredentialsStore:
    return DotenvCredentialsStore()
