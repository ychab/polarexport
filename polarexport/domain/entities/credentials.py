from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta


@dataclass(frozen=True, kw_only=True)
class StoredCredentials:
    user_id: str
    access_token: str
    api: str
    obtained_at: datetime
    expires_in: int

    def is_expired(self, *, now: datetime) -> bool:
        return now >= self.obtained_at + timedelta(seconds=self.expires_in)

    def __repr__(self) -> str:
        return (
            f"StoredCredentials(user_id={self.user_id!r}, access_token='***', api={self.api!r}, "
            f"obtained_at={self.obtained_at!r}, expires_in={self.expires_in})"
        )
