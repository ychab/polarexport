from polarexport.infrastructure.adapters.archivers.zip import ZipNightArchiver
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarNightMapper
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_archiver
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_mapper
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_store
from polarexport.infrastructure.entrypoints.cli.dependencies import get_polar_client


class TestDependencies:
    async def test__get_polar_client__builds_from_settings(self) -> None:
        async with get_polar_client() as client:
            assert isinstance(client, PolarAccessLinkClient)

    def test__get_night_store__builds_filesystem_store(self) -> None:
        assert isinstance(get_night_store(), FilesystemNightStore)

    def test__get_night_mapper__builds_polar_mapper(self) -> None:
        assert isinstance(get_night_mapper(), PolarNightMapper)

    def test__get_night_archiver__builds_zip_archiver(self) -> None:
        assert isinstance(get_night_archiver(), ZipNightArchiver)
