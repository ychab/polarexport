import json
import stat
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest

from polarexport.infrastructure.adapters.stores.json_profile import JsonProfileStore

from tests.unit.factories.ports.stores.profile import StoredProfileFactory


class TestJsonProfileStore:
    @pytest.fixture
    def store(self, tmp_path: Path) -> JsonProfileStore:
        return JsonProfileStore(data_dir=tmp_path, api="polar-accesslink-v3")

    @pytest.fixture
    def profile_path(self, tmp_path: Path) -> Path:
        return tmp_path / "polar-accesslink-v3" / "profile.json"

    async def test__write_then_read__round_trips(self, store: JsonProfileStore) -> None:
        fetched_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
        stored = StoredProfileFactory.build(fetched_at=fetched_at, payload={"birthdate": "1990-03-15"})

        await store.write(stored)
        result = await store.read()

        assert result is not None
        assert result.payload == {"birthdate": "1990-03-15"}
        assert result.fetched_at == fetched_at
        assert result.api == "polar-accesslink-v3"

    async def test__write__produces_expected_envelope_at_expected_path(
        self, store: JsonProfileStore, profile_path: Path
    ) -> None:
        stored = StoredProfileFactory.build(fetched_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC), payload={"a": 1})

        await store.write(stored)

        envelope = json.loads(profile_path.read_text(encoding="utf-8"))
        assert envelope == {
            "schema_version": 1,
            "api": "polar-accesslink-v3",
            "fetched_at": "2026-08-18T12:00:00+00:00",
            "payload": {"a": 1},
        }

    async def test__write_twice__overwrites_cleanly(self, store: JsonProfileStore) -> None:
        await store.write(StoredProfileFactory.build(payload={"v": 1}))
        await store.write(StoredProfileFactory.build(payload={"v": 2}))

        result = await store.read()

        assert result is not None
        assert result.payload == {"v": 2}

    async def test__never_written__read_returns_none(self, store: JsonProfileStore) -> None:
        result = await store.read()

        assert result is None

    async def test__result_file_mode_is_0600(self, store: JsonProfileStore, profile_path: Path) -> None:
        await store.write(StoredProfileFactory.build())

        assert stat.S_IMODE(profile_path.stat().st_mode) == 0o600

    async def test__write__creates_missing_parent_directories(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "fresh" / "data"
        store = JsonProfileStore(data_dir=data_dir, api="polar-accesslink-v3")

        await store.write(StoredProfileFactory.build())

        assert (data_dir / "polar-accesslink-v3" / "profile.json").is_file()

    async def test__write_is_atomic__no_leftover_temp_files(self, store: JsonProfileStore, profile_path: Path) -> None:
        await store.write(StoredProfileFactory.build())

        assert list(profile_path.parent.iterdir()) == [profile_path]
