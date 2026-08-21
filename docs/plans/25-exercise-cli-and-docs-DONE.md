# Phase 25 — `exercise` command and documentation

**Depends on:** phases 21–24. This is the phase that makes the feature reachable.
**Needs a Polar token:** no for the suite; yes for the end-to-end verification at the bottom.
**Size:** medium-large. Two commits: command, then documentation.

## Where this came from

The user asked for the command to be called `exercise` rather than `activity`, because Polar's own
vocabulary reserves "activity" for daily step and calorie totals — a genuinely different dataset that
may become its own command later. `exercise` matches `/v3/exercises` and the payload's own wording.

## 1 — The command

`infrastructure/entrypoints/cli/commands/exercise.py`, modelled on `night.py`.

```
polarexport exercise [OPTIONS]

  # filters
  --date-min  -f  YYYY-MM-DD   default: today - 29 days
  --date-max  -t  YYYY-MM-DD   default: today
  --sport         NAME         repeatable; matches detailed_sport_info, case-insensitive

  # processing config
  --refresh / --no-refresh     fetch from Polar first (default: --refresh)
  --force-refresh              overwrite sessions already stored
  --with-raw / --no-raw        include raw/ payloads (default: --with-raw)
  --with-samples / --no-samples  include the per-minute heart-rate curve (default: --with-samples)
  --output-dir    PATH         default: data/export
  --force                      overwrite an existing archive

  # cap
  --limit         INT          export at most this many sessions, most recent first
```

Option order is filters → processing config → cap, per `CLAUDE.md`. The default `--date-min` is
`today - (POLAR_EXERCISE_WINDOW_DAYS - 1)` = 29 days back, **not** the night command's 27.

`--force-refresh` combined with `--no-refresh` is contradictory — reject it with
`typer.BadParameter`, exactly as `night` does.

`exercise_logic` is an async function called through `asyncio.run()` by a thin sync wrapper. It
**returns** `tuple[ExerciseSyncReport | None, ExerciseExportReport]` and prints nothing; every
`typer.secho`, every Rich table lives in the command callback. This rule has been enforced since
phase 8 and there is no reason to bend it here.

Output, mirroring `night`'s two tables:

- A **sync** table when `--refresh`: sessions fetched, skipped, requests, availability, whether the
  profile was refreshed.
- An **export** table always: sessions exported, total duration, total calories, the per-sport
  breakdown, archive path, size.

The per-sport breakdown is the interesting line for the user, so give it room — sport label, session
count, total duration, total calories, and mean cardio-load if present.

Error handling mirrors `night.py` exactly: `MissingCredentialsError`, `InvalidDateRangeError`,
`NoExerciseDataError`, `ArchiveAlreadyExistsError`, `ProviderRateLimitError` and `httpx.HTTPStatusError`
each map to a `typer.secho(..., fg=RED, err=True)` plus `raise typer.Exit(code=1) from e`.

**Move `_unauthorized_message()` out of `night.py` first.** Both commands need the expired-token
versus generic-401 distinction that phase 17 built, and copying it would mean the next fix lands in
one copy only. Put it in `cli/messages.py` and have `night.py` import it — `night.py`'s existing tests
must keep passing unchanged.

Where a message names the store, say `data/raw/` — phase 18 fixed the last of the bare `data/`
references and a new command should not reintroduce one.

## 2 — Parser and dependencies

`cli/parsers.py`: add `parse_sports(values: list[str] | None) -> list[str]`. Unlike `parse_sources`
it validates **nothing** against an enum — Polar's sport vocabulary is open. It normalises: strip,
upper-case, `-` → `_`, drop empties, and return `[]` for "no filter". `"all"` is accepted as an
explicit no-filter for symmetry with `--source`.

`cli/dependencies.py`: add `get_exercise_store()`, `get_profile_store()`, `get_exercise_mapper()`,
`get_exercise_archiver()`. Plain factory functions returning concrete adapters, like the night ones.
`get_polar_client()` is reused untouched — it already yields a client that now implements all three
provider ports.

`cli/main.py`: register it.

```python
app.command(name="exercise", help="Export training sessions as a zip archive")(exercise.exercise)
```

## 3 — Documentation

This is not a footnote — the feature is only usable if it is documented, and one existing statement
is now actively wrong.

**`CLAUDE.md`.** The "What this tool does" section says:

> **Scope:** two commands, `auth` and `night`. […] Sport sessions and other metrics are out of
> scope — the architecture makes them a drop-in later, but do not implement them.

Rewrite it for three commands and describe what `exercise` covers. Update the ASCII diagram to show
both archive kinds. Add the exercise entities to the domain layer description and note the 30-day
window alongside the 28-day one in the "Polar API rules" section — that section currently states the
28-day window as though it were universal, and a reader would apply it to exercises and be wrong.

**`README.md`.** Add `exercise` to the CLI User Guide with a worked example and real output. Update
the intro, which currently describes the tool as night-data-only. Keep the phase-20 badges intact.

**`docs/api-vs-account-export.md`.** Add a short section on training sessions. State what is known
and no more: `/v3/exercises` retains 30 days against the account export's multi-year history, the
route/GPS data is available via `?route=true` but deliberately not exported, and the per-second sample
series is stored locally but not archived. **Do not claim anything about what the account export
contains for exercises** — the 2026-08-20 audit only examined sleep and recovery files. Say the
exercise side has not been audited yet, and leave it as a known gap rather than inventing a
comparison.

Check whether `docs/authentication.md` claims the token's scope covers only night data; if it names
the sources, add exercises.

## 4 — Verification with a real token

```bash
uv run polarexport exercise --help
uv run polarexport exercise
uv run polarexport exercise --sport kickboxing-martial-arts --no-raw
uv run polarexport exercise --no-refresh --force
unzip -l data/export/polarexport-exercises-*.zip
```

Then confirm by hand, against the archive:

- `manifest.json` totals match the sum of `exercises.json`.
- A session's `heart_rate.minimum` is present and plausible — below `average`, above 40.
- `heart_rate_per_minute` has roughly `duration_seconds / 60` entries.
- No `-1.0` appears anywhere in `exercises.json`.
- No access token appears anywhere in the archive.
- The archive is mode `0600`.

## Files

| File | Change |
|---|---|
| `cli/commands/exercise.py` | new |
| `cli/messages.py` | new — `_unauthorized_message` moved out of `night.py` |
| `cli/commands/night.py` | import the moved helper |
| `cli/parsers.py` | add `parse_sports` |
| `cli/dependencies.py` | add four factories |
| `cli/main.py` | register the command |
| `CLAUDE.md` | scope, diagram, domain entities, both retention windows |
| `README.md` | intro + CLI User Guide |
| `docs/api-vs-account-export.md` | training-session section, honest about what is unaudited |

## Tests

Per the CLI convention: three unit classes plus one integration class.

`tests/unit/.../test_exercise.py`:

- `TestExerciseParserCommand` — `--date-min` rejects a bad date; `--sport` normalises
  `kickboxing-martial-arts` to `KICKBOXING_MARTIAL_ARTS`; `--sport all` yields no filter;
  `--force-refresh --no-refresh` raises `BadParameter`.
- `TestExerciseCommand` — each domain exception produces its message on **stderr** and exit code 1;
  the default date range spans 30 days, not 28 (the assertion that catches a copy-paste from
  `night.py`); `--no-refresh` builds no sync input.
- `TestExerciseLogic` — with `AsyncMock` use cases: `--no-refresh` skips the sync entirely; the
  logic function returns reports and writes nothing to stdout. Assert the no-print rule with
  `capsys`.

`tests/integration/.../test_exercise.py` — one happy path, `@pytest.mark.wiremock`, real store on
`tmp_path` and real archiver: sync then export, then open the resulting zip and assert
`exercises.json` holds the captured session with its derived minimum heart rate.

Also add an integration test that the access token appears nowhere in the exercise archive, mirroring
`test__access_token_never_appears_in_archive`. It is the rule most worth a belt-and-braces check.

## Acceptance criteria

- `uv run polarexport --help` lists three commands.
- `exercise_logic` prints nothing; the callback owns all output.
- `CLAUDE.md` no longer says sport sessions are out of scope.
- The 30-day window is used and documented; nights still use 28.
- `make lint` clean, `make test` green at 100 % branch coverage.
