from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class StoredCredentials:
    user_id: str
    access_token: str
    api: str
    obtained_at: datetime
    expires_in: int

    def __repr__(self) -> str:
        return (
            f"StoredCredentials(user_id={self.user_id!r}, access_token='***', api={self.api!r}, "
            f"obtained_at={self.obtained_at!r}, expires_in={self.expires_in})"
        )
