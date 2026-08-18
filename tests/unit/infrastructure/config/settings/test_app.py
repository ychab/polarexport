from pathlib import Path

from pydantic import ValidationError

import pytest

from polarexport import BASE_DIR
from polarexport.infrastructure.config.settings.app import AppSettings


class TestAppSettings:
    def test__defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The test suite forces POLAREXPORT_LOG_LEVEL_CLI/LOG_HANDLERS_CLI (see pyproject.toml
        # pytest env) so the CLI stays quiet during tests — remove them to see the real defaults.
        monkeypatch.delenv("POLAREXPORT_LOG_LEVEL_CLI", raising=False)
        monkeypatch.delenv("POLAREXPORT_LOG_HANDLERS_CLI", raising=False)

        settings = AppSettings(_env_file=None)

        assert settings.DEBUG is False
        assert settings.LOG_LEVEL_CLI == "WARNING"
        assert settings.LOG_HANDLERS_CLI == ["cli", "cli_alert"]
        assert settings.DATA_DIR == BASE_DIR / "data"
        assert settings.EXPORT_DIR == BASE_DIR / "export"
        assert settings.EXPORT_CONCURRENCY == 5

    def test__data_and_export_dir_are_relocatable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLAREXPORT_DATA_DIR", "/mnt/backup/polar")
        monkeypatch.setenv("POLAREXPORT_EXPORT_DIR", "/mnt/backup/polar-archives")

        settings = AppSettings(_env_file=None)

        assert settings.DATA_DIR == Path("/mnt/backup/polar")
        assert settings.EXPORT_DIR == Path("/mnt/backup/polar-archives")

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
