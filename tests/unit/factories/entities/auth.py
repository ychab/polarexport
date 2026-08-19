from pathlib import Path

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.entities.auth import AuthReport
from polarexport.domain.entities.auth import OAuthTokens


class OAuthTokensFactory(DataclassFactory[OAuthTokens]):
    __model__ = OAuthTokens


class AuthReportFactory(DataclassFactory[AuthReport]):
    __model__ = AuthReport

    credentials_path = Use(lambda: Path("data/auth/credentials.json"))
