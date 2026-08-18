from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.application.ports.stores.night import StoredPayload
from polarexport.domain.enums import NightSource


class TestStoredPayload:
    def test__fields(self) -> None:
        fetched_at = datetime(2026, 7, 20, 6, 0, tzinfo=UTC)

        stored = StoredPayload(
            source=NightSource.SLEEP,
            date=date(2026, 7, 20),
            fetched_at=fetched_at,
            api="polar-accesslink-v3",
            payload={"foo": "bar"},
        )

        assert stored.source is NightSource.SLEEP
        assert stored.fetched_at == fetched_at
        assert stored.payload == {"foo": "bar"}

    def test__payload_none_means_no_data(self) -> None:
        stored = StoredPayload(
            source=NightSource.SLEEP,
            date=date(2026, 7, 20),
            fetched_at=datetime(2026, 7, 20, tzinfo=UTC),
            api="polar-accesslink-v3",
            payload=None,
        )

        assert stored.payload is None
