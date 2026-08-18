from tests.unit.factories.entities.auth import AuthReportFactory
from tests.unit.factories.entities.auth import OAuthTokensFactory


class TestOAuthTokens:
    def test__fields(self) -> None:
        tokens = OAuthTokensFactory.build(user_id="12345678", expires_in=3600)

        assert tokens.user_id == "12345678"
        assert tokens.expires_in == 3600

    def test__repr__redacts_access_token(self) -> None:
        tokens = OAuthTokensFactory.build(access_token="tok-must-never-be-logged", user_id="12345678")

        rendered = repr(tokens)

        assert "***" in rendered
        assert "tok-must-never-be-logged" not in rendered
        assert "12345678" in rendered


class TestAuthReport:
    def test__fields(self) -> None:
        report = AuthReportFactory.build(user_id="12345678", member_id="yannick", newly_registered=True)

        assert report.user_id == "12345678"
        assert report.member_id == "yannick"
        assert report.newly_registered is True
