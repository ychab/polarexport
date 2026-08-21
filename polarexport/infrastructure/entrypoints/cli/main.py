from typing import cast

import typer

from polarexport import __version__
from polarexport.infrastructure.config.loggers import configure_loggers
from polarexport.infrastructure.config.settings.app import app_settings
from polarexport.infrastructure.entrypoints.cli.commands import auth
from polarexport.infrastructure.entrypoints.cli.commands import exercise
from polarexport.infrastructure.entrypoints.cli.commands import night
from polarexport.infrastructure.entrypoints.cli.parsers import parse_log_handlers
from polarexport.infrastructure.types import LogHandler
from polarexport.infrastructure.types import LogLevel

app = typer.Typer(
    name="polarexport",
    help="Export your Polar data as shareable archives.",
    no_args_is_help=True,
)

app.command(name="auth", help="Authorize polarexport against your Polar account")(auth.auth)
app.command(name="night", help="Export nightly sleep & recovery data as a zip archive")(night.night)
app.command(name="exercise", help="Export training sessions as a zip archive")(exercise.exercise)


def version_callback(show_version: bool) -> None:
    if show_version:
        typer.echo(f"polarexport Version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    log_level: LogLevel = typer.Option(
        app_settings.LOG_LEVEL_CLI,
        "--log-level",
        "-l",
        case_sensitive=False,
        help="Set the logging level.",
    ),
    log_handlers: list[str] = typer.Option(
        app_settings.LOG_HANDLERS_CLI,
        "--log-handlers",
        case_sensitive=True,
        callback=parse_log_handlers,
        help="Set the logging handlers.",
    ),
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """Main entry point for the polarexport CLI application.

    This function initializes the logging configuration.
    """
    configure_loggers(level=log_level, handlers=cast(list[LogHandler], log_handlers))


# This entrypoint should be used only for local debugging.
if __name__ == "__main__":
    app()
