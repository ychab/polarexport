from pydantic import ValidationError

import pytest

from polarexport.infrastructure.config.settings.polar import PolarSettings


class TestPolarSettings:
    def test__defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # ACCESS_TOKEN/USER_ID have no default — they are required. Everything else must fall back.
        monkeypatch.setenv("POLAR_ACCESS_TOKEN", "dummy-access-token")
        monkeypatch.setenv("POLAR_USER_ID", "00000000")

        settings = PolarSettings(_env_file=None)

        assert settings.ACCESS_TOKEN == "dummy-access-token"
        assert settings.USER_ID == "00000000"
        assert settings.CLIENT_ID is None
        assert settings.CLIENT_SECRET is None
        assert settings.REDIRECT_URI is None
        assert str(settings.BASE_URL) == "https://www.polaraccesslink.com/"
        assert settings.HTTP_TIMEOUT == 30.0
        assert settings.HTTP_MAX_RETRIES == 5

    def test__access_token_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("POLAR_ACCESS_TOKEN", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            PolarSettings(_env_file=None)

        assert "ACCESS_TOKEN" in str(exc_info.value)

    def test__user_id_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("POLAR_USER_ID", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            PolarSettings(_env_file=None)

        assert "USER_ID" in str(exc_info.value)

    def test__client_credentials_are_independent_of_the_token_pair(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLAR_ACCESS_TOKEN", "dummy-access-token")
        monkeypatch.setenv("POLAR_USER_ID", "00000000")
        monkeypatch.setenv("POLAR_CLIENT_ID", "app-client-id")
        monkeypatch.setenv("POLAR_CLIENT_SECRET", "app-client-secret")

        settings = PolarSettings(_env_file=None)

        assert settings.CLIENT_ID == "app-client-id"
        assert settings.CLIENT_ID != settings.USER_ID
        assert settings.CLIENT_SECRET != settings.ACCESS_TOKEN
