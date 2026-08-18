from datetime import date

import pytest
import typer

from polarexport.infrastructure.entrypoints.cli.parsers import parse_date
from polarexport.infrastructure.entrypoints.cli.parsers import parse_log_handlers


class TestParseDate:
    def test__valid(self) -> None:
        assert parse_date("2026-08-17") == date(2026, 8, 17)

    def test__invalid(self) -> None:
        with pytest.raises(typer.BadParameter, match="Date must be in YYYY-MM-DD format, got 'not-a-date'"):
            parse_date("not-a-date")


class TestParseLogHandlers:
    def test__valid(self) -> None:
        assert parse_log_handlers(["console", "null"]) == ["console", "null"]

    def test__invalid(self) -> None:
        with pytest.raises(typer.BadParameter, match="Invalid handler"):
            parse_log_handlers(["console", "not-a-handler"])
