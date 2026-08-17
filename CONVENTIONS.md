# polarexport Coding Conventions & Architecture

## 1. Architecture Overview

This project follows **Clean Architecture (Hexagonal)** principles.

- **Domain (`polarexport/domain`)**: Entities as pure Python dataclasses (`frozen=True`). The "truth"
  of the system — what a night *is*, independent of Polar or of any file format.
- **Application (`polarexport/application`)**: Orchestrates the pipeline. Depends ONLY on domain.
  Holds the Ports (`abc.ABC` interfaces), the Input Schemas, and the Use Cases.
- **Infrastructure (`polarexport/infrastructure`)**: Implements the details — the Polar HTTP client,
  the filesystem store, the zip archiver, the Typer CLI.

### The pipeline

```
NightSyncUseCase  :  Polar API ──▶ data/          (fetch only what's missing, store raw)
NightExportUseCase:  data/ ──▶ map ──▶ merge ──▶ export/*.zip
```

Two properties fall out of this split and both are load-bearing:

1. **The store holds raw payloads, not entities.** Mapping happens on the export side. A mapper bug
   found in six months can be fixed and every past archive rebuilt from data already on disk.
2. **Export never touches the network.** `--no-refresh` is a genuinely offline operation and needs no
   access token at all.

### Why a local store exists

Polar AccessLink v3 retains only the **last 28 days** of sleep, nightly recharge and SleepWise data
(v4 would give 90 — still not history). A tool that fetches on demand can therefore never show more
than a month of nights. Never throwing a fetched night away turns a rolling window into unbounded
local history. `data/` is the durable asset; `export/` is disposable.

## 2. Coding Rules by Layer

### Domain Layer

#### A. Entities (`polarexport/domain/entities/`)
- **Technology**: `@dataclass(frozen=True, kw_only=True)`.
- **Immutability**: read-only after creation. Use tuples, not lists, for collections.
- **Validation**: business rules ONLY, in `__post_init__`. No transport or storage concerns.
- **Computed fields**: `__post_init__` + `object.__setattr__` for permanent ones, `@property` for
  dynamic ones.
- **Optionality is meaningful**: every field Polar may omit is `X | None`. `None` = "the device did
  not report this", which is not the same as `0`. Never invent a default for a physiological value.
- **No framework imports, ever.** Not `httpx`, not `pydantic`, not `typer`, not `pathlib` I/O.

#### B. Input Schemas / Commands (`polarexport/application/inputs/`)
- **Technology**: `pydantic.BaseModel` (v2), frozen.
- **Purpose**: define data entering the application (`NightSyncInput`, `NightExportInput`).
- **Validation**: strict validation happens here.
- **Field order** mirrors the CLI option order: filters → processing config → cap.

#### C. Ports (`polarexport/application/ports/`)
- **Technology**: Abstract Base Classes (`abc.ABC`), bodies are `...`.
- **Docstrings required** — these are the public interfaces of the application.
- Accept Input Schemas / primitives, return Domain Entities or transport-neutral results.
- Four ports: `NightProviderPort` (fetch raw), `NightStorePort` (persist raw),
  `NightMapperPort` (raw → entity), `NightArchiverPort` (entities → zip).

### Application Layer (Use Cases)
- **Structure**: standalone async functions by default; a **class** when the use case holds injected
  dependencies and is called with per-run args. Both use cases here are classes.
- **Dependency Injection**: accept Ports as constructor arguments. DO NOT instantiate adapters inside
  use cases. **DI parameters must be contiguous** — never scatter a port between operation flags.
- **No side channels**: use cases never print and never touch the filesystem directly.

### Infrastructure Layer

#### A. External APIs (Polar AccessLink)
- **DTOs**: Pydantic models matching the *external* API shape exactly. Same names, same nesting, no
  renaming. `model_config = ConfigDict(extra="allow")` so a new Polar field never breaks an export.
- **Mappers**: standalone functions (`to_domain_sleep(dto) -> Sleep`), wrapped by the port
  implementation. Complex transformation — timezone parsing, unit normalisation, hypnogram decoding —
  belongs here, not in the entity.
- **Transport is not interpretation**: the client returns untouched `dict` payloads. DTO parsing
  happens on the mapping side.
- **Status policy**: `404` → gap (not an error). `403` → source unavailable, continue with the rest.
  `429`/`5xx`/network → retried by tenacity. Implement it once in a private `_get` helper.

#### B. Local store
- Layout: `data/<api>/<source>/<YYYY>/<MM>/<YYYY-MM-DD>.json`. The API identity is the top level so a
  future v4 store sits alongside without migration. Month partitioning keeps the tree browsable by
  hand — the user is expected to inspect and trust this directory.
- Every file carries a provenance envelope: `schema_version`, `api`, `source`, `date`, `fetched_at`,
  `payload`.
- **Writes are atomic**: temp file in the same directory, then `Path.replace()`. An interrupted run
  must never leave a truncated JSON file — a corrupt night is worse than a missing one.
- A file that fails to parse is logged as a warning and skipped, never deleted.

#### C. Archives
- The archive is the product. Its legibility to an AI agent is the design constraint.
- `manifest.json` + `README.md` + `nights.json` + optional `raw/<source>/<date>.json`.
- The bundled `README.md` must let a reader interpret `nights.json` without consulting Polar's docs:
  units, scales, the meaning of `null`, and the retention caveat.
- Written to a temp file then atomically moved, same reasoning as the store.

## 3. General Python Standards
- **Python Version**: target **Python 3.13**.
- **Formatting**: Ruff (line length 119), `force-single-line` imports.
- **Typing**:
  - **Strict type hints** for ALL arguments and return values, including tests.
  - Native union syntax: `str | None`.
  - No `Any` unless justified. The one justified case is `dict[str, Any]` for an unmodelled Polar
    payload — annotate why in a comment.
- **Naming**:
  - `sleep` = Domain Entity (dataclass)
  - `sleep_in` = Input Schema (Pydantic)
  - `sleep_dto` = External API DTO (Pydantic)
  - Trailing underscore for keyword collisions (`list_.py`, `import_.py`)

## 4. Logging Strategy

### Philosophy: "Signal over Noise"
- **Goal**: logs are for operators and developers, not for storing data.
- **Privacy**: **NEVER** log secrets. The Polar access token must not appear in a log line, an
  exception message, a stored file, or an archive. Log the user id and the endpoint instead.

### Log Levels
- **ERROR**: cannot recover. Include a stack trace via `logger.exception` inside catch blocks.
- **WARNING**: unexpected but handled. Rate limit hit, a night that failed to map, a `--date-min`
  outside the retention window, a corrupt file in the store.
- **INFO**: high-level milestones. Keep it minimal.
- **DEBUG**: low-level flow. Rate-limit headers, per-request detail.

### Best Practices
- **Logger**: `logger = logging.getLogger(__name__)`.
- **f-strings in messages**: always allowed — they produce the human-readable message.
- **Structured context**: add `extra={}` when the data would be useful to query (dates, counts,
  source names). Not required for every line — use judgement.
- **Exception blocks**: static message, variable data in `extra={}`. The traceback carries the detail.
  - **Bad**: `logger.exception(f"Polar error: {e}")`
  - **Good**: `logger.exception("Polar API error", extra={"status_code": e.response.status_code})`

## 5. Documentation & Comments

### Philosophy: "Signal over Noise"
- **Code is the documentation**: descriptive names and strict type hints first.
- **Avoid redundancy**: no docstring that just repeats the function name.
- **Target audience**: public interfaces (Ports, ABCs) and complex logic where the "why" isn't
  obvious — the `missing()` retry rule and the heart-rate clipping in `night_merger` both qualify.

### Style Guide
- **Format**: **Google Style**.
- **Type Hints**: do NOT duplicate types in the docstring.
- **Content**: behaviour, non-obvious arguments, returns, and — crucially — `Raises:`.

## 6. Testing Strategy

### Philosophy
- **Coverage goal**: **100% branch coverage or nothing.** Every `if/else`, loop and exception path.
  Enforced by `fail_under = 100`.
- **Integration tests (`tests/integration`)**: primary focus. Real collaborators — WireMock for the
  Polar API, a real store on `tmp_path`, a real archiver.
- **Unit tests (`tests/unit`)**: gap filling. Error branches and edge cases hard to reach via
  integration, using `AsyncMock` ports.
- **Do not mirror happy paths** across both suites.

### Assertion Standards
- **Avoid loops** for assertions if `assert items == expected` works.
- If you must loop, include an identifier in the message so failures are debuggable.

### Fixtures & Factories
- **Technology**: `polyfactory`. `DataclassFactory` for entities, `ModelFactory` for Pydantic.
- Never create module-level `_make_*` / `_build_*` helpers — use a factory or a fixture.
- **Never `mock.patch` inside a test method** — always a fixture.

### Markers
- `@pytest.mark.wiremock` — **mandatory** on any integration class using WireMock. It pins the class
  to a single xdist worker so stub mappings don't race between parallel workers.
- `@pytest.mark.polar_live` — hits the real API, skipped unless `--polar-live` is passed.

### Coverage gotcha
`[tool.coverage.run] source` includes `tests`, which means test code is measured too — a real benefit
(it catches dead test helpers), with one sharp edge: **an unused fixture body or a skipped test body
counts as uncovered**. Introduce a helper only in the phase that exercises it, and add an `omit` entry
for opt-in live tests when they land.
