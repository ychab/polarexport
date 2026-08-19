import asyncio
import logging
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

from polarexport.application.inputs.night import NightExportInput
from polarexport.application.inputs.night import NightSyncInput
from polarexport.application.use_cases.night_export import NightExportUseCase
from polarexport.application.use_cases.night_sync import NightSyncUseCase
from polarexport.domain.const import POLAR_HISTORY_WINDOW_DAYS
from polarexport.domain.entities.export import ExportReport
from polarexport.domain.entities.sync import SyncReport
from polarexport.domain.enums import NightSource
from polarexport.domain.exceptions import ArchiveAlreadyExistsError
from polarexport.domain.exceptions import InvalidDateRangeError
from polarexport.domain.exceptions import MissingCredentialsError
from polarexport.domain.exceptions import NoNightDataError
from polarexport.domain.exceptions import ProviderRateLimitError
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.config.settings.app import app_settings
from polarexport.infrastructure.config.settings.polar import polar_settings
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_archiver
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_mapper
from polarexport.infrastructure.entrypoints.cli.dependencies import get_night_store
from polarexport.infrastructure.entrypoints.cli.dependencies import get_polar_client
from polarexport.infrastructure.entrypoints.cli.parsers import parse_date
from polarexport.infrastructure.entrypoints.cli.parsers import parse_sources

logger = logging.getLogger(__name__)

console = Console()


async def night_logic(
    sync_in: NightSyncInput | None,
    export_in: NightExportInput,
    *,
    today: date,
    generated_at: datetime,
) -> tuple[SyncReport | None, ExportReport]:
    sync_report: SyncReport | None = None
    if sync_in is not None:
        async with get_polar_client() as client:
            sync_report = await NightSyncUseCase(night_provider=client, night_store=get_night_store()).sync(
                sync_in, today=today
            )

    export_report = await NightExportUseCase(
        night_store=get_night_store(),
        night_mapper=get_night_mapper(),
        night_archiver=get_night_archiver(),
    ).export(export_in, today=today, generated_at=generated_at)

    return sync_report, export_report


def night(
    # filters
    date_min: date | None = typer.Option(
        None,
        "--date-min",
        "-f",
        parser=parse_date,
        help="First night to export (YYYY-MM-DD). Defaults to 27 days ago.",
    ),
    date_max: date | None = typer.Option(
        None,
        "--date-max",
        "-t",
        parser=parse_date,
        help="Last night to export (YYYY-MM-DD). Defaults to today.",
    ),
    source: list[str] = typer.Option(
        None,
        "--source",
        callback=parse_sources,
        help="Data source to include; repeatable. Defaults to all.",
    ),
    # processing config
    refresh: bool = typer.Option(
        True,
        "--refresh/--no-refresh",
        help="Fetch missing nights from Polar first. --no-refresh builds the archive offline from data/.",
    ),
    force_refresh: bool = typer.Option(False, "--force-refresh", help="Re-fetch nights already present in data/."),
    with_raw: bool = typer.Option(
        True, "--with-raw/--no-raw", help="Include the untouched Polar payloads under raw/."
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Where to write the archive. Defaults to data/export."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing archive."),
    # cap
    limit: int | None = typer.Option(None, "--limit", help="Export at most this many nights, most recent first."),
) -> None:
    """Export your Polar night data as a zip archive."""
    if not refresh and force_refresh:
        raise typer.BadParameter("--force-refresh cannot be combined with --no-refresh.")

    today = date.today()
    resolved_date_min = date_min if date_min is not None else today - timedelta(days=POLAR_HISTORY_WINDOW_DAYS - 1)
    resolved_date_max = date_max if date_max is not None else today
    resolved_output_dir = output_dir if output_dir is not None else app_settings.RESOLVED_EXPORT_DIR
    resolved_sources = frozenset(NightSource(value) for value in source)
    generated_at = datetime.now(UTC)

    try:
        date_range = DateRange(date_min=resolved_date_min, date_max=resolved_date_max)

        sync_in = (
            NightSyncInput(date_range=date_range, sources=resolved_sources, force_refresh=force_refresh, limit=limit)
            if refresh
            else None
        )
        export_in = NightExportInput(
            date_range=date_range,
            sources=resolved_sources,
            include_raw=with_raw,
            output_dir=resolved_output_dir,
            force=force,
            limit=limit,
        )

        sync_report, export_report = asyncio.run(
            night_logic(sync_in, export_in, today=today, generated_at=generated_at)
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
            "Polar rate-limited this request even after retries. Nights already fetched are saved "
            "in data/ — wait a while and run the command again to pick up where it left off.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except httpx.RequestError as e:
        typer.secho(
            f"Could not reach Polar at {polar_settings.BASE_URL} ({e.__class__.__name__}). Nights "
            "already fetched are saved in data/ — use --no-refresh to build the archive offline.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except httpx.HTTPStatusError as e:
        if e.response.status_code == codes.UNAUTHORIZED:
            typer.secho(
                "Authentication failed (401 Unauthorized). Check POLAR_ACCESS_TOKEN in .env — see "
                "docs/authentication.md.",
                fg=typer.colors.RED,
                err=True,
            )
        else:
            typer.secho(
                f"Polar returned HTTP {e.response.status_code} even after retries. Nights already "
                "fetched are saved in data/ — try again later.",
                fg=typer.colors.RED,
                err=True,
            )
        raise typer.Exit(code=1) from e
    except NoNightDataError as e:
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

    typer.secho(f"Archive written to {export_report.archive_path}", fg=typer.colors.GREEN)


def _build_sync_table(sync_report: SyncReport) -> Table:
    table = Table(title="Sync")
    table.add_column("Source")
    table.add_column("Fetched", justify="right")
    table.add_column("From Cache", justify="right")
    table.add_column("Empty", justify="right")
    table.add_column("Availability")
    for night_source, stat in sync_report.stats.items():
        table.add_row(
            night_source.value, str(stat.fetched), str(stat.skipped), str(stat.empty), stat.availability.value
        )
    return table


def _build_export_table(export_report: ExportReport) -> Table:
    manifest = export_report.manifest
    table = Table(title="Export")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Nights Exported", str(manifest.night_count))
    table.add_row("Gaps", str(len(manifest.gaps)))
    table.add_row(
        "Source Availability",
        ", ".join(
            f"{night_source.value}: {manifest.source_availability[night_source].value}"
            for night_source in manifest.sources_requested
        ),
    )
    table.add_row("Archive", str(export_report.archive_path))
    table.add_row("Size", _human_readable_size(export_report.archive_size_bytes))
    return table


def _human_readable_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB"):
        if size < 1024.0:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"
