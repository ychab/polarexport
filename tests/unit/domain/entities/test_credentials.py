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
