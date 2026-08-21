from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.application.ports.stores.exercise import StoredExercise


class TestStoredExercise:
    def test__fields(self) -> None:
        fetched_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)

        stored = StoredExercise(
            id="54klrKbL",
            date=date(2026, 8, 18),
            fetched_at=fetched_at,
            api="polar-accesslink-v3",
            payload={"id": "54klrKbL"},
        )

        assert stored.id == "54klrKbL"
        assert stored.date == date(2026, 8, 18)
        assert stored.fetched_at == fetched_at
        assert stored.payload == {"id": "54klrKbL"}
