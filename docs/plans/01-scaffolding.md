# Phase 1 — Scaffolding & tooling

**Depends on:** nothing. **Needs a Polar token:** no.

## Goal

Stand up an empty but fully lint-and-test-green project mirroring museflow's tooling, minus every
database and web concern. At the end of this phase `make install`, `make lint` and `make test` all
succeed on a repository that contains no business logic yet.

## Reference — read these first

```
/home/yannick/Projects/PERSONAL/museflow/pyproject.toml
/home/yannick/Projects/PERSONAL/museflow/Makefile
/home/yannick/Projects/PERSONAL/museflow/docker-compose.yml
/home/yannick/Projects/PERSONAL/museflow/.pre-commit-config.yaml
/home/yannick/Projects/PERSONAL/museflow/.github/workflows/ci.yml
/home/yannick/Projects/PERSONAL/museflow/.envrc  .env.example  .gitignore  .claudeignore
/home/yannick/Projects/PERSONAL/museflow/CLAUDE.md  CONVENTIONS.md  README.md  ROADMAP.txt
/home/yannick/Projects/PERSONAL/museflow/tests/conftest.py  tests/CLAUDE.md
```

Copy them, replacing `museflow` → `polarexport` and `MUSEFLOW_` → `POLAREXPORT_`.

---

## Files to create

### `pyproject.toml`

```toml
[project]
name = "polarexport"
version = "0.1.0.dev0"
description = "Export your Polar night data as a shareable zip archive."
requires-python = ">=3.13"
license = { text = "MIT" }
authors = [{ name = "Yannick Chabbert", email = "yannick.chabbert.it@gmail.com" }]

dependencies = [
    "pydantic>=2.13.4",
    "pydantic-settings>=2.14.2",
    "typer>=0.26.8",
    "rich>=15.0.0",
    "httpx>=0.28.1",
    "tenacity>=9.1.4",
]

[project.scripts]
polarexport = "polarexport.infrastructure.entrypoints.cli.main:app"
```

**Removed vs museflow:** `fastapi`, `starlette`, `sqlalchemy`, `alembic`, `asyncpg`, `argon2-cffi`,
`pyjwt`, `rapidfuzz`, `unidecode`, `ijson`, `pyyaml`, `pydantic-core`; `pydantic[email]` → `pydantic`.

`[dependency-groups]` — museflow's `test` group verbatim (`pytest`, `pytest-cov`, `pytest-env`,
`pytest-httpx`, `pytest-reverse`, `pytest-xdist[psutil]`, `coverage[toml]`, `polyfactory`,
`time-machine`) and its `dev` group minus `types-pyyaml`.

`[tool.hatch.build.targets.wheel] packages = ["polarexport"]` and `[tool.bumpversion]` as museflow's
with `current_version = "0.1.0.dev0"`.

**`[tool.ruff]`** — copy verbatim (119, `py313`, `fix = true`, `select = ["E","F","I","UP","B","PERF","FURB"]`).
- `ignore = ["E501"]`. Drop `B008` for now; if ruff flags it on the phase-8 Typer options, re-add it then.
- isort: keep `force-single-line`, `known-first-party = ["polarexport"]`, `known-local-folder = ["tests"]`:
  ```toml
  section-order = ["future", "standard-library", "httpx", "pydantic", "third-party", "first-party", "local-folder"]
  sections.httpx = ["httpx"]
  sections.pydantic = ["pydantic", "pydantic_settings"]
  ```
  (drop the `sqlalchemy` section; rename `fastapi` → `httpx`).

**`[tool.mypy]`** — `python_version = "3.13"`, `files = ["polarexport", "tests"]`,
`plugins = "pydantic.mypy"`. Drop the `ijson` override.

**`[tool.pytest.ini_options]`**
```toml
junit_family = "legacy"
addopts = [
    "--dist=loadgroup",
    "--cov=polarexport", "--cov-report=xml", "--cov-report=term-missing",
    "--cov-report=html", "--cov-branch", "--junitxml=junit.xml",
]
testpaths = ["tests"]
pythonpath = ["."]
env = [
    'POLAREXPORT_LOG_LEVEL_CLI=DEBUG',
    'POLAREXPORT_LOG_HANDLERS_CLI=["null"]',
    # Polar credentials — 'D:' means "default, only if not already set", so live runs can override
    'D:POLAR_ACCESS_TOKEN=dummy-access-token',
    'D:POLAR_USER_ID=00000000',
    # WireMock
    'WIREMOCK_POLAR_ADMIN_URL=http://localhost:8081',
    'WIREMOCK_POLAR_BASE_URL=https://localhost:8444',
]
filterwarnings = ["always"]
```
`--dist=loadgroup` is kept because WireMock integration tests are pinned to one xdist worker.

**`[tool.coverage]`** — museflow's blocks verbatim with `source = ["polarexport", "tests"]`,
`branch = true`, `fail_under = 100`. Drop `concurrency = ["thread", "greenlet"]` (no greenlet without
SQLAlchemy).

### `Makefile`

Copy museflow's, keeping `.DEFAULT_GOAL := help`, the awk self-doc target and the section banners.

- **Keep:** Help, Dependencies, Versioning, Testing, Local Development — verbatim, with
  `museflow tests` → `polarexport tests`.
- **Delete:** the entire Database section.
- **Docker section** — keep, reduced to WireMock only:
  ```make
  .PHONY: ps logs up up-wiremock down restart reload reset
  up: up-wiremock
  up-wiremock:  ## Start the WireMock container
  	docker compose up --detach --wait wiremock-polar
  down: ## Stop containers
  	docker compose down --remove-orphans
  ```
  plus `ps`, `logs`, `restart`, `reload`, `reset` as in museflow.
- **App section:** `run: ## Show the CLI help` → `uv run polarexport --help`. Delete `app-shell`.
- **Testing:**
  ```make
  test: up-wiremock ## Run all the testsuite
  	uv run pytest ./tests -n auto --dist=loadgroup || ($(MAKE) down && exit 1)
  	@$(MAKE) down

  test-unit: ## Run unit tests (no Docker required)
  	uv run pytest ./tests/unit -n auto --dist=loadgroup -v

  test-integration: up-wiremock ## Run integration tests
  	uv run pytest ./tests/integration -n auto --dist=loadgroup -v || ($(MAKE) down && exit 1)
  	@$(MAKE) down
  ```

### `docker-compose.yml`

One service, modelled on museflow's `wiremock-spotify`:

```yaml
services:
  wiremock-polar:
    image: wiremock/wiremock:3.12.0
    container_name: polarexport-wiremock
    ports:
      - "8081:8080"
      - "8444:8443"
    volumes:
      - ./tests/assets/wiremock/polar:/home/wiremock
    command: ["--verbose", "--https-port", "8443", "--global-response-templating"]

networks:
  polarexport-network:
    driver: bridge
```

No `db`, no `migration`, no `app` service. Create `tests/assets/wiremock/polar/__files/.gitkeep` and
`tests/assets/wiremock/polar/mappings/.gitkeep`; phase 5 fills them.

### `.pre-commit-config.yaml`

Copy verbatim; change both `files: (museflow|tests)` patterns to `(polarexport|tests)`.

### `.github/`

- `workflows/ci.yml` — copy verbatim. `make test` brings WireMock up itself via docker compose, which
  works on `ubuntu-latest` without extra setup.
- `workflows/dependabot-auto-merge.yml`, `dependabot.yml` — copy verbatim.

### Dotfiles

- `.gitignore` — museflow's, dropping `external_data` and **adding `/export` and `/data`**.
- `.claudeignore` — caches/coverage/IDE/build, plus `/export`, `/data`, and
  `tests/assets/wiremock/` (heavy).
- `.dockerignore` — not needed (no app image), skip it.
- `.envrc` — direnv non-secret defaults (`COMPOSE_PROJECT_NAME`, `POLAREXPORT_LOG_LEVEL_CLI`,
  `POLAREXPORT_LOG_HANDLERS_CLI`), ending with `dotenv` to overlay `.env`.
- `.env.example`:
  ```bash
  # Non-secret defaults live in .envrc (loaded by direnv).
  # Only secrets and personal overrides belong here.
  #
  # See docs/authentication.md for how to obtain these — it matters that
  # CLIENT_ID != USER_ID and CLIENT_SECRET != ACCESS_TOKEN.

  # --- Required by polarexport ---
  POLAR_ACCESS_TOKEN=      # bearer token from the OAuth exchange
  POLAR_USER_ID=           # x_user_id from that same response

  # --- Only needed to re-run the auth flow ---
  POLAR_CLIENT_ID=         # Credentials tab at admin.polaraccesslink.com
  POLAR_CLIENT_SECRET=     # same place
  POLAR_REDIRECT_URI=http://localhost:8000/auth/polar/callback
  ```
- `LICENSE` — MIT, "Yannick Chabbert", 2026.
- `ROADMAP.txt` — plain-text scratch list, seeded with: `sport sessions export command`,
  `polarexport auth login (OAuth loopback on the registered redirect URI)`,
  `v4 API adapter (90-day window, richer hypnogram)`, `SUMMARY.md renderer in the archive`,
  `data/ compaction + integrity check command`.

### `README.md`

Write it **now**, not in phase 8 — the auth section is a prerequisite for phase 5 and the user needs
it before any data can be fetched. Sections:

1. **What & why** — Polar's own export takes over a week; this is fresh data in seconds.
2. **How it works** — the two-stage `API → data/ → export/*.zip` flow, and why the local store exists
   (28-day API window vs. unbounded local history). A small diagram.
3. **Requirements** — Python 3.13, uv, Docker (tests only), a Polar account and a registered client.
4. **Installation** — `make install`.
5. **Authentication** — a condensed walkthrough with real commands, linking to
   `docs/authentication.md` for the full version. **Must state plainly that `POLAR_CLIENT_ID` is not
   `POLAR_USER_ID` and `POLAR_CLIENT_SECRET` is not `POLAR_ACCESS_TOKEN`.**
6. **Usage** — placeholder; phase 8 fills in the CLI User Guide.
7. **Development** — `make lint`, `make test`, `make test-unit` (no Docker).
8. **Claude Code** — CLAUDE.md / CONVENTIONS.md / `.claude/` pointers.

`docs/authentication.md` already exists — do not rewrite it, link to it.

### `CLAUDE.md` and `CONVENTIONS.md`

Adapt museflow's. **Strip every** SQLAlchemy / repository / Alembic / FastAPI / PostgreSQL rule.
**Keep** the stack header, architecture diagram (updated to this tree), Domain Layer, Ports,
Application Layer, External API Adapters, CLI Entrypoints, Naming Conventions (drop the `user_db` row,
keep `_in` / `_dto`), Types & Style, Logging, Error Handling, Documentation, and the whole Testing
section (WireMock stays; "real DB" becomes "real store on `tmp_path`").

Add two project-specific sections:
- **Polar API** — the 28-day window; `404` is a gap, `403` marks a source unavailable; never log the
  token.
- **Local store** — `data/` holds raw payloads only; mapping happens at export time so archives can be
  rebuilt after a mapper fix.

Keep `CLAUDE.md` **small** — it is always loaded. Long prose goes in `CONVENTIONS.md`.

### Package & test skeleton

Every directory gets an `__init__.py`:

```
polarexport/
  domain/{entities,value_objects,services,utils}
  application/{inputs,ports/{providers,stores,archivers},use_cases}
  infrastructure/
    adapters/{providers/polar,stores,archivers}
    config/settings
    entrypoints/cli/commands
tests/{unit,integration}/<mirror>
tests/assets/polar/                      # raw JSON captures (phase 5)
tests/assets/wiremock/polar/{__files,mappings}
```

`tests/__init__.py`, `tests/CLAUDE.md` (short pointer file like museflow's), and `tests/conftest.py`:

- `pytest_addoption`: `--polar-live`.
- `pytest_configure`: register the `polar_live` and `wiremock` markers.
- `pytest_collection_modifyitems` (`@pytest.hookimpl(tryfirst=True)`): skip `polar_live` unless the
  flag is given, **and** assign `pytest.mark.xdist_group("wiremock")` to every `wiremock`-marked test.
  museflow's union-find helper handles multiple servers; we have one, so a single fixed group name is
  enough — simplify rather than copy.
- `anyio_backend` — `scope="session", autouse=True`, returns `"asyncio"`.
- `frozen_time` — `time_machine` pinned to `datetime(2026, 1, 1, tzinfo=UTC)`, `tick=False`.
- The `configure_logging` fixture arrives in **phase 2** (`configure_loggers` doesn't exist yet).

Also port museflow's `tests/integration/utils/wiremock.py` helper for driving the WireMock admin API;
adapt it to the single Polar server.

### Coverage bootstrap

`fail_under = 100` fails on an empty codebase. Create a minimal `polarexport/__init__.py`
(`PROJECT_DIR`, `BASE_DIR`, `__project_name__`, `__version__` — phase 2 owns anything more) plus
`tests/unit/test_package.py` asserting both metadata values are non-empty.

### Git

The directory is **not yet a repository**. `git init`, default branch `main`, one initial commit.
Do not push.

---

## Acceptance criteria

```bash
make install          # succeeds; creates uv.lock, installs pre-commit hooks
make lint             # zero findings
make test-unit        # green (no Docker needed)
make test             # green at 100 % coverage; brings WireMock up and down
make precommit        # all hooks pass
docker compose up --detach --wait wiremock-polar && docker compose down   # WireMock starts clean
git log --oneline     # one initial commit on main
```

**deptry note:** it will flag declared-but-unused dependencies at this stage. Resolve it by declaring
each dependency only when a phase first imports it (`httpx`/`tenacity` in phase 2, `rich` in phase 8) —
**not** by adding per-rule ignores.
