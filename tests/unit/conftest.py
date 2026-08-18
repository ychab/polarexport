from unittest import mock

import pytest

from polarexport.application.ports.archivers.night import NightArchiverPort
from polarexport.application.ports.mappers.night import NightMapperPort
from polarexport.application.ports.providers.night import NightProviderPort
from polarexport.application.ports.stores.night import NightStorePort

# --- Port Mocks ---


@pytest.fixture
def mock_night_provider() -> mock.AsyncMock:
    return mock.AsyncMock(spec=NightProviderPort)


@pytest.fixture
def mock_night_store() -> mock.AsyncMock:
    return mock.AsyncMock(spec=NightStorePort)


@pytest.fixture
def mock_night_mapper() -> mock.Mock:
    return mock.Mock(spec=NightMapperPort)


@pytest.fixture
def mock_night_archiver() -> mock.AsyncMock:
    return mock.AsyncMock(spec=NightArchiverPort)
