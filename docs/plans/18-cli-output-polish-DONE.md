# Phase 18 — CLI output polish

> Depends on: phases 15–17 (complete). Needs a Polar token: **no** — every item is reachable offline
> with `--no-refresh` and a hand-made `data/` directory.

## Where this came from

The 2026-08-19 review of phase 17. Phase 17 is correct and complete — all four items verified, plus
five malformed-file shapes I hadn't listed in the plan (a bare list, a scalar, an empty file, `null`,
a missing `schema_version`) all return `None` cleanly rather than raising. `make lint` clean,
`make test` green at 390 passed / 100 % branch coverage. `docs/runbook.md` is gone.

The regression that motivated phase 17 is fixed:

```
$ echo '{"schema_version": 2, "user": "x"}' > data/auth/credentials.json
$ polarexport night --limit 1
No Polar credentials found. Run `polarexport auth` to set them up, or see docs/authentication.md to do it by hand.
exit=1
```

But running that regression test surfaced a display bug in the layer underneath, which phase 17 had
no reason to look at. It is not a phase 17 defect — it has been there since phase 2 — but three of the
user-facing warnings added in phases 15 and 17 are the first things to make it visible.

---

## 1. Every warning and error is printed twice

`AppSettings.LOG_HANDLERS_CLI` defaults to `["cli", "cli_alert"]`. In `config/loggers.py`:

| Handler | Level | Formatter | Stream |
|---|---|---|---|
| `cli` | `DEBUG` | `message` (`%(message)s`) | stdout |
| `cli_alert` | `WARNING` | `default` (timestamp, level, module, line) | stdout |

Nothing caps `cli` below `WARNING`, so every record at `WARNING` or above matches **both** handlers
and is emitted twice to the same stream — once bare, once verbose. Phase 17's own new warning, on a
fresh clone:

```
Unsupported credentials schema_version 2, skipping
[2026-08-19 22:57:35] WARNING [polarexport...json_credentials._read_sync:101] Unsupported credentials schema_version 2, skipping
```

Phase 15's legacy-layout warning is three lines long, so it prints as six:

```
…/data/polar-accesslink-v3 is the pre-0.2 layout. Move it with:
  mkdir -p data/raw && mv data/polar-accesslink-v3 data/raw/
  mkdir -p data/export && mv export/*.zip data/export/
[2026-08-19 22:58:00] WARNING [polarexport…dependencies.get_night_store:58] …/data/polar-accesslink-v3 is the pre-0.2 layout. Move it with:
  mkdir -p data/raw && mv data/polar-accesslink-v3 data/raw/
  mkdir -p data/export && mv export/*.zip data/export/
```

**Why nobody noticed.** `.envrc` line 13 sets `POLAREXPORT_LOG_HANDLERS_CLI='["rich"]'` — a single
handler. Anyone with direnv active, which is how this repo has been developed throughout, never sees
it. The doubling only appears on a plain checkout without direnv, which is what an actual user has.
Reproduce it deliberately: `env -u POLAREXPORT_LOG_HANDLERS_CLI uv run polarexport night --no-refresh`
in a directory with a `data/polar-accesslink-v3/` in it.

**Fix.** The two handlers were meant to split the range, not overlap it: `cli` for ordinary messages,
`cli_alert` for warnings and above with enough detail to debug. Give `cli` an upper bound so the split
is real. Add a `logging.Filter` subclass to `infrastructure/config/loggers.py`:

```python
class MaxLevelFilter(logging.Filter):
    """Passes only records strictly below `level`, so a paired handler can own the rest."""

    def __init__(self, level: int) -> None:
        super().__init__()
        self._level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self._level
```

**Attach it conditionally, not statically.** This is the trap in this item: if the filter is baked
into the `cli` handler in `default_conf`, then a user running `POLAREXPORT_LOG_HANDLERS_CLI='["cli"]'`
gets `cli` alone with an upper bound and no handler above it — warnings and errors vanish entirely.
Silently losing errors is far worse than printing them twice.

So apply the filter in `configure_loggers`, on the deep-copied conf, only when **both** names are in
the requested handler list:

```python
if "cli" in handlers and "cli_alert" in handlers:
    # cli_alert owns WARNING and above; cap cli below it so the two don't overlap.
    conf["handlers"]["cli"]["filters"] = ["max_level_warning"]
```

`configure_loggers` already deep-copies `default_conf` and mutates it per call, so this fits the
function's existing shape.

Do not solve this by dropping `cli_alert` from the default — the detailed form is worth having on
warnings, and the bare form is worth having on INFO. Do not solve it by giving the two handlers
different streams either; that is item 2 and it is a separate decision.

## 2. Warnings go to stdout; errors go to stderr

Both `cli` and `cli_alert` write to `ext://sys.stdout`, while every `typer.secho` in the command
callbacks passes `err=True`. So diagnostics are split across streams by *mechanism* rather than by
severity:

```
$ polarexport night --no-refresh > out.txt      # warnings land in out.txt, errors on the terminal
$ polarexport night --no-refresh 2>/dev/null    # errors suppressed, warnings still printed
```

A user redirecting stdout to capture a report silently buries the 28-day retention warning and the
legacy-layout warning in the file.

**Fix.** Point `cli_alert` at `ext://sys.stderr` and leave `cli` on stdout. After item 1's filter,
that maps cleanly onto severity: `INFO` and below to stdout, `WARNING` and above to stderr, matching
the `typer.secho(..., err=True)` convention already used for fatal messages. Leave the `console`
handler on stdout — it is the single-handler debugging view and splitting it helps nobody.

Note that `history_window_warning` is printed with `typer.secho(..., fg=YELLOW)` and **no** `err=True`
(`commands/night.py`, just after the try/except). That one is deliberate — it is part of the report,
printed on the success path next to the Rich tables, not a diagnostic. Leave it on stdout. Do not
"fix" it for consistency.

## 3. Two missing-polish items in `night.py`

Both trivial, both in the block phase 17 already touched.

**A missing sentence separator.** `NoNightDataError` carries no trailing period, and the callback
concatenates onto it:

```
No night data found for 2026-07-23 to 2026-08-19 The local store has nothing for that range — try again without --no-refresh.
```

Phase 17's `DateRange.__str__` fixed the ugly part of this line (it used to read
`DateRange(date_min=datetime.date(2026, 7, 23), …)`), which is what made the missing period visible.
Add the period to the message raised in `application/use_cases/night_export.py`, not to the
concatenation in the callback — the sentence should terminate itself wherever it is caught.

**One `data/` that should be `data/raw/`.** Phase 17 updated the `ProviderRateLimitError` and
`httpx.RequestError` messages but not the non-401 `HTTPStatusError` branch:

```python
f"Polar returned HTTP {e.response.status_code} even after retries. Nights already "
"fetched are saved in data/ — try again later.",
```

Make it `data/raw/` to match its two neighbours.

---

## Files

| File | Change |
|---|---|
| `polarexport/infrastructure/config/loggers.py` | add `MaxLevelFilter`; attach to `cli`; `cli_alert` → stderr |
| `polarexport/application/use_cases/night_export.py` | terminate the `NoNightDataError` message with a period |
| `polarexport/infrastructure/entrypoints/cli/commands/night.py` | `data/` → `data/raw/` in the non-401 branch |

## Tests

- `tests/unit/infrastructure/config/test_loggers.py` — `MaxLevelFilter` passes `INFO`, blocks `WARNING`
  and `ERROR`; `configure_loggers(handlers=["cli", "cli_alert"])` produces a `cli` handler carrying the
  filter and a `cli_alert` handler on `sys.stderr`.
- An integration test is what actually pins item 1: emit one `logger.warning` through the real
  configured handlers with `capsys`, and assert the message appears **exactly once** across
  `capsys.readouterr().out + .err`. A unit test on the filter alone would not have caught the original
  bug, since each handler is correct in isolation — it is the pair that is wrong.
- Assert the same warning lands on `.err` and not `.out`, for item 2.
- `tests/unit/application/use_cases/test_night_export.py` — the `NoNightDataError` message ends in `.`.

Watch the coverage gotcha: `[tool.coverage.run] source` includes `tests`, so do not add a fixture or
helper this phase does not exercise.

## Acceptance criteria

- `make lint` clean, `make test` green at 100 % branch coverage.
- With `POLAREXPORT_LOG_HANDLERS_CLI` **unset**, a legacy-layout `data/<api>/` directory produces the
  three-line warning exactly once, on stderr.
- `polarexport night --no-refresh > out.txt` leaves every warning on the terminal and `out.txt`
  holding only the report.
- The single-handler configurations (`["rich"]`, `["console"]`, `["cli"]`) still emit warnings — the
  filter must not swallow them when `cli_alert` is absent. **Test `["cli"]` alone explicitly**: it is
  the way to get item 1 wrong, it loses errors rather than duplicating them, and `.envrc`'s `["rich"]`
  means local runs would never reveal it.
