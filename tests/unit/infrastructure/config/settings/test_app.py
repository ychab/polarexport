from pathlib import Path

from pydantic import ValidationError

import pytest

from polarexport import BASE_DIR
from polarexport.infrastructure.config.settings.app import AppSettings


class TestAppSettings:
    def test__defaults(self) -> None:
        # `isolated_settings_env` (conftest) has already stripped POLAREXPORT_* from the environment,
        # so what is left is exactly what the model declares.
        settings = AppSettings(_env_file=None)

        assert settings.DEBUG is False
        assert settings.LOG_LEVEL_CLI == "WARNING"
        assert settings.LOG_HANDLERS_CLI == ["cli", "cli_alert"]
        assert settings.DATA_DIR == BASE_DIR / "data"
        assert settings.EXPORT_DIR is None
        assert settings.RAW_DIR == BASE_DIR / "data" / "raw"
        assert settings.AUTH_DIR == BASE_DIR / "data" / "auth"
        assert settings.RESOLVED_EXPORT_DIR == BASE_DIR / "data" / "export"
        assert settings.EXPORT_CONCURRENCY == 5

    def test__data_dir_is_relocatable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLAREXPORT_DATA_DIR", "/mnt/backup/polar")

        settings = AppSettings(_env_file=None)

        assert settings.DATA_DIR == Path("/mnt/backup/polar")
        assert settings.RAW_DIR == Path("/mnt/backup/polar/raw")
        assert settings.AUTH_DIR == Path("/mnt/backup/polar/auth")
        assert settings.RESOLVED_EXPORT_DIR == Path("/mnt/backup/polar/export")

    def test__export_dir_override__wins_over_data_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLAREXPORT_DATA_DIR", "/mnt/backup/polar")
        monkeypatch.setenv("POLAREXPORT_EXPORT_DIR", "/mnt/backup/polar-archives")

        settings = AppSettings(_env_file=None)

        assert settings.EXPORT_DIR == Path("/mnt/backup/polar-archives")
        assert settings.RESOLVED_EXPORT_DIR == Path("/mnt/backup/polar-archives")

    @pytest.mark.parametrize("value", [0, 21])
    def test__export_concurrency_out_of_range(self, monkeypatch: pytest.MonkeyPatch, value: int) -> None:
        monkeypatch.setenv("POLAREXPORT_EXPORT_CONCURRENCY", str(value))

        with pytest.raises(ValidationError):
            AppSettings(_env_file=None)

    @pytest.mark.parametrize("value", [1, 20])
    def test__export_concurrency_boundary_values(self, monkeypatch: pytest.MonkeyPatch, value: int) -> None:
        monkeypatch.setenv("POLAREXPORT_EXPORT_CONCURRENCY", str(value))

        settings = AppSettings(_env_file=None)

        assert settings.EXPORT_CONCURRENCY == value
