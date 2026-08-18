from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from polarexport.infrastructure.adapters.archivers.zip import ZipNightArchiver
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarNightMapper
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore
from polarexport.infrastructure.config.settings.app import app_settings
from polarexport.infrastructure.config.settings.polar import polar_settings


@asynccontextmanager
async def get_polar_client() -> AsyncIterator[PolarAccessLinkClient]:
    async with PolarAccessLinkClient(
        access_token=polar_settings.ACCESS_TOKEN,
        user_id=polar_settings.USER_ID,
        base_url=polar_settings.BASE_URL,
        timeout=polar_settings.HTTP_TIMEOUT,
        concurrency=app_settings.EXPORT_CONCURRENCY,
    ) as client:
        yield client


def get_night_store() -> FilesystemNightStore:
    return FilesystemNightStore(data_dir=app_settings.DATA_DIR)


def get_night_mapper() -> PolarNightMapper:
    return PolarNightMapper()


def get_night_archiver() -> ZipNightArchiver:
    return ZipNightArchiver()
