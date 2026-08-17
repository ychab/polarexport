# Phase 2 — Config & shared infrastructure

**Depends on:** phase 1. **Needs a Polar token:** no.

## Goal

Put the cross-cutting infrastructure in place: package metadata, log configuration, settings, the
shared HTTP client mixin, and a bare Typer app. At the end of this phase `uv run polarexport --version`
works.

## Reference — read these first

```
/home/yannick/Projects/PERSONAL/museflow/museflow/__init__.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/types.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/config/loggers.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/config/settings/app.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/adapters/http.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/entrypoints/cli/main.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/entrypoints/cli/parsers.py
```

## Carried over from phase 1 — do this first

Phase 1 declared **no runtime dependencies** (so `deptry` stays meaningful) and therefore had to
disable the pydantic mypy plugin. This phase is the first to import them, so in `pyproject.toml`:

1. Fill in `dependencies`:
   ```toml
   dependencies = [
       "pydantic>=2.13.4",
       "pydantic-settings>=2.14.2",
       "typer>=0.26.8",
       "httpx>=0.28.1",
       "tenacity>=9.1.4",
   ]
   ```
   (`rich` waits for phase 8, which is where it is first used.)
2. Re-enable the commented-out line in `[tool.mypy]`:
   ```toml
   plugins = "pydantic.mypy"
   ```
3. `make install-deps` and confirm `make lint` is still clean.

## Files

### `polarexport/__init__.py`

Copy museflow's verbatim:

```python
from importlib.metadata import metadata
from importlib.metadata import version
from pathlib import Path
from typing import Final

PROJECT_DIR: Final[Path] = Path(__file__).parent
BASE_DIR: Final[Path] = PROJECT_DIR.parent

__project_name__ = metadata("polarexport")["Name"]
__version__ = version("polarexport")
```

### `polarexport/infrastructure/types.py`

```python
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogHandler = Literal["console", "cli", "cli_alert", "rich", "null"]
```

### `polarexport/infrastructure/config/loggers.py`

Copy `museflow/infrastructure/config/loggers.py` verbatim with these edits:
- `LOGGER_MUSEFLOW` → `LOGGER_POLAREXPORT: Final[str] = "polarexport"`.
- In `default_conf["loggers"]`, keep `polarexport` and `httpx`; **delete** the `uvicorn`, `alembic`
  and `sqlalchemy.engine` entries.
- Keep every formatter and handler (`console`, `cli`, `cli_alert`, `rich`, `null`) and the
  `configure_loggers(level, handlers, propagate=False)` signature and docstring unchanged.

### `polarexport/infrastructure/config/settings/__init__.py`

Empty, like museflow's.

### `polarexport/infrastructure/config/settings/app.py`

```python
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POLAREXPORT_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DEBUG: bool = False

    LOG_LEVEL_CLI: LogLevel = "WARNING"
    LOG_HANDLERS_CLI: list[LogHandler] = ["cli", "cli_alert"]

    DATA_DIR: Path = BASE_DIR / "data"       # accumulating raw-payload store
    EXPORT_DIR: Path = BASE_DIR / "export"   # generated zip archives

    EXPORT_CONCURRENCY: int = Field(default=5, ge=1, le=20)   # in-flight Polar requests


app_settings = AppSettings()
```

`DATA_DIR` and `EXPORT_DIR` are settings rather than constants so a user can relocate them
(`POLAREXPORT_DATA_DIR=/mnt/backup/polar`) without touching code. Both are gitignored.

### `polarexport/infrastructure/config/settings/polar.py`

```python
class PolarSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POLAR_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Required at export time.
    ACCESS_TOKEN: str = Field(..., min_length=1)   # bearer token from the OAuth exchange
    USER_ID: str = Field(..., min_length=1)        # x_user_id from that same response

    # Only used to (re-)run the auth flow by hand; see docs/authentication.md.
    # Deliberately optional so the tool runs with just the two values above.
    CLIENT_ID: str | None = None
    CLIENT_SECRET: str | None = None
    REDIRECT_URI: HttpUrl | None = None

    BASE_URL: HttpUrl = HttpUrl("https://www.polaraccesslink.com")

    HTTP_TIMEOUT: float = 30.0
    HTTP_MAX_RETRIES: int = 5


polar_settings = PolarSettings()
```

**Do not confuse the two pairs.** `CLIENT_ID`/`CLIENT_SECRET` identify the *application* (from the
Credentials tab at admin.polaraccesslink.com); `ACCESS_TOKEN`/`USER_ID` identify the *user's grant to
that application* and are what the API actually authenticates with. `CLIENT_ID` is **not** `USER_ID`.
Put that as a comment in the module and point at `docs/authentication.md`.

`ACCESS_TOKEN` and `CLIENT_SECRET` are secret. **They must never be logged, never appear in an
exception message, and never be written into `data/`, the archive, or the manifest.**

### `polarexport/infrastructure/adapters/http.py`

Copy `museflow/infrastructure/adapters/http.py` **verbatim** — `_is_retryable_error` and
`HttpClientMixin`, including the docstring (reword the last paragraph, which mentions Spotify/Gemini
ports, to reference `NightProviderPort`). The only functional change is the settings import:
`stop=stop_after_attempt(polar_settings.HTTP_MAX_RETRIES)`.

This adds `httpx` and `tenacity` to `pyproject.toml` dependencies (see the deptry note in phase 1).

### `polarexport/infrastructure/entrypoints/cli/parsers.py`

Lift only what is needed from museflow's:

```python
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
```

Drop `parse_email`, `parse_password`, `parse_locale`. `parse_sources` arrives in phase 7.

### `polarexport/infrastructure/entrypoints/cli/main.py`

Model on museflow's `cli/main.py`:

```python
app = typer.Typer(
    name="polarexport",
    help="Export your Polar data as shareable archives.",
    no_args_is_help=True,
)


def version_callback(show_version: bool) -> None:
    if show_version:
        typer.echo(f"polarexport Version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    log_level: LogLevel = typer.Option(app_settings.LOG_LEVEL_CLI, "--log-level", "-l", case_sensitive=False, help="Set the logging level."),
    log_handlers: list[str] = typer.Option(app_settings.LOG_HANDLERS_CLI, "--log-handlers", case_sensitive=True, callback=parse_log_handlers, help="Set the logging handlers."),
    version: bool | None = typer.Option(None, "--version", "-v", help="Show the application's version and exit.", callback=version_callback, is_eager=True),
):
    """Main entry point for the polarexport CLI application.

    This function initializes the logging configuration.
    """
    configure_loggers(level=log_level, handlers=cast(list[LogHandler], log_handlers))
```

No `add_typer` calls yet — the `night` command is registered here in phase 7.
Keep the trailing `if __name__ == "__main__": app()` guard.

### `tests/conftest.py` — add the logging fixture

Now that `configure_loggers` exists, add museflow's session-scoped autouse `configure_logging`
fixture: import `configure_loggers` **inside** the fixture body, call
`configure_loggers(level="DEBUG", handlers=["null"], propagate=True)`, and `logging.shutdown()` on
teardown.

---

## Tests

Mirror one test file per source file.

- `tests/unit/infrastructure/test_types.py` — trivial; may be folded into the loggers test if it would
  otherwise be empty.
- `tests/unit/infrastructure/config/test_loggers.py` — assert the resulting `logging` config for a
  couple of `(level, handlers, propagate)` combinations; use `caplog`, never patch the logger.
- `tests/unit/infrastructure/config/settings/test_app.py`, `test_polar.py` — defaults, validation
  bounds (`EXPORT_CONCURRENCY` out of range), and the required-field error when `POLAR_ACCESS_TOKEN`
  is absent (use `monkeypatch.delenv` in a fixture).
- `tests/unit/infrastructure/adapters/test_http.py` — port museflow's version. Cover
  `_is_retryable_error` for: 429 → True, 500 → True, 404 → False, `httpx.RequestError` → True,
  `ValueError` → False. Cover `make_api_call` happy path, `204` → `{}`, and `raise_for_status`
  propagation, using `pytest-httpx`. Cover `close()` and the async context manager.
- `tests/unit/infrastructure/entrypoints/cli/test_parsers.py` — valid date, invalid date →
  `typer.BadParameter`; valid and invalid handler lists.
- `tests/unit/infrastructure/entrypoints/cli/test_main.py` — `CliRunner` invocations for `--version`,
  `--help`, and a `--log-level`/`--log-handlers` pass-through asserting `configure_loggers` was called
  (patch it via a **fixture**, not inline).

---

## Acceptance criteria

```bash
uv run polarexport --version     # prints "polarexport Version: 0.1.0.dev0"
uv run polarexport --help        # shows global options, no subcommands yet
make lint                        # zero findings
make test                        # green at 100 % branch coverage
```
