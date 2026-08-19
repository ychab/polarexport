from datetime import UTC
from datetime import datetime
from datetime import timedelta

from tests.unit.factories.entities.credentials import StoredCredentialsFactory


class TestStoredCredentials:
    def test__fields(self) -> None:
        credentials = StoredCredentialsFactory.build(
            user_id="12345678", api="polar-accesslink-v3", expires_in=473040000
        )

        assert credentials.user_id == "12345678"
        assert credentials.api == "polar-accesslink-v3"
        assert credentials.expires_in == 473040000

    def test__repr__redacts_access_token(self) -> None:
        credentials = StoredCredentialsFactory.build(access_token="tok-must-never-be-logged", user_id="12345678")

        rendered = repr(credentials)

        assert "***" in rendered
        assert "tok-must-never-be-logged" not in rendered
        assert "12345678" in rendered

    def test__is_expired__before_boundary__false(self) -> None:
        obtained_at = datetime(2026, 8, 18, tzinfo=UTC)
        credentials = StoredCredentialsFactory.build(obtained_at=obtained_at, expires_in=100)

        assert credentials.is_expired(now=obtained_at + timedelta(seconds=99)) is False

    def test__is_expired__at_boundary__true(self) -> None:
        obtained_at = datetime(2026, 8, 18, tzinfo=UTC)
        credentials = StoredCredentialsFactory.build(obtained_at=obtained_at, expires_in=100)

        assert credentials.is_expired(now=obtained_at + timedelta(seconds=100)) is True

    def test__is_expired__after_boundary__true(self) -> None:
        obtained_at = datetime(2026, 8, 18, tzinfo=UTC)
        credentials = StoredCredentialsFactory.build(obtained_at=obtained_at, expires_in=100)

        assert credentials.is_expired(now=obtained_at + timedelta(seconds=101)) is True
