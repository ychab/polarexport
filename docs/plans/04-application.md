# Phase 4 — Application layer

**Depends on:** phase 3. **Needs a Polar token:** no.

## Goal

Define the ports the infrastructure will implement, the input schemas, and the two use cases that
drive the pipeline. This layer depends **only** on `polarexport.domain`.

## Reference — read these first

```
/home/yannick/Projects/PERSONAL/museflow/museflow/application/ports/repositories/users.py   # canonical ABC docstrings
/home/yannick/Projects/PERSONAL/museflow/museflow/application/ports/providers/library.py
/home/yannick/Projects/PERSONAL/museflow/museflow/application/use_cases/user_create.py      # function-style use case
/home/yannick/Projects/PERSONAL/museflow/museflow/application/use_cases/history_import.py   # class-style use case
/home/yannick/Projects/PERSONAL/museflow/museflow/application/inputs/history.py
```

---

## The pipeline this layer describes

```
NightSyncUseCase :  Polar API ──▶ data/         (fetch only what's missing, store raw)
NightExportUseCase: data/ ──▶ map ──▶ merge ──▶ export/*.zip
```

**Raw payloads are what get stored.** Mapping to entities happens on the export side, so a mapper fix
can be applied retroactively to nights already on disk. Keep that separation strict: the sync path
never constructs a domain entity, and the export path never touches the network.

---

## `application/inputs/night.py`

Two schemas, both `model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)`
(`DateRange` is a domain dataclass, not a Pydantic model).

```python
class NightSyncInput(BaseModel):
    date_range: DateRange
    sources: frozenset[NightSource] = frozenset(NightSource)
    force_refresh: bool = False     # re-fetch dates already present in the store
    limit: int | None = Field(default=None, ge=1)


class NightExportInput(BaseModel):
    date_range: DateRange
    sources: frozenset[NightSource] = frozenset(NightSource)
    include_raw: bool = True
    output_dir: Path
    force: bool = False             # overwrite an existing archive
    limit: int | None = Field(default=None, ge=1)
```

Field order mirrors the CLI option order: **filters → processing config → cap**. Validate that
`sources` is non-empty.

---

## Ports

### `application/ports/providers/night.py`

```python
@dataclass(frozen=True, kw_only=True)
class SourceFetchResult:
    payloads: Mapping[date, dict[str, Any] | None]   # None = Polar reported no data for that date
    availability: SourceAvailability
    request_count: int


class NightProviderPort(ABC):
    @abstractmethod
    async def fetch(self, source: NightSource, dates: Sequence[date]) -> SourceFetchResult:
        """Fetch raw payloads for one source over the given dates.

        Returns raw API payloads, not domain entities — the store keeps them verbatim so that
        archives can be rebuilt after a mapper change.

        Raises:
            PolarRateLimitError: Rate limits were still exceeded after retries.
        """
```

A single `fetch(source, dates)` method rather than five `fetch_sleep` / `fetch_recharge` / … methods:
the caller iterates over `NightSource`, and adding a source later never widens the port. The adapter
dispatches internally.

`dict[str, Any]` is the one justified `Any` in this codebase — an unmodelled payload is the whole
point. Note that in a comment.

### `application/ports/stores/night.py`

```python
@dataclass(frozen=True, kw_only=True)
class StoredPayload:
    source: NightSource
    date: date
    fetched_at: datetime
    api: str                          # "polar-accesslink-v3"
    payload: dict[str, Any] | None    # None = Polar had no data for this night


class NightStorePort(ABC):
    @abstractmethod
    async def write(self, stored: StoredPayload) -> None: ...

    @abstractmethod
    async def read(self, source: NightSource, date_range: DateRange) -> Mapping[date, StoredPayload]: ...

    @abstractmethod
    async def missing(self, source: NightSource, dates: Sequence[date], *, today: date) -> tuple[date, ...]:
        """Return the dates that still need fetching.

        A date already stored with a payload is never re-fetched. A date stored as empty is
        re-fetched only while it remains inside the Polar retention window, since a device may
        sync late; once the date falls outside the window the empty verdict is final.
        """
```

### `application/ports/mappers/night.py`

```python
class NightMapperPort(ABC):
    @abstractmethod
    def to_sleep(self, payload: Mapping[str, Any]) -> Sleep: ...
    @abstractmethod
    def to_nightly_recharge(self, payload: Mapping[str, Any]) -> NightlyRecharge: ...
    @abstractmethod
    def to_skin_temperature(self, payload: Mapping[str, Any]) -> SkinTemperature: ...
    @abstractmethod
    def to_sleepwise(self, payload: Mapping[str, Any]) -> SleepWise: ...
    @abstractmethod
    def to_continuous_heart_rate(self, payload: Mapping[str, Any]) -> ContinuousHeartRate: ...
```

This port exists because the export use case reads raw payloads from the store and must turn them into
entities without the application layer importing the Polar adapter. `StoredPayload.api` records which
mapper produced-shape a payload has, so a future v4 adapter ships its own mapper for its own stored
files.

### `application/ports/archivers/night.py`

```python
class NightArchiverPort(ABC):
    @abstractmethod
    async def write(
        self,
        nights: Sequence[Night],
        manifest: ExportManifest,
        raw: Mapping[NightSource, Mapping[date, dict[str, Any]]],
        *,
        output_dir: Path,
        include_raw: bool,
        force: bool,
    ) -> Path:
        """Write the export archive and return its path.

        Raises:
            ArchiveAlreadyExistsError: The target archive exists and ``force`` is False.
        """
```

---

## `application/use_cases/night_sync.py`

```python
class NightSyncUseCase:
    def __init__(self, night_provider: NightProviderPort, night_store: NightStorePort) -> None: ...

    async def sync(self, sync_in: NightSyncInput, *, today: date) -> SyncReport: ...
```

Flow:
1. Truncate the range to the most recent `limit` dates **before** any request — the cap exists to avoid
   the requests, not to trim the results.
2. Per requested source: `missing()` unless `force_refresh`, in which case take every date.
3. Nothing missing → skip the provider entirely for that source (assert this in tests with
   `assert_not_awaited()`).
4. `fetch()` the missing dates, `write()` each result (including the `None` payloads — recording
   "Polar had nothing" is what stops the endless re-fetch).
5. Log a warning if `date_range.date_min` is outside the retention window; **never raise** — the store
   may already hold those nights.
6. Return a `SyncReport`: per-source fetched / skipped / empty counts, availability, request counts,
   and the window warning.

The sync use case does **no** mapping and **no** archiving.

## `application/use_cases/night_export.py`

```python
class NightExportUseCase:
    def __init__(
        self,
        night_store: NightStorePort,
        night_mapper: NightMapperPort,
        night_archiver: NightArchiverPort,
    ) -> None: ...

    async def export(self, night_in: NightExportInput, *, today: date, generated_at: datetime) -> ExportReport: ...
```

DI parameters contiguous in `__init__`. `today` and `generated_at` are injected so the window check and
the manifest timestamp are testable without freezing the clock.

Flow:
1. `read()` each requested source from the store over the range. **No network access at all.**
2. Map non-empty payloads to entities via `night_mapper`. A payload that fails to map is logged as a
   warning and skipped — one malformed night must not sink the whole export.
3. `merge_nights(...)` from `domain.services.night_merger`.
4. Zero nights with any data → raise `NoNightDataError`.
5. Build the `ExportManifest` (tool name/version from `polarexport.__project_name__` / `__version__`,
   `generated_at`, availability, gaps, window warning).
6. `await self._night_archiver.write(...)` and return the `ExportReport` with the path and
   `Path.stat().st_size`.

Neither use case prints anything or touches the filesystem directly.

---

## Tests

All unit, all `AsyncMock` ports — `tests/unit/application/{inputs,ports,use_cases}/` mirroring source.

`NightSyncUseCase` branches:
- everything missing → all fetched and written;
- nothing missing → provider never awaited;
- `force_refresh` → provider awaited even for stored dates;
- a source returning `UNAVAILABLE` → recorded, other sources still synced;
- a source not in `sources` → never fetched;
- `limit` → the truncated date list reaches the provider (assert on call args);
- `date_min` outside the window → warning via `caplog`, sync proceeds;
- an empty payload → written as `payload=None`.

`NightExportUseCase` branches:
- all sources present → nights merged, archive written, report returned;
- store empty for every date → `NoNightDataError`;
- one payload failing to map → warning logged, that night still exported from its other sources;
- `ArchiveAlreadyExistsError` propagates unchanged;
- `include_raw=False` → passed through to the archiver.

Input schemas: empty `sources` rejected, `limit=0` rejected, defaults correct.

No integration tests here — ABCs have no behaviour, and `@abstractmethod` is already in the coverage
`exclude_lines`.

---

## Acceptance criteria

```bash
make lint
make test
grep -rE "^(from|import) (httpx|typer|rich|tenacity|zipfile)" polarexport/application/   # prints nothing
```
