import stat
from pathlib import Path

import pytest

from polarexport.domain.exceptions import CredentialsAlreadyExistError
from polarexport.infrastructure.adapters.stores.dotenv import DotenvCredentialsStore


class TestDotenvCredentialsStore:
    @pytest.fixture
    def store(self) -> DotenvCredentialsStore:
        return DotenvCredentialsStore()

    @pytest.fixture
    def env_path(self, tmp_path: Path) -> Path:
        return tmp_path / ".env"

    async def test__missing_file__creates_it(self, store: DotenvCredentialsStore, env_path: Path) -> None:
        await store.write(access_token="tok", user_id="123", env_path=env_path, force=False)

        content = env_path.read_text(encoding="utf-8")
        assert "POLAR_ACCESS_TOKEN=tok" in content
        assert "POLAR_USER_ID=123" in content

    async def test__preserves_comments_and_unrelated_keys(self, store: DotenvCredentialsStore, env_path: Path) -> None:
        env_path.write_text("# a comment\nPOLAR_CLIENT_ID=my-client-id\n\nPOLAREXPORT_DEBUG=true\n", encoding="utf-8")

        await store.write(access_token="tok", user_id="123", env_path=env_path, force=False)

        lines = env_path.read_text(encoding="utf-8").splitlines()
        assert "# a comment" in lines
        assert "POLAR_CLIENT_ID=my-client-id" in lines
        assert "" in lines
        assert "POLAREXPORT_DEBUG=true" in lines
        assert "POLAR_ACCESS_TOKEN=tok" in lines
        assert "POLAR_USER_ID=123" in lines

    async def test__existing_token__force__replaces_in_place(
        self, store: DotenvCredentialsStore, env_path: Path
    ) -> None:
        env_path.write_text("POLAR_ACCESS_TOKEN=old-token\nPOLAR_USER_ID=old-id\n", encoding="utf-8")

        await store.write(access_token="new-token", user_id="new-id", env_path=env_path, force=True)

        lines = env_path.read_text(encoding="utf-8").splitlines()
        assert lines.count("POLAR_ACCESS_TOKEN=new-token") == 1
        assert "POLAR_ACCESS_TOKEN=old-token" not in lines
        assert "POLAR_USER_ID=new-id" in lines

    async def test__existing_token__no_force__refuses(self, store: DotenvCredentialsStore, env_path: Path) -> None:
        env_path.write_text("POLAR_ACCESS_TOKEN=old-token\n", encoding="utf-8")

        with pytest.raises(CredentialsAlreadyExistError, match="--force"):
            await store.write(access_token="new-token", user_id="new-id", env_path=env_path, force=False)

        assert "old-token" in env_path.read_text(encoding="utf-8")

    async def test__result_file_mode_is_0600(self, store: DotenvCredentialsStore, env_path: Path) -> None:
        await store.write(access_token="tok", user_id="123", env_path=env_path, force=False)

        mode = stat.S_IMODE(env_path.stat().st_mode)
        assert mode == 0o600

    async def test__creates_missing_parent_directories(self, store: DotenvCredentialsStore, tmp_path: Path) -> None:
        nested_env_path = tmp_path / "nested" / ".env"

        await store.write(access_token="tok", user_id="123", env_path=nested_env_path, force=False)

        assert nested_env_path.is_file()

    async def test__write_is_atomic__no_leftover_temp_files(
        self, store: DotenvCredentialsStore, env_path: Path
    ) -> None:
        await store.write(access_token="tok", user_id="123", env_path=env_path, force=False)

        assert list(env_path.parent.iterdir()) == [env_path]

    async def test__write_fails__temp_file_is_cleaned_up(
        self, store: DotenvCredentialsStore, env_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(*args: object, **kwargs: object) -> None:
            raise ValueError("boom")

        monkeypatch.setattr("polarexport.infrastructure.adapters.stores.dotenv.os.fchmod", _raise)

        with pytest.raises(ValueError, match="boom"):
            await store.write(access_token="tok", user_id="123", env_path=env_path, force=False)

        assert list(env_path.parent.iterdir()) == []
