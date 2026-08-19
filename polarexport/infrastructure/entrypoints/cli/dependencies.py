import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import datetime

from polarexport.domain.const import API_NAME
from polarexport.domain.const import CREDENTIALS_FILENAME
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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_polar_client() -> AsyncIterator[PolarAccessLinkClient]:
    access_token, user_id = await _resolve_credentials()

    async with PolarAccessLinkClient(
        access_token=access_token,
        user_id=user_id,
        base_url=polar_settings.BASE_URL,
        timeout=polar_settings.HTTP_TIMEOUT,
        concurrency=app_settings.EXPORT_CONCURRENCY,
        max_retries=polar_settings.HTTP_MAX_RETRIES,
    ) as client:
        yield client


async def _resolve_credentials() -> tuple[str, str]:
    if polar_settings.ACCESS_TOKEN is not None and polar_settings.USER_ID is not None:
        logger.debug("Resolved Polar credentials", extra={"source": "settings"})
        return polar_settings.ACCESS_TOKEN, polar_settings.USER_ID

    stored = await get_credentials_store().read(app_settings.AUTH_DIR / CREDENTIALS_FILENAME)
    if stored is not None:
        logger.debug("Resolved Polar credentials", extra={"source": "credentials file"})
        if stored.is_expired(now=datetime.now(UTC)):
            logger.warning(
                "Stored Polar token is past its expiry; continuing anyway", extra={"user_id": stored.user_id}
            )
        return stored.access_token, stored.user_id

    raise MissingCredentialsError("No Polar credentials found. Run `polarexport auth` first.")


def get_night_store() -> FilesystemNightStore:
    legacy_path = app_settings.DATA_DIR / API_NAME
    if legacy_path.is_dir():
        logger.warning(
            f"{legacy_path} is the pre-0.2 layout. Move it with:\n"
            f"  mkdir -p data/raw && mv data/{API_NAME} data/raw/\n"
            "  mkdir -p data/export && mv export/*.zip data/export/",
            extra={"path": str(legacy_path)},
        )
    return FilesystemNightStore(data_dir=app_settings.RAW_DIR)


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


def get_credentials_store() -> JsonCredentialsStore:
    return JsonCredentialsStore()
