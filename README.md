# polarexport

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Export your Polar night data — sleep, nightly recharge, skin temperature, SleepWise, continuous heart
rate — as a self-contained `.zip` archive you can hand to an AI agent for analysis.

## Why this exists

Polar's own account export takes **over a week** to be delivered. That is useless if you want to look
at last night's sleep today. polarexport pulls the same data straight from the Polar AccessLink API
and hands you an archive in seconds.

## How it works

```
Polar API ──sync──▶ data/ ──export──▶ export/*.zip
        (only what's missing)   (offline, local files only)
```

Every payload polarexport fetches is written to a local `data/` store and **never thrown away**.
Archives are built from that store, not from the API.

This matters because **Polar AccessLink v3 only retains the last 28 days** of sleep and recovery data.
A tool that fetches on demand could never show you more than a month. By keeping everything it has
ever seen, polarexport turns a rolling 28-day window into unbounded local history — run it once a
month and your archive grows forever.

> **Be clear-eyed about the limit:** this cannot recover nights from *before* you started running it.
> For those, Polar's own account export is still the only source. Start running it now and the problem
> solves itself going forward.

`data/` is the durable asset and worth backing up. `export/` is disposable — regenerate it any time.

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

The short version:

```bash
# 1. Authorize in a browser — open the printed URL, log in, accept.
#    You land on your redirect URI with ?code=... in the address bar.
python3 - <<'EOF'
import os, urllib.parse
print("https://flow.polar.com/oauth2/authorization?" + urllib.parse.urlencode({
    "response_type": "code",
    "client_id": os.environ["POLAR_CLIENT_ID"],
    "redirect_uri": os.environ["POLAR_REDIRECT_URI"],
    "scope": "accesslink.read_all",
}))
EOF

# 2. Exchange the code (valid 10 minutes, single use) for a token.
curl -sS -X POST 'https://polarremote.com/v2/oauth2/token' \
  -u "${POLAR_CLIENT_ID}:${POLAR_CLIENT_SECRET}" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=authorization_code' \
  -d "code=${CODE}" \
  -d "redirect_uri=${POLAR_REDIRECT_URI}"
# → {"access_token": "...", "expires_in": 473039999, "x_user_id": 12345678}

# 3. Register yourself with your application (409 = already done, that's fine).
curl -sS -X POST 'https://www.polaraccesslink.com/v3/users' \
  -H "Authorization: Bearer ${POLAR_ACCESS_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"member-id": "your-name"}'
```

Then put `POLAR_ACCESS_TOKEN` and `POLAR_USER_ID` in `.env`.

**Full walkthrough, including the browser step and a troubleshooting table:
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
| `--output-dir` | Where to write the archive. Defaults to `./export`. |
| `--force` | Overwrite an existing archive at the target path. |
| `--limit` | Export at most this many nights, most recent first. |

Worked examples:

```bash
polarexport night                                        # last 28 days
polarexport night --date-min 2026-06-01                  # older nights served from data/
polarexport night --no-refresh --date-min 2026-01-01     # offline, from the local store only
polarexport night --source sleep --source recharge       # subset of sources
```

### Keeping history

This is the section that earns the project its keep. Polar AccessLink only retains 28 days of sleep and
recovery data — run `polarexport night` **on a schedule** and `data/` accumulates nights forever, even
though Polar's own window never moves. A monthly cron entry is enough to never lose a night again:

```cron
# Refresh the local store on the 1st of every month at 06:00
0 6 1 * * cd /path/to/polarexport && uv run polarexport night --output-dir /dev/null >> polarexport.log 2>&1
```

(Writing the archive to `/dev/null` there is deliberate — the point of a scheduled run is feeding `data/`,
not producing an archive every time. Point `--output-dir` at a real directory when you actually want one.)

`data/` is the durable asset — back it up. `export/` is disposable — delete it and regenerate any time
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

## Claude Code

- `CLAUDE.md` — the always-loaded, distilled project rules
- `CONVENTIONS.md` — the long-form architecture and conventions reference
- `docs/plans/` — the phased implementation plan (`00-overview.md` first)
- `.claude/` — project agents and commands

## License

MIT — see [LICENSE](LICENSE).
