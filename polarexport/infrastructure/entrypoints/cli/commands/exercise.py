import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import httpx
from httpx import codes

import typer
from rich.console import Console
from rich.table import Table

from polarexport.application.inputs.exercise import ExerciseExportInput
from polarexport.application.inputs.exercise import ExerciseSyncInput
from polarexport.application.use_cases.exercise_export import ExerciseExportUseCase
from polarexport.application.use_cases.exercise_sync import ExerciseSyncUseCase
from polarexport.domain.const import POLAR_EXERCISE_WINDOW_DAYS
from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.exercise_export import ExerciseExportReport
from polarexport.domain.entities.exercise_export import ExerciseSyncReport
from polarexport.domain.exceptions import ArchiveAlreadyExistsError
from polarexport.domain.exceptions import InvalidDateRangeError
from polarexport.domain.exceptions import MissingCredentialsError
from polarexport.domain.exceptions import NoExerciseDataError
from polarexport.domain.exceptions import ProviderRateLimitError
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.config.settings.app import app_settings
from polarexport.infrastructure.config.settings.polar import polar_settings
from polarexport.infrastructure.entrypoints.cli.dependencies import get_credentials_store
from polarexport.infrastructure.entrypoints.cli.dependencies import get_exercise_archiver
from polarexport.infrastructure.entrypoints.cli.dependencies import get_exercise_mapper
from polarexport.infrastructure.entrypoints.cli.dependencies import get_exercise_store
from polarexport.infrastructure.entrypoints.cli.dependencies import get_polar_client
from polarexport.infrastructure.entrypoints.cli.dependencies import get_profile_store
from polarexport.infrastructure.entrypoints.cli.messages import unauthorized_message
from polarexport.infrastructure.entrypoints.cli.parsers import parse_date
from polarexport.infrastructure.entrypoints.cli.parsers import parse_sports

logger = logging.getLogger(__name__)

console = Console()


async def exercise_logic(
    sync_in: ExerciseSyncInput | None,
    export_in: ExerciseExportInput,
    *,
    today: date,
    generated_at: datetime,
) -> tuple[ExerciseSyncReport | None, ExerciseExportReport]:
    sync_report: ExerciseSyncReport | None = None
    if sync_in is not None:
        async with get_polar_client() as client:
            sync_report = await ExerciseSyncUseCase(
                exercise_provider=client,
                profile_provider=client,
                exercise_store=get_exercise_store(),
                profile_store=get_profile_store(),
            ).sync(sync_in, today=today)

    export_report = await ExerciseExportUseCase(
        exercise_store=get_exercise_store(),
        profile_store=get_profile_store(),
        exercise_mapper=get_exercise_mapper(),
        exercise_archiver=get_exercise_archiver(),
    ).export(export_in, today=today, generated_at=generated_at)

    return sync_report, export_report


def exercise(
    # filters
    date_min: date | None = typer.Option(
        None,
        "--date-min",
        "-f",
        parser=parse_date,
        help="First session to export (YYYY-MM-DD). Defaults to 29 days ago.",
    ),
    date_max: date | None = typer.Option(
        None,
        "--date-max",
        "-t",
        parser=parse_date,
        help="Last session to export (YYYY-MM-DD). Defaults to today.",
    ),
    sport: list[str] = typer.Option(
        [],
        "--sport",
        callback=parse_sports,
        help="Sport to include, matched against detailed_sport_info; repeatable. Defaults to all.",
    ),
    # processing config
    refresh: bool = typer.Option(
        True,
        "--refresh/--no-refresh",
        help="Fetch training sessions from Polar first. --no-refresh builds the archive offline from data/.",
    ),
    force_refresh: bool = typer.Option(
        False, "--force-refresh", help="Re-fetch sessions already present in data/raw/."
    ),
    with_raw: bool = typer.Option(
        True, "--with-raw/--no-raw", help="Include the untouched Polar payloads under raw/."
    ),
    with_samples: bool = typer.Option(
        True, "--with-samples/--no-samples", help="Include the per-minute heart-rate curve."
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Where to write the archive. Defaults to data/export."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing archive."),
    # cap
    limit: int | None = typer.Option(None, "--limit", help="Export at most this many sessions, most recent first."),
) -> None:
    """Export your Polar training sessions as a zip archive."""
    if not refresh and force_refresh:
        raise typer.BadParameter("--force-refresh cannot be combined with --no-refresh.")

    today = date.today()
    resolved_date_min = date_min if date_min is not None else today - timedelta(days=POLAR_EXERCISE_WINDOW_DAYS - 1)
    resolved_date_max = date_max if date_max is not None else today
    resolved_output_dir = output_dir if output_dir is not None else app_settings.RESOLVED_EXPORT_DIR
    resolved_sports = frozenset(sport)
    generated_at = datetime.now(UTC)

    try:
        date_range = DateRange(date_min=resolved_date_min, date_max=resolved_date_max)

        sync_in = ExerciseSyncInput(with_samples=with_samples, force_refresh=force_refresh) if refresh else None
        export_in = ExerciseExportInput(
            date_range=date_range,
            sports=resolved_sports,
            include_raw=with_raw,
            include_samples=with_samples,
            output_dir=resolved_output_dir,
            force=force,
            limit=limit,
        )

        sync_report, export_report = asyncio.run(
            exercise_logic(sync_in, export_in, today=today, generated_at=generated_at)
        )
    except MissingCredentialsError as e:
        typer.secho(
            "No Polar credentials found. Run `polarexport auth` to set them up, or see "
            "docs/authentication.md to do it by hand.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except ProviderRateLimitError as e:
        typer.secho(
            "Polar rate-limited this request even after retries. Sessions already fetched are saved "
            "in data/raw/ — wait a while and run the command again to pick up where it left off.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except httpx.RequestError as e:
        typer.secho(
            f"Could not reach Polar at {polar_settings.BASE_URL} ({e.__class__.__name__}). Sessions "
            "already fetched are saved in data/raw/ — use --no-refresh to build the archive offline.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except httpx.HTTPStatusError as e:
        if e.response.status_code == codes.UNAUTHORIZED:
            typer.secho(unauthorized_message(get_credentials_store), fg=typer.colors.RED, err=True)
        else:
            typer.secho(
                f"Polar returned HTTP {e.response.status_code} even after retries. Sessions already "
                "fetched are saved in data/raw/ — try again later.",
                fg=typer.colors.RED,
                err=True,
            )
        raise typer.Exit(code=1) from e
    except NoExerciseDataError as e:
        message = str(e)
        if not refresh:
            message += " The local store has nothing for that range — try again without --no-refresh."
        typer.secho(message, fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except (InvalidDateRangeError, ArchiveAlreadyExistsError) as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if export_report.manifest.history_window_warning is not None:
        typer.secho(export_report.manifest.history_window_warning, fg=typer.colors.YELLOW)

    if sync_report is not None:
        console.print(_build_sync_table(sync_report))

    console.print(_build_export_table(export_report))
    console.print(_build_sport_table(export_report))

    typer.secho(f"Archive written to {export_report.archive_path}", fg=typer.colors.GREEN)


def _build_sync_table(sync_report: ExerciseSyncReport) -> Table:
    table = Table(title="Sync")
    table.add_column("Fetched", justify="right")
    table.add_column("Skipped", justify="right")
    table.add_column("Requests", justify="right")
    table.add_column("Availability")
    table.add_column("Profile Refreshed")
    table.add_row(
        str(sync_report.fetched),
        str(sync_report.skipped),
        str(sync_report.requests),
        sync_report.availability.value,
        "yes" if sync_report.profile_fetched else "no",
    )
    return table


def _build_export_table(export_report: ExerciseExportReport) -> Table:
    manifest = export_report.manifest
    table = Table(title="Export")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Sessions Exported", str(manifest.exercise_count))
    table.add_row("Total Duration", _human_readable_duration(manifest.total_duration_seconds))
    table.add_row("Total Calories", str(manifest.total_calories))
    table.add_row("Availability", manifest.availability.value)
    table.add_row("Archive", str(export_report.archive_path))
    table.add_row("Size", _human_readable_size(export_report.archive_size_bytes))
    return table


def _build_sport_table(export_report: ExerciseExportReport) -> Table:
    cardio_loads = _mean_cardio_load_by_sport(export_report.exercises)
    table = Table(title="By Sport")
    table.add_column("Sport")
    table.add_column("Sessions", justify="right")
    table.add_column("Total Duration", justify="right")
    table.add_column("Total Calories", justify="right")
    table.add_column("Mean Cardio Load", justify="right")
    for summary in export_report.manifest.sports:
        cardio_load = cardio_loads.get(summary.sport)
        table.add_row(
            summary.sport,
            str(summary.session_count),
            _human_readable_duration(summary.total_duration_seconds),
            str(summary.total_calories),
            f"{cardio_load:.1f}" if cardio_load is not None else "—",
        )
    return table


def _mean_cardio_load_by_sport(exercises: Sequence[Exercise]) -> dict[str, float]:
    totals: dict[str, list[float]] = {}
    for exercise_entity in exercises:
        training_load = exercise_entity.training_load
        if training_load is None or training_load.cardio_load is None:
            continue
        sport = exercise_entity.sport_label or "Unknown"
        totals.setdefault(sport, []).append(training_load.cardio_load)
    return {sport: sum(values) / len(values) for sport, values in totals.items()}


def _human_readable_duration(total_seconds: float) -> str:
    total_minutes = int(total_seconds // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def _human_readable_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB"):
        if size < 1024.0:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"
