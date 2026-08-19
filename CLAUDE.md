# polarexport Project Guidelines

## Stack & Tools
- **Python:** 3.13 managed by `uv`
- **Frameworks:** Typer (CLI), Pydantic v2, pydantic-settings
- **HTTP:** httpx (async), tenacity (retry logic)
- **Formatter/Linter:** Ruff (line length 119), mypy (strict), deptry
- **Test:** pytest + pytest-cov, polyfactory, pytest-httpx, WireMock
- **Storage:** plain files — no database

## Commands
- `make install` — install deps + pre-commit hooks
- `make lint` — format + type check + dependency check
- `make test` — all tests with 100% branch coverage (starts WireMock)
- `make test-unit` — unit tests only, no Docker required
- `make run` — show the CLI help
- `make up` / `make down` — Docker (WireMock)

## What this tool does

Fetches night data from the Polar AccessLink API, accumulates raw payloads in a local `data/` store,
and builds shareable `.zip` archives in `data/export/`.

```
Polar API ──sync──▶ data/raw/ ──export──▶ data/export/*.zip
        (only what's missing)   (offline, local files only)
```

**Scope:** two commands, `auth` and `night`. `auth` authorizes polarexport against a Polar account and
writes `.env`; `night` syncs and exports night data. Sport sessions and other metrics are out of
scope — the architecture makes them a drop-in later, but do not implement them.

## Architecture: Clean / Hexagonal

```
polarexport/
├── domain/          # Pure Python — NO framework imports ever
│   ├── entities/    # frozen dataclasses (Night, Sleep, NightlyRecharge, …)
│   ├── value_objects/  # DateRange, SleepStages
│   ├── services/    # night_merger
│   ├── utils/       # pure functions (date helpers)
│   ├── exceptions.py
│   ├── enums.py     # all StrEnum / IntEnum definitions
│   ├── const.py     # all domain constants
│   └── types.py     # type aliases only
├── application/     # Orchestration — depends ONLY on domain
│   ├── use_cases/   # night_sync, night_export
│   ├── inputs/      # Pydantic command/input schemas
│   └── ports/       # ABC interfaces (providers, stores, mappers, archivers)
└── infrastructure/  # Implements ports
    ├── adapters/
    │   ├── providers/polar/  # AccessLink client, DTOs, mappers
    │   ├── stores/           # filesystem night store
    │   ├── archivers/        # zip archiver
    │   └── http.py           # shared HttpClientMixin
    ├── config/settings/      # Pydantic settings (POLAREXPORT_, POLAR_)
    └── entrypoints/cli/      # Typer commands + dependencies
```

## Domain Layer

### Entities
```python
@dataclass(frozen=True, kw_only=True)
class Sleep:
    date: date
    stages: SleepStages

    def __post_init__(self) -> None:
        # Business rules and validation only.
        # Permanent computed fields: object.__setattr__ (frozen dataclass workaround)
        ...
```
- NO framework imports. No `httpx`, no `pydantic`, no `typer`, no filesystem.
- Business rules and validation only in `__post_init__`.
- **Dynamic fields**: use `@property`.
- Use tuples, not lists, for collections inside frozen dataclasses.
- **Every field Polar may omit is `X | None`.** `None` means "not reported by the device" and must
  stay distinguishable from `0`.

### Ports (Interfaces)
```python
class NightStorePort(ABC):
    @abstractmethod
    async def read(self, source: NightSource, date_range: DateRange) -> Mapping[date, StoredPayload]: ...
```
- Use `abc.ABC` + `@abstractmethod`. Ports are public interfaces — docstrings required.
- Ports live in `application/ports/`, never in `domain/`.

## Application Layer (Use Cases)

**Default — standalone async function.** **Class with a named method** when the use case holds
injected dependencies and is called with per-run args (both use cases here are classes):

```python
class NightExportUseCase:
    def __init__(
        self,
        night_store: NightStorePort,      # DI params contiguous
        night_mapper: NightMapperPort,
        night_archiver: NightArchiverPort,
    ) -> None: ...

    async def export(self, night_in: NightExportInput, *, today: date) -> ExportReport: ...
```
- Accept ports via parameters (DI). NEVER instantiate adapters inside use cases.
- Accept Input Schemas, return Domain Entities.
- Use cases never print and never touch the filesystem directly.

## Infrastructure Layer

### External API Adapters (Polar)
- **DTOs**: Pydantic models matching the external API shape exactly. `extra="allow"` so a new Polar
  field never breaks an export.
- **Mappers**: standalone functions `to_domain_sleep(dto) -> Sleep`, wrapped by a port implementation.
- **Transport returns raw payloads, not entities.** The provider's job is transport; interpretation
  happens at export time.

### Local store
- `data/` is the single root: `raw/` (accumulating payloads), `export/` (generated archives), `auth/`
  (credentials — see below).
- `data/raw/` holds **raw payloads only**, never mapped entities. Mapping happens at export time so a
  mapper fix can be applied retroactively to nights already on disk.
- Layout: `data/raw/<api>/<source>/<YYYY>/<MM>/<YYYY-MM-DD>.json` with a provenance envelope
  (`fetched_at`, `api`, `source`, `date`, `schema_version`, `payload`).
- `payload: null` records "Polar was asked and had nothing" — that is what stops endless re-fetching.
- All writes are atomic (temp file in the same directory + `Path.replace()`).
- `data/auth/credentials.json` holds the bearer token and its provenance (`obtained_at`,
  `expires_in`) — state the tool produces, not configuration the user authors. `.env` holds only
  `POLAR_CLIENT_ID` / `POLAR_CLIENT_SECRET` / `POLAR_REDIRECT_URI` and log config.

### CLI Entrypoints
- Each Typer command is a thin sync wrapper that calls `asyncio.run()` on a co-located async function.
- Name the async helper `<command>_logic` — never a `_`-prefixed private name.
- **Output belongs in the callback, not the logic function.** `*_logic` returns data and raises
  exceptions; it never calls `typer.secho`, `typer.echo` or `console.print`. The `@app.command`
  callback owns all user-visible output.
- **CLI option ordering:** filters first, then processing config, then cap (`--limit`).

## Polar API rules
- **28-day window.** AccessLink v3 retains only the last 28 days of sleep / nightly-recharge /
  sleepwise. A `--date-min` older than that logs a warning and **still proceeds** — the local store
  may already hold those nights.
- `404` on a date → that night has **no data**. Record a gap. Not an error.
- `403` on a source → consent missing. Mark the source unavailable and continue with the others.
- `429` / `5xx` / network → retried by `HttpClientMixin`'s tenacity policy.
- **Never log the access token**, never put it in an exception message, and never write it into
  `data/raw/`, an archive, or a manifest. The one file that may hold it is `data/auth/credentials.json`,
  mode 0600.

## Naming Conventions
| Suffix | Meaning | Type |
|--------|---------|------|
| `sleep` | Domain Entity | frozen dataclass |
| `sleep_in` | Input Schema (command) | Pydantic BaseModel |
| `sleep_dto` | External API DTO | Pydantic BaseModel |

## Types & Style
- 100% strict type hints everywhere — including tests. Native union: `str | None`.
- No `Any` unless justified. The one justified `Any` is `dict[str, Any]` for raw Polar payloads.
- Ruff line length: 119. Async everywhere.
- **Group function parameters by logical role** — input schemas first, then ports. Keep each group
  contiguous.

## Logging
```python
logger = logging.getLogger(__name__)

logger.info(f"Fetched {count} nights", extra={"count": count, "source": source})
logger.warning(f"No data for {day}", extra={"date": str(day)})

# Exception blocks — static message + extra (traceback carries the error detail)
logger.exception("Polar API error", extra={"status_code": e.response.status_code})
```
- Levels: ERROR (unrecoverable), WARNING (handled unexpected), INFO (milestones, minimal), DEBUG (flow).
- NEVER log secrets. Log the user id and endpoint, never the token.
- Exception blocks: static message + `extra={}`.

## Error Handling
- Domain exceptions live in `polarexport/domain/exceptions.py` — use these across all layers.
- Adapter-specific exceptions (e.g. `PolarNotFoundError`) live in their adapter package.
- In tenacity retry adapters, `_is_retryable_error()` must explicitly `return False` for all
  non-retriable exceptions.
- **Never use `assert` in production code.** Raise `ValueError` at the top for contract violations.

## Documentation
- No docstrings for obvious functions. Only for: public ports/ABCs, complex algorithms,
  non-obvious `Raises:`.
- Format: Google Style. Don't duplicate types from the signature.

## Testing

### Philosophy
Tests are the **contract with our users** — clean, clear, easy to maintain, not just 100% coverage.

- **100% branch coverage** is mandatory.
- **Integration tests** are the primary focus — full flows with WireMock and a real store on `tmp_path`.
- **Unit tests** fill gaps — error branches and edge cases hard to reach via integration.
- **Do not mirror happy paths** — if integration covers the nominal flow, no unit test for the same.
- **Error paths belong in unit tests** — use `AsyncMock` ports.
- **All test code is typed** — fixtures, functions, factories, helpers.
- **No inner imports in test functions** — all imports at module level.

### Test File Mirror
One test file per source file — never consolidate:
```
polarexport/application/use_cases/night_export.py
→ tests/unit/application/use_cases/test_night_export.py
→ tests/integration/application/use_cases/test_night_export.py
```

### Fixture Rules
- `scope="session"` for expensive shared setup (logging).
- `scope="function"` (default) for everything that touches state.
- `autouse=True` only for fixtures every test in scope needs.
- `request.param` for parametrized fixtures — never module-level `_make_*` helpers.
- **Never `with mock.patch(...)` inside a test method** — always a `pytest.fixture` instead.

### CLI Command Tests
Each command: 3 unit classes (`TestXParserCommand`, `TestXCommand`, `TestXLogic`) + 1 integration
`TestXLogic` (happy-path only).

### Factories
- `DataclassFactory` → domain entities | `ModelFactory` → Pydantic | `TypedDictFactory` → TypedDicts.
- Never create module-level helper functions (`_make_*`, `_build_*`).

### Special Markers
- `@pytest.mark.polar_live` — requires `--polar-live`, hits the real Polar API
- `@pytest.mark.wiremock` — required on any integration class using WireMock (prevents xdist flakiness)

### Coverage gotcha
`[tool.coverage.run] source` includes `tests`, so **unused test helpers and skipped test bodies count
as uncovered**. Introduce a fixture, helper or live test only in the phase that actually exercises it,
and add `omit` entries for opt-in live tests when they land.
