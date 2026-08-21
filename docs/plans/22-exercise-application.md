# Phase 22 — Exercise application layer

**Depends on:** phase 21 (the entities and services this layer moves around).
**Needs a Polar token:** no. Ports are abstract; use cases are tested with `AsyncMock`.
**Size:** medium. One commit.

## Where this came from

Same request as phase 21. This phase defines the contracts — what the provider, the store and the
mapper must do — and the two use cases that orchestrate them. Phases 23 and 24 implement the ports.

### The one thing that is genuinely different from `night`

`night` is **date-addressed**: the use case computes which dates are missing, then asks the provider
for exactly those. `GET /v3/exercises` has no date filter and no pagination — one request returns
every session uploaded in the last 30 days, samples and zones included. So the exercise sync inverts:

```
night:     store.missing(dates)  ->  provider.fetch(missing_dates)  ->  store.write(each)
exercise:  provider.fetch()      ->  store.known_ids()              ->  store.write(new only)
```

Deduplication happens **after** the fetch, on `id`, not before it on dates. Do not try to force the
night shape onto this — a `missing()` method on the exercise store would have nothing to filter on.

A consequence worth stating: `--force-refresh` on the exercise command does not save or cost a single
request. The request is the same either way; the flag only decides whether already-stored payloads
get overwritten. Say that in the option's help text.

## 1 — Ports

`application/ports/providers/exercise.py`:

```python
@dataclass(frozen=True, kw_only=True)
class ExerciseFetchResult:
    payloads: Mapping[str, dict[str, Any]]  # keyed by exercise id
    availability: SourceAvailability
    request_count: int


class ExerciseProviderPort(ABC):
    """A port for fetching raw Polar training-session data."""

    @abstractmethod
    async def fetch_exercises(self, *, with_samples: bool, with_zones: bool) -> ExerciseFetchResult:
        """Fetch every training session Polar still holds.

        Polar returns whatever is inside its rolling retention window with no way to narrow the
        request; date filtering is the caller's job, applied to the result. Returns raw payloads, not
        entities — the store keeps them verbatim so archives can be rebuilt after a mapper change.

        Args:
            with_samples: Request the per-second sample series (`?samples=true`).
            with_zones: Request the heart-rate zone breakdown (`?zones=true`).

        Returns:
            The raw payloads keyed by exercise id, the availability observed, and the request count.

        Raises:
            ProviderRateLimitError: Rate limits were still exceeded after retries.
        """
        ...
```

There is no `payload: None` case here, unlike `NightStorePort`. "Polar was asked and had nothing" is
expressed by an empty mapping for the whole fetch, not per-id — an id only exists because Polar
returned a session for it.

`application/ports/providers/profile.py` — `ProfileProviderPort.fetch_profile() -> dict[str, Any] | None`.
Separate port: a profile is not a training session, and one client implementing both is fine.

`application/ports/stores/exercise.py`:

```python
@dataclass(frozen=True, kw_only=True)
class StoredExercise:
    id: str
    date: date          # local start date, used for the on-disk path and for range reads
    fetched_at: datetime
    api: str
    payload: dict[str, Any]


class ExerciseStorePort(ABC):
    async def write(self, stored: StoredExercise) -> None: ...
    async def read(self, date_range: DateRange) -> Mapping[str, StoredExercise]: ...
    async def known_ids(self) -> frozenset[str]: ...
    async def write_availability(self, availability: SourceAvailability, *, observed_at: datetime) -> None: ...
    async def read_availability(self) -> SourceAvailability | None: ...
```

Every method needs a Google-style docstring — ports are public interfaces. Note `known_ids()` takes no
range: an id is unique across the whole store and the sync has no date context to narrow by.

`application/ports/stores/profile.py` — `ProfileStorePort.write(StoredProfile)` / `.read() -> StoredProfile | None`.
The profile must be stored, not fetched at export time: `--no-refresh` has to build a complete archive
offline, and that includes the manifest's profile block.

`application/ports/mappers/exercise.py` — `ExerciseMapperPort.to_exercises(payloads) -> tuple[Exercise, ...]`
and `to_profile(payload) -> UserProfile | None`. Mirrors `NightMapperPort`: mapping happens at export
time so a mapper fix applies retroactively to sessions already on disk.

## 2 — Inputs

`application/inputs/exercise.py`, Pydantic, `frozen=True`:

```python
class ExerciseSyncInput(BaseModel):
    with_samples: bool = True   # needed for minimum heart rate and the per-minute curve
    with_zones: bool = True     # free on the same request
    force_refresh: bool = False


class ExerciseExportInput(BaseModel):
    date_range: DateRange
    sports: frozenset[str] = frozenset()   # empty = every sport
    include_raw: bool = True
    include_samples: bool = True           # the per-minute curve in exercises.json
    output_dir: Path
    force: bool = False
    limit: int | None = Field(default=None, ge=1)
```

`ExerciseSyncInput` carries no date range on purpose — there is nothing to filter a fetch by. Add a
comment saying so, or the next reader will "fix" it.

`sports` filters on `detailed_sport_info` **case-insensitively**, matching either the raw Polar token
(`KICKBOXING_MARTIAL_ARTS`) or a friendlier form (`kickboxing-martial-arts`). Normalise both sides —
upper-case and swap `-` for `_` — inside the export use case. Do not add a validator that rejects
unknown sports: Polar's vocabulary is open and a typo'd filter yielding an empty archive with a clear
message beats a hard failure on a sport that genuinely exists.

## 3 — `ExerciseSyncUseCase`

`application/use_cases/exercise_sync.py`. A class — it holds injected ports and takes per-run args.

```python
class ExerciseSyncUseCase:
    def __init__(
        self,
        exercise_provider: ExerciseProviderPort,   # DI params contiguous
        profile_provider: ProfileProviderPort,
        exercise_store: ExerciseStorePort,
        profile_store: ProfileStorePort,
    ) -> None: ...

    async def sync(self, sync_in: ExerciseSyncInput, *, today: date) -> ExerciseSyncReport: ...
```

Flow:

1. `fetch_exercises(with_samples=..., with_zones=...)`.
2. `write_availability(result.availability, observed_at=now)` — always, on every real fetch, same as
   the night sync. This is what lets a later export tell "consent missing" from "nothing recorded".
3. `known = await store.known_ids()` unless `force_refresh`, in which case treat it as empty.
4. Write every payload whose id is not in `known`. Count `fetched` and `skipped`.
5. Fetch and store the profile. A profile failure must **not** fail the sync — log a warning and
   carry on with `profile_fetched=False`. Sessions are the point; the profile is context.

`ExerciseSyncReport` is a new frozen dataclass in `domain/entities/exercise_export.py`:
`fetched`, `skipped`, `requests`, `availability`, `profile_fetched`.

A `403` surfaces as `SourceAvailability.UNAVAILABLE` from the provider, not as an exception — the
client already owns that policy for nights and phase 23 extends it here.

## 4 — `ExerciseExportUseCase`

`application/use_cases/exercise_export.py`:

```python
class ExerciseExportUseCase:
    def __init__(
        self,
        exercise_store: ExerciseStorePort,
        profile_store: ProfileStorePort,
        exercise_mapper: ExerciseMapperPort,
        exercise_archiver: ExerciseArchiverPort,
    ) -> None: ...

    async def export(
        self, export_in: ExerciseExportInput, *, today: date, generated_at: datetime
    ) -> ExerciseExportReport: ...
```

Flow:

1. `read(export_in.date_range)` — the store filters by date on the way out, since the fetch could not.
2. Map to entities.
3. Filter by `sports` when non-empty.
4. Sort by `start_time` ascending, then apply `limit` keeping the **most recent** (`[-limit:]`),
   matching what `night` does.
5. Raise `NoExerciseDataError` when nothing survives — a new exception in `domain/exceptions.py`,
   sibling to `NoNightDataError`. Message must use `DateRange.__str__`, which phase 17 added, and end
   with a period; when a sport filter was applied, say so, because "no data" and "no data *for that
   sport*" send the user to completely different places.
6. Emit the 30-day warning via `is_outside_history_window(..., window_days=POLAR_EXERCISE_WINDOW_DAYS)`
   — **30, not 28**. Warn and proceed, exactly as `night` does: the local store may hold older
   sessions even though Polar no longer serves them.
7. Build the manifest, including totals and the per-sport breakdown from `exercise_summary`, and the
   profile from `profile_store.read()` (`None` when never synced — not an error).
8. When `include_samples` is `False`, strip `heart_rate_per_minute` before archiving. Do this by
   passing the flag to the archiver, not by mutating entities — they are frozen and the mapper's
   output is the truth.
9. Archive, return the report.

Use cases never print and never touch the filesystem directly. Both of these hold ports and take
per-run args, so both are classes.

## Files

| File | Change |
|---|---|
| `polarexport/application/ports/providers/exercise.py` | new |
| `polarexport/application/ports/providers/profile.py` | new |
| `polarexport/application/ports/stores/exercise.py` | new |
| `polarexport/application/ports/stores/profile.py` | new |
| `polarexport/application/ports/mappers/exercise.py` | new |
| `polarexport/application/ports/archivers/exercise.py` | new — `ExerciseArchiverPort` |
| `polarexport/application/inputs/exercise.py` | new |
| `polarexport/application/use_cases/exercise_sync.py` | new |
| `polarexport/application/use_cases/exercise_export.py` | new |
| `polarexport/domain/entities/exercise_export.py` | add `ExerciseSyncReport` |
| `polarexport/domain/exceptions.py` | add `NoExerciseDataError` |

## Tests

Unit only in this phase — there is no real collaborator to integrate against until phases 23 and 24.
`AsyncMock` for every port.

Cover, at minimum:

- Sync writes only unknown ids: provider returns three ids, store knows one, exactly two writes.
- `force_refresh=True` writes all three even though the store knows one, and issues the same number
  of provider calls — assert the call count is unchanged, since that is the non-obvious part.
- `write_availability` is called on every sync, including one that writes nothing new.
- A profile fetch raising does not fail the sync: sessions are still written, `profile_fetched` is
  `False`, and a warning is logged.
- Export raises `NoExerciseDataError` when the store is empty, and separately when the store has data
  but the `sports` filter excludes all of it — assert the two messages differ.
- `sports` matching is case- and separator-insensitive: `{"kickboxing-martial-arts"}` selects a
  session whose `detailed_sport_info` is `KICKBOXING_MARTIAL_ARTS`.
- `limit` keeps the most recent sessions, not the oldest.
- `include_samples=False` reaches the archiver as `False` and the entities are untouched.
- The history-window warning fires at 31 days and not at 29 — the boundary that proves 30 is wired,
  not 28. This is the test that catches a copy-paste from the night use case.

## Acceptance criteria

- Nothing in `application/` imports from `infrastructure/`.
- Every port method carries a Google-style docstring.
- The 30-day window is used for exercises everywhere, and nights still use 28.
- `make lint` clean, `make test` green at 100 % branch coverage.
