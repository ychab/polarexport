from typing import get_args

from polarexport.infrastructure.types import LogHandler
from polarexport.infrastructure.types import LogLevel


class TestLogLevel:
    def test__values(self) -> None:
        assert get_args(LogLevel) == ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class TestLogHandler:
    def test__values(self) -> None:
        assert get_args(LogHandler) == ("console", "cli", "cli_alert", "rich", "null")
