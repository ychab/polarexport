from pathlib import Path

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from polarexport.application.inputs.auth import AuthLoginInput


class AuthLoginInputFactory(ModelFactory[AuthLoginInput]):
    __model__ = AuthLoginInput

    member_id = None
    redirect_uri = "http://localhost:8000/auth/polar/callback"
    credentials_file = Use(lambda: Path("data/auth/credentials.json"))
    force = False
    timeout = 300.0
