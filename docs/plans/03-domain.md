# Phase 3 — Domain layer

**Depends on:** phase 2. **Needs a Polar token:** no.

## Goal

Model a "night" as pure Python. No `httpx`, no `pydantic`, no `typer`, no filesystem — **zero framework
imports in `polarexport/domain/`**. Everything is a frozen, keyword-only dataclass with validation in
`__post_init__`.

## Reference — read these first

```
/home/yannick/Projects/PERSONAL/museflow/museflow/domain/entities/track.py
/home/yannick/Projects/PERSONAL/museflow/museflow/domain/value_objects/
/home/yannick/Projects/PERSONAL/museflow/museflow/domain/{enums,const,types,exceptions}.py
/home/yannick/Projects/PERSONAL/museflow/museflow/domain/services/reconciler.py
/home/yannick/Projects/PERSONAL/museflow/tests/unit/factories/entities/
```

---

## `domain/const.py`

```python
POLAR_HISTORY_WINDOW_DAYS: Final[int] = 28   # AccessLink v3 retention for sleep / recharge / sleepwise
EXPORT_DIR_NAME: Final[str] = "export"
ARCHIVE_NAME_TEMPLATE: Final[str] = "polarexport-nights-{date_min}_{date_max}.zip"
```

## `domain/enums.py`

- `NightSource(StrEnum)` — `SLEEP = "sleep"`, `RECHARGE = "recharge"`,
  `SKIN_TEMPERATURE = "skin-temperature"`, `SLEEPWISE = "sleepwise"`, `HEART_RATE = "heart-rate"`.
  These values are the `--source` CLI values **and** the `raw/<source>/` directory names — keep them
  identical so there is one vocabulary.
- `SleepStage(IntEnum)` — the hypnogram codes Polar returns. **Verify the real mapping in phase 5**
  against a live payload; seed with `WAKE`, `REM`, `LIGHT`, `DEEP` and add a comment that the numeric
  values are provisional until confirmed.
- `ContinuityClass(IntEnum)` and `NightlyRechargeStatus(IntEnum)` — likewise provisional; give each
  member a human label via a `label` property so the archive README can be generated from them.
- `SourceAvailability(StrEnum)` — `AVAILABLE`, `UNAVAILABLE` (403 / consent missing), `NOT_REQUESTED`.

## `domain/exceptions.py`

```python
class PolarExportError(Exception): ...

class InvalidDateRangeError(PolarExportError): ...
class NoNightDataError(PolarExportError): ...          # every requested date came back empty
class ArchiveAlreadyExistsError(PolarExportError): ...  # target zip exists and --force not given
```

Keep the hierarchy flat and small. Adapter-specific errors (`PolarNotFoundError`, …) belong in the
adapter package in phase 5, **not here**.

## `domain/types.py`

Type aliases only:
```python
Hypnogram = dict[str, int]                 # "HH:MM" -> SleepStage value, as Polar returns it
HeartRateSample = tuple[datetime, int]
SkinTemperatureSample = tuple[datetime, float]
AlertnessHour = tuple[int, str]
IsoDateStr = str
```

## `domain/value_objects/date_range.py`

```python
@dataclass(frozen=True, kw_only=True)
class DateRange:
    date_min: date
    date_max: date

    def __post_init__(self) -> None:
        if self.date_min > self.date_max:
            raise InvalidDateRangeError(...)

    @property
    def days(self) -> int: ...        # inclusive count
```

Add `def __iter__(self) -> Iterator[date]` or leave iteration to `utils/dates.iterate_dates` — pick
one, do not do both.

## `domain/value_objects/sleep_stages.py`

```python
@dataclass(frozen=True, kw_only=True)
class SleepStages:
    light_seconds: int
    deep_seconds: int
    rem_seconds: int
    unrecognized_seconds: int
```
Validation: every field `>= 0`. Properties: `total_seconds`, `total_hours`, and
`light_ratio` / `deep_ratio` / `rem_ratio` (guard division by zero — that guard is a **branch you must
cover**).

## `domain/entities/`

One file per entity. All `@dataclass(frozen=True, kw_only=True)`.

| File | Entity | Notable fields |
|---|---|---|
| `sleep.py` | `Sleep` | `date`, `sleep_start_time`, `sleep_end_time`, `stages: SleepStages`, `continuity`, `continuity_class`, `short_interruption_duration`, `long_interruption_duration`, `total_interruption_duration`, `sleep_score`, `sleep_charge`, `sleep_goal`, `sleep_rating`, `sleep_cycles`, `group_duration_score`, `group_solidity_score`, `group_regeneration_score`, `hypnogram`, `device_id` |
| `recharge.py` | `NightlyRecharge` | `date`, `nightly_recharge_status`, `ans_charge`, `ans_charge_status`, `heart_rate_avg`, `heart_rate_variability_avg`, `beat_to_beat_avg`, `breathing_rate_avg` |
| `skin_temperature.py` | `SkinTemperature` | `date`, `sleep_start`, `sleep_end`, `samples`, `deviation` |
| `sleepwise.py` | `SleepWise` | `date`, `alertness_hourly`, `sleep_time`, `wake_time`, `bedtime_window_start`, `bedtime_window_end` |
| `heart_rate.py` | `ContinuousHeartRate` | `date`, `samples: tuple[HeartRateSample, ...]` |
| `night.py` | `Night` | `date` + `sleep`, `recharge`, `skin_temperature`, `sleepwise`, `heart_rate` — **every source optional (`X \| None`)**; plus `@property has_data` |
| `export.py` | `ExportManifest`, `ExportReport` | see below |
| `sync.py` | `SourceSyncStat`, `SyncReport` | see below |

Every field that Polar may omit is `X | None`. Do **not** invent defaults for missing physiological
values — `None` means "Polar did not report it", and the receiving AI must be able to tell the
difference between "0" and "unknown".

Use tuples, not lists, for collections inside frozen dataclasses (hashability + immutability).

**`ExportManifest`** — everything the archive's `manifest.json` needs:
`tool_name`, `tool_version`, `generated_at`, `date_range`, `sources_requested`,
`source_availability: Mapping[NightSource, SourceAvailability]`, `night_count`,
`gaps: tuple[date, ...]`, `request_counts: Mapping[NightSource, int]`,
`history_window_warning: str | None`.

**`ExportReport`** — what the use case returns to the CLI: `archive_path`, `archive_size_bytes`,
`manifest`, `nights`. The CLI renders its summary table from this.

**`SourceSyncStat`** — per source: `availability`, `fetched`, `skipped` (already in the store),
`empty` (Polar had nothing), `requests`.
**`SyncReport`** — `date_range`, `stats: Mapping[NightSource, SourceSyncStat]`,
`history_window_warning: str | None`. Returned by `NightSyncUseCase` and rendered by the CLI so the
user can see what was newly captured versus served from `data/`.

## `domain/services/night_merger.py`

A pure function (or a small stateless class if it needs several helpers):

```python
def merge_nights(
    date_range: DateRange,
    sleeps: Mapping[date, Sleep],
    recharges: Mapping[date, NightlyRecharge],
    skin_temperatures: Mapping[date, SkinTemperature],
    sleepwises: Mapping[date, SleepWise],
    heart_rates: Mapping[date, ContinuousHeartRate],
) -> tuple[tuple[Night, ...], tuple[date, ...]]:
```

Returns the merged nights (sorted ascending, **only dates with at least one source present**) and the
tuple of gap dates.

Second responsibility — **clip heart-rate samples to the night window**: when a date has both a
`Sleep` and a `ContinuousHeartRate`, keep only samples between `sleep_start_time` and
`sleep_end_time`. When there is no `Sleep` for that date, keep the samples unclipped. Both paths need
a test.

## `domain/utils/dates.py`

```python
def iterate_dates(date_range: DateRange) -> Iterator[date]: ...
def is_outside_history_window(day: date, *, today: date) -> bool: ...
def history_window_start(today: date) -> date: ...     # today - (POLAR_HISTORY_WINDOW_DAYS - 1)
```

Pass `today` in explicitly rather than calling `date.today()` inside — it keeps these pure and
testable without `time-machine`.

---

## Tests

**Carried over from phase 1:** the `frozen_time` fixture was deliberately left out of
`tests/conftest.py`, because coverage measures test code and an unused fixture body fails the 100 %
gate. This phase is the first with date logic, so add it now:

```python
@pytest.fixture
def frozen_time(time_machine: TimeMachineFixture) -> datetime:
    fixed_dt = datetime(2026, 1, 1, tzinfo=UTC)
    time_machine.move_to(fixed_dt, tick=False)
    return fixed_dt
```

Only add it if a test in this phase actually uses it — otherwise leave it for phase 8.

- `tests/unit/domain/...` mirroring every source file.
- `tests/unit/factories/entities/*.py` — polyfactory `DataclassFactory` for each entity, and
  `tests/unit/factories/value_objects/*.py` for `DateRange` and `SleepStages`. **No `_make_*` helper
  functions** — factories or fixtures only.
- Cover, at minimum: `DateRange` inversion raising `InvalidDateRangeError`; `SleepStages` negative
  values; the zero-total ratio guard; `merge_nights` with (a) all sources present, (b) some dates
  missing every source → gaps, (c) heart rate with a sleep window → clipped, (d) heart rate without a
  sleep window → unclipped; `is_outside_history_window` on both sides of the boundary and exactly on
  it.

There are no integration tests in this phase — the domain has no collaborators.

---

## Acceptance criteria

```bash
make lint   # zero findings; mypy must be clean with no `Any`
make test   # green at 100 % branch coverage
grep -rE "^(from|import) (httpx|pydantic|typer|rich|tenacity)" polarexport/domain/   # must print nothing
```
