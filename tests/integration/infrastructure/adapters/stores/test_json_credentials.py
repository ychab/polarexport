import json
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest

from polarexport.infrastructure.adapters.stores.json_credentials import JsonCredentialsStore


class TestJsonCredentialsStore:
    @pytest.fixture
    def store(self) -> JsonCredentialsStore:
        return JsonCredentialsStore()

    @pytest.fixture
    def credentials_path(self, tmp_path: Path) -> Path:
        return tmp_path / "data" / "auth" / "credentials.json"

    async def test__write__produces_exact_json_schema(
        self, store: JsonCredentialsStore, credentials_path: Path
    ) -> None:
        obtained_at = datetime(2026, 8, 18, 16, 42, 5, 123456, tzinfo=UTC)

        await store.write(
            access_token="wiremock-access-token",
            user_id="60233839",
            obtained_at=obtained_at,
            expires_in=473040000,
            path=credentials_path,
            force=False,
        )

        envelope = json.loads(credentials_path.read_text(encoding="utf-8"))
        assert envelope == {
            "schema_version": 1,
            "api": "polar-accesslink-v3",
            "user_id": "60233839",
            "access_token": "wiremock-access-token",
            "obtained_at": obtained_at.isoformat(),
            "expires_in": 473040000,
        }

    async def test__reauthorize_with_force__cleanly_replaces_prior_credentials(
        self, store: JsonCredentialsStore, credentials_path: Path
    ) -> None:
        first_obtained_at = datetime(2026, 7, 1, tzinfo=UTC)
        second_obtained_at = datetime(2026, 8, 18, tzinfo=UTC)
        await store.write(
            access_token="first-token",
            user_id="60233839",
            obtained_at=first_obtained_at,
            expires_in=100,
            path=credentials_path,
            force=False,
        )

        await store.write(
            access_token="second-token",
            user_id="60233839",
            obtained_at=second_obtained_at,
            expires_in=200,
            path=credentials_path,
            force=True,
        )

        result = await store.read(credentials_path)
        assert result is not None
        assert result.access_token == "second-token"
        assert result.obtained_at == second_obtained_at
        assert result.expires_in == 200
        envelope = json.loads(credentials_path.read_text(encoding="utf-8"))
        assert "first-token" not in json.dumps(envelope)
