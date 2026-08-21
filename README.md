# polarexport

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![CI](https://github.com/ychab/polarexport/actions/workflows/ci.yml/badge.svg)](https://github.com/ychab/polarexport/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ychab/polarexport/graph/badge.svg)](https://codecov.io/gh/ychab/polarexport)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

Export your Polar night data and training sessions — sleep, nightly recharge, skin temperature,
SleepWise, continuous heart rate, exercises with heart-rate zones and derived intensity — as
self-contained `.zip` archives you can hand to an AI agent for analysis.

## Why this exists

Polar's own account export takes **over a week** to be delivered. That is useless if you want to look
at last night's sleep today. polarexport pulls the same data straight from the Polar AccessLink API
and hands you an archive in seconds.

## How it works

```
Polar API ──sync──▶ data/raw/ ──export──▶ data/export/polarexport-nights-*.zip
        (only what's missing)   (offline, local files only)   data/export/polarexport-exercises-*.zip
```

Every payload polarexport fetches is written to a local `data/` store and **never thrown away**.
Archives are built from that store, not from the API.

This matters because **Polar AccessLink v3 only retains the last 28 days** of sleep and recovery data
(30 for exercises — see the `exercise` section below). A tool that fetches on demand could never show
you more than a month. By keeping everything it has ever seen, polarexport turns a rolling window into
unbounded local history — run it once a month and your archive grows forever.

> **Be clear-eyed about the limit:** this cannot recover nights or sessions from *before* you started
> running it. For those, Polar's own account export is still the only source. Start running it now and
> the problem solves itself going forward.

`data/` is the durable asset and worth backing up. `data/export/` is disposable — regenerate it any time.

## Requirements

- Python 3.13 and [uv](https://github.com/astral-sh/uv)
- Docker (only for running the integration test suite)
- A Polar account and a client registered at [admin.polaraccesslink.com](https://admin.polaraccesslink.com)

## Installation

```bash
make install
```

This creates the virtualenv, installs all dependency groups and sets up the pre-commit hooks.

## Configuration

Copy `.env.example` to `.env` and fill it in. Non-secret defaults live in `.envrc` (loaded
automatically by [direnv](https://direnv.net/)); `.env` holds only secrets and personal overrides.

`POLAR_CLIENT_ID`, `POLAR_CLIENT_SECRET` and `POLAR_REDIRECT_URI` are *inputs to `polarexport auth`*
(below), not just stored for reference — get them from the Credentials tab at
[admin.polaraccesslink.com](https://admin.polaraccesslink.com) and register a redirect URI there
before running it. The access token and user id are written by that command into
`data/auth/credentials.json`, not `.env` — you never type them in by hand.

## Authentication

One-time setup. The resulting access token is effectively permanent — Polar's docs state that access
tokens *"will not expire unless explicitly revoked"*.

**The single most common mistake:** the client credentials are not the user credentials.

| Value | From | Identifies |
|---|---|---|
| `POLAR_CLIENT_ID` | Credentials tab at admin.polaraccesslink.com | your **application** |
| `POLAR_CLIENT_SECRET` | same place | your **application** |
| `POLAR_ACCESS_TOKEN` | the OAuth token exchange | your **account's grant** to that app |
| `POLAR_USER_ID` | `x_user_id` in that same response | your **account** |

`POLAR_CLIENT_ID` is **not** `POLAR_USER_ID`. `POLAR_CLIENT_SECRET` is **not** `POLAR_ACCESS_TOKEN`.
Only the bottom two are used at export time.

```bash
polarexport auth --member-id your-name
```

This opens your browser, catches the redirect, exchanges the code, registers your account, and writes
the access token and user id to `data/auth/credentials.json` — no manual `curl`. Pass `--no-browser`
on a headless machine to print the authorization URL instead.

**Full walkthrough, including the manual fallback and a troubleshooting table:
[`docs/authentication.md`](docs/authentication.md).**

## Usage

### Global options

```bash
polarexport --help
polarexport --version
polarexport --log-level DEBUG --log-handlers console night ...   # verbose, human-readable
```

| Option | Description |
|---|---|
| `--log-level`, `-l` | `DEBUG` / `INFO` / `WARNING` (default) / `ERROR` / `CRITICAL` |
| `--log-handlers` | Repeatable. `cli` (plain), `cli_alert` (default, warnings+ only), `console`, `rich`, `null` |
| `--version`, `-v` | Print the version and exit |

### `auth` — authorize against your Polar account

```bash
polarexport auth --help
```

| Option | Description |
|---|---|
| `--member-id` | Stable identifier for you within your app. Defaults to your Polar user id. |
| `--client-id` | Defaults to `POLAR_CLIENT_ID`. |
| `--client-secret` | Defaults to `POLAR_CLIENT_SECRET`; prompted (hidden) if neither is set. |
| `--redirect-uri` | Defaults to `POLAR_REDIRECT_URI`. Must match the admin console exactly. |
| `--credentials-file` | Where to write credentials. Defaults to `data/auth/credentials.json`. |
| `--no-browser` | Print the authorization URL instead of launching a browser (headless / SSH). |
| `--timeout` | Seconds to wait for the callback. Defaults to 300, minimum 10. |
| `--force` | Overwrite credentials already present at `--credentials-file`. |

### `night` — export your night data

```bash
polarexport night --help
```

| Option | Description |
|---|---|
| `--date-min`, `-f` | First night to export (`YYYY-MM-DD`). Defaults to 27 days ago. |
| `--date-max`, `-t` | Last night to export (`YYYY-MM-DD`). Defaults to today. |
| `--source` | Repeatable: `sleep`, `recharge`, `skin-temperature`, `sleepwise`, `heart-rate`, or `all` (default). |
| `--refresh` / `--no-refresh` | Fetch missing nights from Polar first (default), or build the archive offline from `data/` only. |
| `--force-refresh` | Re-fetch nights already present in `data/`. Requires `--refresh`. |
| `--with-raw` / `--no-raw` | Include the untouched Polar payloads under `raw/` in the archive (default: included). |
| `--output-dir` | Where to write the archive. Defaults to `data/export`. |
| `--force` | Overwrite an existing archive at the target path. |
| `--limit` | Export at most this many nights, most recent first. |

Worked examples:

```bash
polarexport night                                        # last 28 days
polarexport night --date-min 2026-06-01                  # older nights served from data/
polarexport night --no-refresh --date-min 2026-01-01     # offline, from the local store only
polarexport night --source sleep --source recharge       # subset of sources
```

### `exercise` — export your training sessions

```bash
polarexport exercise --help
```

| Option | Description |
|---|---|
| `--date-min`, `-f` | First session to export (`YYYY-MM-DD`). Defaults to 29 days ago. |
| `--date-max`, `-t` | Last session to export (`YYYY-MM-DD`). Defaults to today. |
| `--sport` | Repeatable, matched against `detailed_sport_info` (e.g. `kickboxing-martial-arts`); open vocabulary, or `all` (default). |
| `--refresh` / `--no-refresh` | Fetch sessions from Polar first (default), or build the archive offline from `data/` only. |
| `--force-refresh` | Re-fetch sessions already present in `data/raw/`. Requires `--refresh`. |
| `--with-raw` / `--no-raw` | Include the untouched Polar payloads under `raw/` in the archive (default: included). |
| `--with-samples` / `--no-samples` | Include the per-minute heart-rate curve (default: included). |
| `--output-dir` | Where to write the archive. Defaults to `data/export`. |
| `--force` | Overwrite an existing archive at the target path. |
| `--limit` | Export at most this many sessions, most recent first. |

`GET /v3/exercises` has **no date filter** and retains **30 days**, not the nights' 28 — see
[`docs/api-vs-account-export.md`](docs/api-vs-account-export.md) for what that means for a sync.

Worked examples:

```bash
polarexport exercise                                             # last 30 days
polarexport exercise --sport kickboxing-martial-arts --no-raw    # one sport, no raw payloads
polarexport exercise --no-refresh --force                        # rebuild offline from data/
```

Real output, run against a store holding three sessions:

```
                                         Export
┌───────────────────┬──────────────────────────────────────────────────────────┐
│ Metric             │ Value                                                    │
├───────────────────┼──────────────────────────────────────────────────────────┤
│ Sessions Exported  │ 3                                                        │
│ Total Duration     │ 3h 40m                                                   │
│ Total Calories     │ 1945                                                     │
│ Availability       │ available                                                │
│ Archive            │ data/export/polarexport-exercises-2026-08-17_2026-08-20.zip │
│ Size               │ 7.3 KB                                                   │
└───────────────────┴──────────────────────────────────────────────────────────┘
                                         By Sport
┌─────────────────────────┬──────────┬────────────────┬────────────────┬──────────────────┐
│ Sport                   │ Sessions │ Total Duration │ Total Calories │ Mean Cardio Load │
├─────────────────────────┼──────────┼────────────────┼────────────────┼──────────────────┤
│ Kickboxing Martial Arts │        1 │         1h 27m │            786 │             81.2 │
│ Walking                 │        1 │         1h 10m │            633 │             45.2 │
│ Aerobics                │        1 │         1h 02m │            526 │             38.3 │
└─────────────────────────┴──────────┴────────────────┴────────────────┴──────────────────┘
Archive written to data/export/polarexport-exercises-2026-08-17_2026-08-20.zip
```

### Keeping history

This is the section that earns the project its keep. Polar AccessLink only retains 28 days of sleep and
recovery data (30 for exercises) — run `polarexport night` and `polarexport exercise` **on a schedule**
and `data/` accumulates history forever, even though Polar's own window never moves. A monthly cron
entry is enough to never lose a night or a session again:

```cron
# Refresh the local store on the 1st of every month at 06:00
0 6 1 * * cd /path/to/polarexport && uv run polarexport night --output-dir /dev/null >> polarexport.log 2>&1
5 6 1 * * cd /path/to/polarexport && uv run polarexport exercise --output-dir /dev/null >> polarexport.log 2>&1
```

(Writing the archive to `/dev/null` there is deliberate — the point of a scheduled run is feeding `data/`,
not producing an archive every time. Point `--output-dir` at a real directory when you actually want one.)

`data/` is the durable asset — back it up. `data/export/` is disposable — delete it and regenerate any time
from whatever `data/` holds, with `--no-refresh` if you want that regeneration to touch the network at all.

### The workflow it was built for

Generate an archive, attach the `.zip` to a prompt, and ask an AI agent to review the nights — the
archive's own `README.md` (generated inside it) is enough context for the agent to interpret `nights.json`
without you explaining the schema by hand.

```bash
polarexport night --date-min 2026-08-01 --date-max 2026-08-16
```

> Attached: `polarexport-nights-2026-08-01_2026-08-16.zip`. Read its `README.md` first, then look at
> `nights.json`. How has my sleep quality trended over these two weeks, and does anything in the nightly
> recharge or continuous heart-rate data explain the worst night?

### Limits

This covers a rolling 28-day API window plus whatever history you've already accumulated locally. It
**cannot retroactively recover nights from before you started running it** — for those, Polar's own
account export (which can take over a week) is still the only source. Start running `polarexport` now and
the problem solves itself going forward.

## Development

```bash
make lint         # ruff + mypy + deptry
make test         # full suite at 100% branch coverage (starts WireMock via Docker)
make test-unit    # unit tests only, no Docker required
make help         # every available target
```

Coverage is enforced at 100% branch coverage by `pytest --cov-fail-under`; the badge reports the
figure, the build enforces it.

## Claude Code

- `CLAUDE.md` — the always-loaded, distilled project rules
- `CONVENTIONS.md` — the long-form architecture and conventions reference
- `docs/plans/` — the phased implementation plan (`00-overview.md` first)
- `.claude/` — project agents and commands

## License

MIT — see [LICENSE](LICENSE).
