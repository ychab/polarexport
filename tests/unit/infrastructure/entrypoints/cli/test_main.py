import importlib
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType
from typing import get_args
from unittest import mock

import pytest
from typer.testing import CliRunner

import polarexport
from polarexport import __version__
from polarexport.infrastructure.adapters import http as http_module
from polarexport.infrastructure.adapters.providers.polar import client as client_module
from polarexport.infrastructure.config.settings import polar as polar_settings_module
from polarexport.infrastructure.entrypoints.cli import dependencies as dependencies_module
from polarexport.infrastructure.entrypoints.cli import main as main_module
from polarexport.infrastructure.entrypoints.cli.commands import night as night_module
from polarexport.infrastructure.entrypoints.cli.main import app
from polarexport.infrastructure.types import LogLevel

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

# The full import chain `main -> night -> dependencies -> client -> http -> polar`, in dependency
# order, so reloading it end-to-end genuinely re-executes every module-level statement — matching a
# fresh process import rather than reusing already-cached module objects.
_IMPORT_CHAIN: tuple[ModuleType, ...] = (
    polar_settings_module,
    http_module,
    client_module,
    dependencies_module,
    night_module,
    main_module,
)

_POLAR_ENV_VARS = (
    "POLAR_ACCESS_TOKEN",
    "POLAR_USER_ID",
    "POLAR_CLIENT_ID",
    "POLAR_CLIENT_SECRET",
    "POLAR_REDIRECT_URI",
    "POLAR_BASE_URL",
    "POLAR_OAUTH_TOKEN_URL",
    "POLAR_OAUTH_AUTHORIZATION_URL",
    "POLAR_HTTP_TIMEOUT",
    "POLAR_HTTP_MAX_RETRIES",
)


class TestMainCommand:
    @pytest.mark.parametrize("cmd_arg", ["--version", "-v"])
    def test__version(self, runner: CliRunner, cmd_arg: str, block_cli_configure_loggers: mock.Mock) -> None:
        result = runner.invoke(app, [cmd_arg])

        assert result.exit_code == 0
        assert f"polarexport Version: {__version__}" in result.output

        block_cli_configure_loggers.assert_not_called()

    def test__help(self, runner: CliRunner, block_cli_configure_loggers: mock.Mock) -> None:
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "--log-level" in result.output
        assert "--log-handlers" in result.output

    @pytest.mark.parametrize("log_level", get_args(LogLevel))
    def test__log_level(self, runner: CliRunner, block_cli_configure_loggers: mock.Mock, log_level: str) -> None:
        @app.command("noop")
        def noop() -> None:
            pass

        result = runner.invoke(app, ["--log-level", log_level, "noop"])
        assert result.exit_code == 0

        block_cli_configure_loggers.assert_called_once_with(
            level=log_level,
            handlers=mock.ANY,
        )

    def test__log_handler__nominal(self, runner: CliRunner, block_cli_configure_loggers: mock.Mock) -> None:
        @app.command("noop")
        def noop() -> None:
            pass

        result = runner.invoke(app, ["--log-handlers", "console", "--log-handlers", "null", "noop"])
        assert result.exit_code == 0

        block_cli_configure_loggers.assert_called_once_with(
            level=mock.ANY,
            handlers=["console", "null"],
        )

    def test__log_handler__invalid(
        self,
        runner: CliRunner,
        block_cli_configure_loggers: mock.Mock,
        clean_typer_text: TextCleaner,
    ) -> None:
        @app.command("noop")
        def noop() -> None:
            pass

        result = runner.invoke(app, ["--log-handlers", "foo", "--log-handlers", "bar", "noop"])
        assert result.exit_code == 2

        output = clean_typer_text(result.output)
        assert "Invalid value for '--log-handlers'" in output
        assert "Invalid handler: '['foo', 'bar']'" in output

        block_cli_configure_loggers.assert_not_called()


class TestFirstRunBootstrap:
    @pytest.fixture
    def reloaded_with_no_credentials(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterable[ModuleType]:
        # Regression test for the phase-12 bug: `PolarSettings()` used to require ACCESS_TOKEN/USER_ID
        # and was built at import time, so the CLI could not even start on a fresh checkout. A real
        # `.env` on this machine would mask the bug (it's read via BASE_DIR), so BASE_DIR is
        # redirected to an empty tmp_path to simulate one.
        for name in _POLAR_ENV_VARS:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(polarexport, "BASE_DIR", tmp_path)

        for module in _IMPORT_CHAIN:
            importlib.reload(module)

        yield main_module

        monkeypatch.undo()
        for module in _IMPORT_CHAIN:
            importlib.reload(module)

    def test__import_with_no_credentials__does_not_raise(self, reloaded_with_no_credentials: ModuleType) -> None:
        result = CliRunner().invoke(reloaded_with_no_credentials.app, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.output
