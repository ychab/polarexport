# Phase 8 — CLI command & documentation

**Depends on:** phases 5, 6 and 7. **Needs a Polar token:** yes, for the end-to-end check.

## Goal

Wire the whole pipeline into the one shipping command and finish the documentation.

```
polarexport night --date-min 2026-07-20 --date-max 2026-08-16
```

## Reference — read these first

```
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/entrypoints/cli/main.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/entrypoints/cli/dependencies.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/entrypoints/cli/commands/users/update.py
/home/yannick/Projects/PERSONAL/museflow/tests/unit/infrastructure/entrypoints/cli/commands/users/test_update.py   # canonical CLI test file
/home/yannick/Projects/PERSONAL/museflow/tests/integration/infrastructure/entrypoints/cli/
/home/yannick/Projects/PERSONAL/museflow/README.md
/home/yannick/Projects/PERSONAL/museflow/.claude/{agents,commands}/
```

---

## `cli/dependencies.py`

Manual DI, museflow-style — `@asynccontextmanager` factories, no container:

```python
@asynccontextmanager
async def get_polar_client() -> AsyncIterator[PolarAccessLinkClient]:
    async with PolarAccessLinkClient(
        access_token=polar_settings.ACCESS_TOKEN,
        user_id=polar_settings.USER_ID,
        base_url=polar_settings.BASE_URL,
        timeout=polar_settings.HTTP_TIMEOUT,
        concurrency=app_settings.EXPORT_CONCURRENCY,
    ) as client:
        yield client


def get_night_store() -> FilesystemNightStore: ...
def get_night_mapper() -> PolarNightMapper: ...
def get_night_archiver() -> ZipNightArchiver: ...
```

## `cli/parsers.py` — add

```python
def parse_sources(values: list[str]) -> list[str]:
    """Validate --source values against the NightSource enum."""
```
`typer.BadParameter` listing the allowed values on bad input. `"all"` is accepted as shorthand for
every source.

## `cli/commands/night.py`

**`night_logic`** — async, orchestration only, **prints nothing**. It runs sync then export:

```python
async def night_logic(
    sync_in: NightSyncInput | None,
    export_in: NightExportInput,
    *,
    today: date,
    generated_at: datetime,
) -> tuple[SyncReport | None, ExportReport]:
    sync_report = None
    if sync_in is not None:
        async with get_polar_client() as client:
            sync_report = await NightSyncUseCase(
                night_provider=client, night_store=get_night_store()
            ).sync(sync_in, today=today)

    export_report = await NightExportUseCase(
        night_store=get_night_store(),
        night_mapper=get_night_mapper(),
        night_archiver=get_night_archiver(),
    ).export(export_in, today=today, generated_at=generated_at)

    return sync_report, export_report
```

`sync_in is None` is the `--no-refresh` path: **no HTTP client is constructed at all**, so an offline
export never needs a token. Make sure the `get_polar_client()` call sits inside the branch.

**`night`** — sync Typer command, owns every byte of output:

```python
def night(
    # filters
    date_min: str = typer.Option(None, "--date-min", "-f", parser=parse_date,
        help="First night to export (YYYY-MM-DD). Defaults to 27 days ago."),
    date_max: str = typer.Option(None, "--date-max", "-t", parser=parse_date,
        help="Last night to export (YYYY-MM-DD). Defaults to today."),
    source: list[str] = typer.Option(None, "--source", callback=parse_sources,
        help="Data source to include; repeatable. Defaults to all."),
    # processing config
    refresh: bool = typer.Option(True, "--refresh/--no-refresh",
        help="Fetch missing nights from Polar first. --no-refresh builds the archive offline from data/."),
    force_refresh: bool = typer.Option(False, "--force-refresh",
        help="Re-fetch nights already present in data/."),
    with_raw: bool = typer.Option(True, "--with-raw/--no-raw",
        help="Include the untouched Polar payloads under raw/."),
    output_dir: Path = typer.Option(None, "--output-dir",
        help="Where to write the archive. Defaults to ./export."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing archive."),
    # cap
    limit: int | None = typer.Option(None, "--limit",
        help="Export at most this many nights, most recent first."),
) -> None:
    """Export your Polar night data as a zip archive."""
```

Order is **filters → processing config → cap**. Resolve defaults in the body, not the signature, so
`date.today()` isn't frozen at import time. `--force-refresh` implies `--refresh`; if the user passes
`--no-refresh --force-refresh`, fail with a `typer.BadParameter` rather than silently picking one.

Output, all in this callback:
- Yellow warning when `history_window_warning` is set.
- A Rich sync table (skipped when `--no-refresh`): per source — fetched, from cache, empty,
  availability. This is where the user sees the local store doing its job.
- A Rich export table: nights exported, gaps, per-source availability, archive path, human-readable
  size.
- Green success line with the archive path.
- Domain exceptions (`InvalidDateRangeError`, `NoNightDataError`, `ArchiveAlreadyExistsError`) →
  `typer.secho(str(e), fg=typer.colors.RED, err=True)` + `raise typer.Exit(code=1) from e`.
- A missing/invalid token surfaces as `401`. Catch it and print an actionable message pointing at
  `.env` and `docs/authentication.md`. **Never echo the token.**
- `NoNightDataError` with `--no-refresh` deserves a specific hint: the local store has nothing for that
  range — try without `--no-refresh`.

This adds `rich` to `pyproject.toml`.

## `cli/main.py` — register

```python
app.command(name="night", help="Export nightly sleep & recovery data as a zip archive")(night.night)
```

A top-level command, not a sub-app — matching the requested `polarexport night --date-min …`. Future
`sport` / `activity` commands become sibling modules registered the same way; any one can be promoted
to a Typer sub-app later if it grows subcommands.

---

## Tests

Follow museflow's CLI convention exactly (canonical file listed in the reference block above).

**Unit** (`tests/unit/.../commands/test_night.py`) — three classes:
- `TestNightParserCommand` — `parse_sources` valid, invalid, `"all"`.
- `TestNightCommand` — `CliRunner` over the callback with `night_logic` patched via a **fixture**:
  default date resolution, every flag combination, `--no-refresh --force-refresh` rejected, the
  warning branch, each exception → exit 1 with the message on stderr, the 401 branch.
- `TestNightLogic` — `night_logic` with mocked dependencies; assert the inputs it builds, that both
  use cases are awaited once, and that **`get_polar_client` is not called when `sync_in is None`**.

**Integration** (`tests/integration/.../commands/test_night.py`) — one `TestNightLogic`, happy path
only, marked `@pytest.mark.wiremock`: real `PolarAccessLinkClient` against the WireMock stubs, real
`FilesystemNightStore` on `tmp_path`, real `PolarNightMapper`, real `ZipNightArchiver`. Assert a valid
archive comes out the far end. Add a second case that runs the same flow twice and asserts the second
run issues **zero** HTTP requests — that is the proof the local store works.

---

## Documentation

### `README.md`

Phase 1 created it with the What/Why, How it works, Requirements, Installation and Authentication
sections. Now fill in:

- **Usage / CLI User Guide** — Global Options, then `night` with every flag, and worked examples:
  ```bash
  polarexport night                                        # last 28 days
  polarexport night --date-min 2026-06-01                  # older nights served from data/
  polarexport night --no-refresh --date-min 2026-01-01     # offline, from the local store only
  polarexport night --source sleep --source recharge       # subset
  ```
- **Keeping history** — the section that earns the project its keep: run it monthly (a cron line is
  worth including) so `data/` accumulates past Polar's 28-day window. Explain that `data/` is the
  durable asset and `export/` is disposable, and that backing up `data/` is worthwhile.
- **The workflow it was built for** — generate an archive, attach the `.zip` to a prompt, ask an AI to
  review the nights. Include an example prompt.
- **Development** — `make lint`, `make test`, `make test-unit` (no Docker).

Be honest about the limits: this covers a rolling 28-day API window plus whatever history you have
accumulated locally. It cannot retroactively recover nights from before you started running it — for
those, Polar's own account export is still the only source.

### `.claude/`

Adapt museflow's `.claude/agents/` and `.claude/commands/`, dropping anything DB / migration /
provider-OAuth specific. Keep at least an `engineer`, a `python` and a `test` agent, and an
`add-tests` command.

### `ROADMAP.txt`

Remove what this build delivered; leave the future items seeded in phase 1.

---

## Acceptance criteria

```bash
make lint
make test

uv run polarexport --help
uv run polarexport night --help
uv run polarexport night --date-min 2026-08-09 --date-max 2026-08-16
tree data/ | head -30
unzip -l export/polarexport-nights-2026-08-09_2026-08-16.zip
```

Then verify by hand:
- **the store works** — re-run the same command with `-l DEBUG` and confirm no HTTP requests are made
  the second time;
- `--no-refresh` on the same range → archive built offline, no network;
- a range entirely outside the 28-day window → yellow warning, archive still produced from whatever
  `data/` holds, missing dates in `manifest.json → gaps`;
- re-running without `--force` → clean red error, exit 1, existing archive untouched;
- `--no-raw` → no `raw/` entries;
- `--source sleep --source recharge` → only those two fetched;
- an invalid token in `.env` → actionable message pointing at `docs/authentication.md`, and **the
  token is not printed**;
- `grep -r "$POLAR_ACCESS_TOKEN" data/ export/` → no matches.

Finally, the real acceptance test: attach a generated archive to a prompt asking an AI agent to
analyse the nights, and confirm it can interpret the data from the archive's `README.md` alone.
