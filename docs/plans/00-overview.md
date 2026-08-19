# polarexport — implementation overview

> **Read this file first.** Then execute `01` … `08` **in order**. One phase per agent session.
> Master plan (the "why"): `/home/yannick/.claude-personal/plans/effervescent-weaving-nest.md`

---

## Reference project — read it before writing any code

```
/home/yannick/Projects/PERSONAL/museflow
```

This is a working project by the same author and it is the **conventions source of truth**. Before
starting any phase:

1. Read `/home/yannick/Projects/PERSONAL/museflow/CLAUDE.md` (distilled rules, always-loaded)
2. Read `/home/yannick/Projects/PERSONAL/museflow/CONVENTIONS.md` (long-form architecture)
3. Read `/home/yannick/Projects/PERSONAL/museflow/tests/CLAUDE.md` and
   `/home/yannick/Projects/PERSONAL/museflow/.claude/agents/test.md` (testing process)
4. Open the specific museflow files your phase names and **copy their structure, naming and idioms**

Each phase file lists the exact museflow paths to crib from. When a phase says "copy from museflow",
copy the file verbatim and swap the package name — do not reinvent it.

---

## What we are building

A Python CLI that pulls **night data** from the Polar AccessLink API, accumulates it in a local
`data/` store, and builds self-contained `.zip` archives in `export/` — ready to attach to a prompt so
an AI agent can analyse the nights.

```
polarexport night --date-min 2026-07-20 --date-max 2026-08-16
→ data/polar/v3/<source>/<YYYY>/<MM>/<YYYY-MM-DD>.json   (accumulating cache)
→ export/polarexport-nights-2026-07-20_2026-08-16.zip     (the shareable artifact)
```

**Why not Polar's own account export?** It can take over a week to be delivered. This is fresh data in
seconds.

## Scope discipline

**Exactly one command ships: `night`.** Sport sessions and other metrics are explicitly out of scope.
The architecture must make them a drop-in later (a sibling module in `cli/commands/`), but **do not
implement them, do not add flags for them, do not add ports for them.**

---

## ⚠️ The 28-day wall, and why `data/` exists

Polar AccessLink v3 retains only the **last 28 days** of sleep / nightly-recharge / SleepWise data
(v4 would give 90 — still not history). A tool that fetches on demand can therefore never show you
more than a month of nights, ever.

**The fix is to never throw a fetched night away.** Every payload polarexport retrieves is written to
a local `data/` store, partitioned by source and date. The store only grows. Archives are built
**from the store**, not from the API. Run the command once a month and your local history becomes
unbounded, even though Polar's window never moves.

This makes the data flow two-stage:

```
Polar API ──sync──▶ data/  ──export──▶ export/*.zip
            (only what's missing)   (from local files only)
```

Consequences every phase must respect:
- The store holds **raw, untouched API payloads**, not mapped entities. If a mapper is improved later,
  every past archive can be rebuilt from data already on disk. This is the single most important
  design decision in the project.
- Each stored file carries a provenance envelope (`fetched_at`, `api`, `source`, `date`).
- A date that Polar reports as empty is recorded as such, so it isn't re-fetched forever — but only
  **outside** the 28-day window is that verdict final. Inside the window a device may still sync late.
- The default `--date-min` is `today - 27 days`; a `--date-min` older than that logs a **warning** and
  still proceeds, serving whatever the local store already holds.
- `--no-refresh` builds an archive entirely offline from `data/`.

## Locked decisions — do not re-litigate

| Topic | Decision |
|---|---|
| API | **Polar AccessLink v3 only** — `https://www.polaraccesslink.com` |
| Auth | Long-lived token in `.env`, obtained via `polarexport auth` (OAuth flow, phase 13) or by hand — see `docs/authentication.md`. |
| Local store | **`data/`** — the single root: `raw/` (accumulating payloads, partitioned by source and date), `export/` (archives), `auth/` (credentials) |
| Archives | **`data/export/`** — built from `data/raw/`, never directly from the API |
| Persistence | **`data/auth/credentials.json`** — the bearer token and its provenance, mode 0600. Not `.env`. |
| Database | **None.** No PostgreSQL, SQLAlchemy, Alembic, FastAPI. Plain files. |
| Test doubles | **WireMock** for integration (mirroring museflow) + `pytest-httpx` for unit status branches |
| Sources | sleep, nightly-recharge, skin-temperature, sleep-wise, continuous-heart-rate — all five |
| Python | 3.13, managed by `uv` |

## Environment variables

```
POLAR_ACCESS_TOKEN   # required — the bearer token; long-lived
POLAR_USER_ID        # required — the x_user_id from the token exchange
POLAR_CLIENT_ID      # stored for re-running the auth flow; unused at export time
POLAR_CLIENT_SECRET  # stored for re-running the auth flow; unused at export time
POLAR_REDIRECT_URI   # stored for re-running the auth flow; unused at export time
```

**`POLAR_CLIENT_ID` is not `POLAR_USER_ID`, and `POLAR_CLIENT_SECRET` is not `POLAR_ACCESS_TOKEN`.**
The client pair identifies the *application*; the token pair identifies the *user's grant to it*.
Full explanation and the exact `curl` commands: **`docs/authentication.md`**.

---

## Phase order

| # | Phase | Depends on | Real token? |
|---|---|---|---|
| 1 | Scaffolding & tooling | — | no |
| 2 | Config & shared infrastructure | 1 | no |
| 3 | Domain layer | 2 | no |
| 4 | Application layer — ports, inputs, use cases | 3 | no |
| 5 | Polar AccessLink adapter | 4 | **yes** |
| 6 | Local data store (filesystem adapter) | 4 | no |
| 7 | Zip archiver | 4 | no |
| 8 | CLI command & documentation | 5, 6, 7 | yes |

Phases 5, 6 and 7 are mutually independent and may be parallelised or reordered.

### Follow-up phases — from the 2026-08-18 review of the delivered code

Phases 1–8 are complete and green. These came out of reviewing the result; they are independent of
each other and none is a prerequisite for using the tool.

| # | Phase | Why | Real token? |
|---|---|---|---|
| 9 | Manifest fidelity | `manifest.json` reports fabricated `source_availability` and `request_counts` | no |
| 10 | CLI error handling gaps | rate limits, connection failures and 5xx reach the user as tracebacks | no |
| 11 | Layering cleanup & test-suite gaps | filesystem I/O in a use case, cross-adapter import, duplicated constant | no |

Phase 9 carries two decisions that must be made before implementing — read its "Decision required"
sections rather than guessing.

### Follow-up phases — from the 2026-08-18 review of phases 9-11

Phases 9-11 are complete and green. Phase 12 is a **hard prerequisite for phase 13**: the CLI
currently cannot start without the credentials that `polarexport auth` is meant to create.

| # | Phase | Why | Real token? |
|---|---|---|---|
| 12 | First-run bootstrap | `polarexport --version` crashes with a pydantic traceback on a checkout with no `.env` | no |
| 13 | `polarexport auth` | replaces the six manual steps in `docs/authentication.md` with one command | at the end |
| 14 | Consent fidelity | a 403 source is reported `no_data` in the manifest, indistinguishable from an empty night | no |

Phase 14 carries a decision that must be made before implementing. Phases 12 and 14 are small and
independent; 13 is the large one.

### Follow-up phases — from the 2026-08-19 review of phases 12-14

Phases 12-14 are complete and green. These two came out of that review plus an audit of the full
Polar account export (`polar-user-data-export.zip`, 4 881 files) against what `night` produces.
**Do 15 before 16** — 15 moves `data/`, and running them in the other order only creates conflicts.

| # | Phase | Why | Real token? |
|---|---|---|---|
| 15 | Credentials & storage layout | `auth` writes the bearer token into `.env`, the file the user hand-authors; `expires_in` is parsed and discarded | at the end |
| 16 | Night data fidelity | four things the API returns never reach `nights.json`; three dead fields ship as `null` in every night | yes |

Both decisions for phase 15 (credentials inside the data root; a single `data/` root) were made by
the user on 2026-08-19 and are recorded in the plan — do not re-open them.

### Follow-up phase — from the 2026-08-19 review of phases 15-16

Phases 15 and 16 are complete and green, and every phase-16 fidelity fix is verified against the real
store. Phase 17 collects four defects found around that work — one crash, three wrong messages.

| # | Phase | Why | Real token? |
|---|-------|-----|-------------|
| 17 | Credentials robustness | a malformed `credentials.json` escapes as a bare `KeyError`, against the port's own contract; `expires_in` is now stored but still unread; the 401 message points at `.env` | no |


## Definition of done — every phase

```bash
make lint     # ruff check + ruff format + mypy + deptry — zero findings
make test     # pytest — green, 100 % branch coverage (fail_under = 100)
```

Plus the phase's own acceptance criteria. If coverage is short, write the missing test — never lower
the threshold, never add a blanket `# pragma: no cover`.

## Non-negotiable conventions

Full detail in museflow's `CLAUDE.md`, and in this project's `CLAUDE.md` after phase 1.

- **Layering:** `domain/` (pure Python, zero framework imports) ← `application/` (depends only on
  domain) ← `infrastructure/` (implements ports). Never invert.
- **Every directory gets an `__init__.py`** — source and tests. No implicit namespace packages.
- **Ports** live in `application/ports/`, are `abc.ABC` + `@abstractmethod` with `...` bodies, and
  carry Google-style docstrings.
- **Entities** are `@dataclass(frozen=True, kw_only=True)`; validation only in `__post_init__`;
  computed permanent fields via `object.__setattr__`; dynamic values via `@property`.
- **Use cases** are standalone async functions by default; a class only when it holds injected
  dependencies. DI parameters contiguous. Never instantiate adapters inside a use case.
- **CLI:** each Typer command is a thin sync wrapper calling `asyncio.run()` on a co-located
  `<command>_logic` async function. **`*_logic` never prints** — it returns data or raises. The
  command callback owns every `typer.secho` and Rich table. Option order: filters → config → cap.
- **Types:** 100 % strict hints everywhere including tests. Native unions. No `Any` unless justified.
- **Logging:** `logger = logging.getLogger(__name__)`. f-strings fine for messages; exception blocks
  use a static message + `extra={}`. **Never log the access token.**
- **Errors:** domain exceptions in `domain/exceptions.py`; adapter-specific ones in the adapter
  package. **Never `assert` in production code.**
- **Docstrings:** only for public ports/ABCs, complex algorithms, non-obvious `Raises:`.
- **Tests:** one test file per source file, mirrored under `tests/unit/` and `tests/integration/`.
  Integration = real collaborators (WireMock, real store on `tmp_path`, real archiver). Unit = error
  branches with `AsyncMock` ports. Do not mirror happy paths across both. All test code typed. No
  inner imports. No `mock.patch` inside a test method — use a fixture.
