from pathlib import Path

from pydantic import ValidationError

import pytest

from polarexport.application.inputs.auth import AuthLoginInput


class TestAuthLoginInput:
    def test__defaults(self) -> None:
        auth_in = AuthLoginInput(
            redirect_uri="http://localhost:8000/callback", credentials_file=Path("data/auth/credentials.json")
        )

        assert auth_in.member_id is None
        assert auth_in.force is False
        assert auth_in.timeout == 300.0

    def test__timeout_below_minimum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AuthLoginInput(
                redirect_uri="http://localhost:8000/callback",
                credentials_file=Path("data/auth/credentials.json"),
                timeout=5.0,
            )
