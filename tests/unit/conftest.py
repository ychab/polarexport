from unittest import mock

import pytest

from polarexport.application.ports.archivers.night import NightArchiverPort
from polarexport.application.ports.mappers.night import NightMapperPort
from polarexport.application.ports.providers.auth import AuthProviderPort
from polarexport.application.ports.providers.night import NightProviderPort
from polarexport.application.ports.receivers.callback import AuthCallbackReceiverPort
from polarexport.application.ports.stores.credentials import CredentialsStorePort
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


@pytest.fixture
def mock_auth_provider() -> mock.Mock:
    # Mock (not AsyncMock): `authorization_url` is sync while the other two methods are async, and
    # `spec=` auto-detects the right mock type per method — an AsyncMock() top-level would wrongly
    # make `authorization_url` a coroutine too.
    return mock.Mock(spec=AuthProviderPort)


@pytest.fixture
def mock_auth_callback_receiver() -> mock.AsyncMock:
    return mock.AsyncMock(spec=AuthCallbackReceiverPort)


@pytest.fixture
def mock_credentials_store() -> mock.AsyncMock:
    return mock.AsyncMock(spec=CredentialsStorePort)
