from datetime import date
from typing import get_args

import typer

from polarexport.domain.enums import NightSource
from polarexport.infrastructure.types import LogHandler


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise typer.BadParameter(f"Date must be in YYYY-MM-DD format, got '{value}'") from e


def parse_log_handlers(values: list[str]) -> list[str]:
    for value in values:
        if value not in get_args(LogHandler):
            raise typer.BadParameter(f"Invalid handler: '{values}'. Allowed: {', '.join(get_args(LogHandler))}")

    return values


def parse_sources(values: list[str] | None) -> list[str]:
    """Validate --source values against the NightSource enum. "all" is shorthand for every source."""
    allowed = [source.value for source in NightSource]
    if not values or "all" in values:
        return allowed

    for value in values:
        if value not in allowed:
            raise typer.BadParameter(f"Invalid source: '{value}'. Allowed: {', '.join(allowed)}, all")

    return values
