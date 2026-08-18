import pytest

from polarexport.infrastructure.config.settings.polar import PolarSettings


class TestPolarSettings:
    def test__defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLAR_ACCESS_TOKEN", "dummy-access-token")
        monkeypatch.setenv("POLAR_USER_ID", "00000000")

        settings = PolarSettings(_env_file=None)

        assert settings.ACCESS_TOKEN == "dummy-access-token"
        assert settings.USER_ID == "00000000"
        assert settings.CLIENT_ID is None
        assert settings.CLIENT_SECRET is None
        assert settings.REDIRECT_URI is None
        assert str(settings.BASE_URL) == "https://www.polaraccesslink.com/"
        assert str(settings.OAUTH_TOKEN_URL) == "https://polarremote.com/v2/oauth2/token"
        assert str(settings.OAUTH_AUTHORIZATION_URL) == "https://flow.polar.com/oauth2/authorization"
        assert settings.HTTP_TIMEOUT == 30.0
        assert settings.HTTP_MAX_RETRIES == 5

    def test__access_token_and_user_id_absent__none_not_a_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # ACCESS_TOKEN/USER_ID are None until `polarexport auth` has run — constructing PolarSettings
        # must succeed on a first-time checkout with no credentials configured yet.
        monkeypatch.delenv("POLAR_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("POLAR_USER_ID", raising=False)

        settings = PolarSettings(_env_file=None)

        assert settings.ACCESS_TOKEN is None
        assert settings.USER_ID is None

    def test__access_token__empty_string__treated_as_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLAR_ACCESS_TOKEN", "")

        settings = PolarSettings(_env_file=None)

        assert settings.ACCESS_TOKEN is None

    def test__client_credentials_are_independent_of_the_token_pair(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLAR_ACCESS_TOKEN", "dummy-access-token")
        monkeypatch.setenv("POLAR_USER_ID", "00000000")
        monkeypatch.setenv("POLAR_CLIENT_ID", "app-client-id")
        monkeypatch.setenv("POLAR_CLIENT_SECRET", "app-client-secret")

        settings = PolarSettings(_env_file=None)

        assert settings.CLIENT_ID == "app-client-id"
        assert settings.CLIENT_ID != settings.USER_ID
        assert settings.CLIENT_SECRET != settings.ACCESS_TOKEN
