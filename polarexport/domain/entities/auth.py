from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, kw_only=True)
class OAuthTokens:
    access_token: str
    user_id: str
    expires_in: int

    def __repr__(self) -> str:
        return f"OAuthTokens(user_id={self.user_id!r}, access_token='***', expires_in={self.expires_in})"


@dataclass(frozen=True, kw_only=True)
class AuthReport:
    user_id: str
    member_id: str
    newly_registered: bool
    credentials_path: Path
