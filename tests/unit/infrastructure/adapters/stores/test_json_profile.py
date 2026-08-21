import logging
from pathlib import Path

import pytest

from polarexport.infrastructure.adapters.stores.json_profile import JsonProfileStore

from tests.unit.factories.ports.stores.profile import StoredProfileFactory


class TestJsonProfileStoreRead:
    @pytest.fixture
    def store(self, tmp_path: Path) -> JsonProfileStore:
        return JsonProfileStore(data_dir=tmp_path, api="polar-accesslink-v3")

    async def test__corrupt_file__logs_warning_and_returns_none(
        self, store: JsonProfileStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        profile_path = tmp_path / "polar-accesslink-v3" / "profile.json"
        profile_path.parent.mkdir(parents=True)
        profile_path.write_text("not valid json {", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = await store.read()

        assert result is None
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    async def test__envelope_missing_payload__logs_warning_and_returns_none(
        self, store: JsonProfileStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        profile_path = tmp_path / "polar-accesslink-v3" / "profile.json"
        profile_path.parent.mkdir(parents=True)
        profile_path.write_text('{"schema_version": 1, "api": "polar-accesslink-v3"}', encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = await store.read()

        assert result is None
        assert any(record.levelno == logging.WARNING for record in caplog.records)


class TestJsonProfileStoreWrite:
    async def test__write_fails__temp_file_is_cleaned_up(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(*args: object, **kwargs: object) -> None:
            raise ValueError("boom")

        monkeypatch.setattr("polarexport.infrastructure.adapters.stores.json_profile.os.fchmod", _raise)
        store = JsonProfileStore(data_dir=tmp_path, api="polar-accesslink-v3")

        with pytest.raises(ValueError, match="boom"):
            await store.write(StoredProfileFactory.build())

        profile_dir = tmp_path / "polar-accesslink-v3"
        assert list(profile_dir.iterdir()) == []
