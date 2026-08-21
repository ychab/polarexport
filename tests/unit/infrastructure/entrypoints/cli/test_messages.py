from collections.abc import Iterable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from unittest import mock

import pytest

from polarexport.infrastructure.entrypoints.cli.messages import unauthorized_message

from tests.unit.factories.entities.credentials import StoredCredentialsFactory


class TestUnauthorizedMessage:
    @pytest.fixture
    def mock_credentials_store(self) -> Iterable[mock.Mock]:
        store = mock.Mock()
        store.read = mock.AsyncMock(return_value=None)
        yield store

    def test__no_stored_credentials__generic_message(self, mock_credentials_store: mock.Mock) -> None:
        message = unauthorized_message(lambda: mock_credentials_store)

        assert "Authentication failed (401" in message
        assert "polarexport auth" in message

    def test__stored_credentials_not_expired__generic_message(self, mock_credentials_store: mock.Mock) -> None:
        mock_credentials_store.read.return_value = StoredCredentialsFactory.build(
            obtained_at=datetime.now(UTC), expires_in=473040000
        )

        message = unauthorized_message(lambda: mock_credentials_store)

        assert "Authentication failed (401" in message
        assert "expired" not in message

    def test__stored_credentials_expired__names_expiry_and_auth_command(
        self, mock_credentials_store: mock.Mock
    ) -> None:
        obtained_at = datetime.now(UTC) - timedelta(days=1000)
        mock_credentials_store.read.return_value = StoredCredentialsFactory.build(
            obtained_at=obtained_at, expires_in=100
        )

        message = unauthorized_message(lambda: mock_credentials_store)

        assert "Your Polar token expired on" in message
        assert "polarexport auth" in message
        assert "Authentication failed (401" not in message
