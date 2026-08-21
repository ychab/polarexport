from datetime import UTC
from datetime import datetime

from polarexport.application.ports.stores.profile import StoredProfile


class TestStoredProfile:
    def test__fields(self) -> None:
        fetched_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)

        stored = StoredProfile(fetched_at=fetched_at, api="polar-accesslink-v3", payload={"user-id": "60233839"})

        assert stored.fetched_at == fetched_at
        assert stored.payload == {"user-id": "60233839"}
