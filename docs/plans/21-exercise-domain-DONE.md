# Phase 21 — Exercise domain layer

**Depends on:** nothing in phases 20–25 (phase 20 is unrelated). This is the first of five exercise
phases; do it first, 22–25 build on it.
**Needs a Polar token:** no. Pure domain, no I/O.
**Size:** medium. One commit.

## Where this came from

The user asked for a new command exporting **training sessions** (kickboxing, jogging, walking) with
BPM stats, distance, speed, duration, calories and enough intensity signal that an agent reading the
archive can answer "how many calories for how long an effort, and how hard was it".

`CLAUDE.md` currently says sport sessions are out of scope. **That is now obsolete** — phase 25
updates it. The architecture was built to make this a drop-in; these phases are that drop-in.

### What the API actually returns — probed live on 2026-08-20

`GET /v3/exercises` (non-transactional; the transactional `exercise-transactions` API is marked
deprecated in Polar's own swagger, and `GET` on it returns `405`). Query parameters: `samples`,
`zones`, `route` — **no date filter**, and only the last **30 days** of uploads are returned. One
request returns the whole window.

A real session, verbatim:

```json
{
  "id": "54klrKbL",
  "upload_time": "2026-08-18T10:59:25Z",
  "polar_user": "https://www.polaraccesslink.com/v3/users/60233839",
  "device": "Polar Flow app",
  "start_time": "2026-08-18T11:32:08",
  "start_time_utc_offset": 120,
  "duration": "PT5221.533S",
  "heart_rate": { "average": 121, "maximum": 175 },
  "sport": "OTHER",
  "has_route": false,
  "detailed_sport_info": "KICKBOXING_MARTIAL_ARTS",
  "calories": 786,
  "training_load_pro": {
    "cardio-load": 81.1622,
    "cardio-load-interpretation": "HIGH",
    "muscle-load": -1.0,
    "muscle-load-interpretation": "NOT_AVAILABLE",
    "perceived-load": 0.0,
    "perceived-load-interpretation": "NOT_AVAILABLE",
    "user-rpe": "UNKNOWN"
  }
}
```

With `?zones=true`, a `heart_rate_zones` array of five `{index, lower_limit, upper_limit, in_zone}`
where `in_zone` is an ISO-8601 duration (`"PT16M18S"`). With `?samples=true`, a `samples` array of
`{sample_type, recording_rate, data}` where `data` is a **comma-separated string**; the observed
session carried `sample_type` `"0"`, `"1"` and `"10"` at `recording_rate: 1`, with 5 222 values for
a 5 221-second session.

### The two findings that drive this design

**1. Minimum heart rate does not exist in the API.** Polar's `HeartRate` schema has exactly two
fields, `average` and `maximum`. The user asked for min. It has to be derived from `sample_type: "0"`.
Derivation was verified live on all three sessions in the window:

| session | sport | API avg | avg recomputed from samples | derived min |
|---|---|---|---|---|
| `ymmr1Q46` | AEROBICS | 111 | 110.5 | 83 |
| `54klrKbL` | KICKBOXING_MARTIAL_ARTS | 121 | 121.0 | 70 |
| `09Bzklzo` | AEROBICS | 115 | 115.4 | 73 |

The recomputed average reproduces Polar's own to within rounding, exactly as sleep efficiency did in
phase 19 — so the sample series is trustworthy and the derived minimum is sound.

**2. Time-in-zone is the intensity signal, and it is free.** `?zones=true` costs nothing extra on the
same request and gives the distribution the user is really asking for. The kickboxing session:
Z0 15 min 41 s, Z1 16 min 18 s, Z2 21 min 36 s, Z3 8 min 44 s, Z4 0 s. Combined with
`training_load_pro.cardio-load` (81.2, `HIGH`) an agent can characterise effort without any time
series at all.

## 1 — ISO-8601 duration parsing

Nothing in the codebase parses ISO durations yet, and `duration` / `in_zone` are both ISO-8601. Do
**not** add a dependency for this (`isodate` would be a new runtime dep and deptry is strict); write a
small pure function.

`polarexport/domain/utils/durations.py`:

```python
def parse_iso_duration(value: str) -> float | None:
    """Parse an ISO-8601 duration into seconds.

    Polar emits only the time portion — `PT5221.533S`, `PT16M18S`, `PT2H44M`, `PT0S`. Anything with a
    date component (`P1D`) or that does not parse returns `None`; it has never been observed and
    guessing is worse than reporting nothing.
    """
```

Regex-based, hours/minutes/seconds, each optional, seconds may be fractional. Return `None` rather
than raising — a single unparseable duration must not fail a whole export.

## 2 — Enums

In `domain/enums.py`, alongside the existing ones:

```python
class SampleType(IntEnum):
    """Polar exercise sample-series type ids.

    `HEART_RATE` is confirmed: phase 21's live capture showed type "0" carrying 70–175 bpm values
    whose mean reproduces Polar's own `heart_rate.average`. The rest come from Polar's documentation
    — the audited sessions were all indoor, so types "1" and "10" were present but all-zero and their
    identity is inferred, not verified. Confirm SPEED and DISTANCE against a real outdoor session
    before trusting them (see phase 23).
    """

    HEART_RATE = 0
    SPEED = 1
    CADENCE = 2
    ALTITUDE = 3
    POWER = 4
    POWER_PEDALING_INDEX = 5
    POWER_LEFT_RIGHT_BALANCE = 6
    AIR_PRESSURE = 7
    RUNNING_CADENCE = 8
    TEMPERATURE = 9
    DISTANCE = 10
    RR_INTERVAL = 11


class LoadInterpretation(StrEnum):
    """Polar's verbal reading of a training-load figure.

    `MEDIUM`, `HIGH` and `NOT_AVAILABLE` were observed live; the others are documented by Polar.
    Unknown values must map to `None` with a warning, never raise — see the mapper rule in phase 23.
    """

    NOT_AVAILABLE = "NOT_AVAILABLE"
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
```

Do **not** add a `Sport` enum. Polar's `detailed_sport_info` vocabulary is long, undocumented in the
swagger and changes; a closed enum would break on the first unknown sport. Keep it a `str`.

## 3 — Value objects

`domain/value_objects/heart_rate_stats.py`:

```python
@dataclass(frozen=True, kw_only=True)
class HeartRateStats:
    average: int | None = None
    maximum: int | None = None
    minimum: int | None = None  # never returned by Polar — derived from the sample series
```

`domain/value_objects/heart_rate_zone.py`:

```python
@dataclass(frozen=True, kw_only=True)
class HeartRateZone:
    index: int
    lower_limit: int | None = None
    upper_limit: int | None = None
    seconds: int | None = None  # parsed from `in_zone`
```

`domain/value_objects/speed_stats.py` — `average_kmh`, `maximum_kmh`, `minimum_kmh`, all
`float | None`.

`domain/value_objects/training_load.py`:

```python
@dataclass(frozen=True, kw_only=True)
class TrainingLoad:
    cardio_load: float | None = None
    cardio_load_interpretation: LoadInterpretation | None = None
    muscle_load: float | None = None
    muscle_load_interpretation: LoadInterpretation | None = None
    perceived_load: float | None = None
    perceived_load_interpretation: LoadInterpretation | None = None
    user_rpe: str | None = None
```

**Sentinel rule, and it matters here.** The live payload carries `"muscle-load": -1.0` next to
`"muscle-load-interpretation": "NOT_AVAILABLE"`, and `"perceived-load": 0.0` next to the same. Per
`CLAUDE.md`, `None` must stay distinguishable from `0` — so the *mapper* (phase 23) converts a
`NOT_AVAILABLE` interpretation into `None` for both the value and the interpretation. A `-1.0` muscle
load reaching `exercises.json` is a bug. The entity itself stores whatever it is given; the rule lives
in the mapper, and the test for it lives there too.

## 4 — The `Exercise` entity

`domain/entities/exercise.py`, frozen, `kw_only`:

| Field | Type | Source |
|---|---|---|
| `id` | `str` | `id` |
| `start_time` | `datetime` | `start_time` + `start_time_utc_offset`, tz-aware |
| `date` | `date` | local calendar date of `start_time` — the join key with `Night` |
| `upload_time` | `datetime \| None` | `upload_time` |
| `duration_seconds` | `float \| None` | `parse_iso_duration(duration)` |
| `sport` | `str \| None` | `sport` |
| `detailed_sport_info` | `str \| None` | `detailed_sport_info` |
| `device` / `device_id` | `str \| None` | as named |
| `calories` | `int \| None` | `calories` |
| `distance_meters` | `float \| None` | `distance` — **the API unit is metres** |
| `heart_rate` | `HeartRateStats \| None` | summary + derived minimum |
| `heart_rate_zones` | `tuple[HeartRateZone, ...] \| None` | `?zones=true` |
| `heart_rate_per_minute` | `tuple[int \| None, ...] \| None` | derived, see §5 |
| `speed` | `SpeedStats \| None` | derived, see §5 |
| `training_load` | `TrainingLoad \| None` | `training_load_pro` |
| `running_index` | `int \| None` | `running-index` |
| `fat_percentage` / `carbohydrate_percentage` / `protein_percentage` | `int \| None` | as named |
| `has_route` | `bool \| None` | `has_route` |

`__post_init__`: reject a negative `duration_seconds`. Nothing else — everything Polar may omit is
`X | None` and `None` means "not reported", which is a normal state, not an error.

Properties (dynamic values, per `CLAUDE.md`):

```python
@property
def sport_label(self) -> str | None:
    """Human-readable sport name: "Kickboxing Martial Arts" from KICKBOXING_MARTIAL_ARTS.

    Prefers `detailed_sport_info` — `sport` is frequently the useless "OTHER", as it was on all
    three sessions in the phase-21 capture, including the kickboxing one.
    """

@property
def distance_km(self) -> float | None: ...          # distance_meters / 1000

@property
def average_speed_kmh(self) -> float | None:
    """Derived from distance and duration, not from the speed sample series.

    Both inputs have units confirmed by Polar's swagger (metres, ISO-8601 duration), so this figure
    is trustworthy today. The sample-derived figures in `speed` are not — see phase 23.
    """

@property
def calories_per_hour(self) -> float | None: ...    # None when duration is zero or missing
```

Guard every property against `None` inputs and against a zero duration — return `None`, exactly the
shape `Sleep.efficiency_percent` uses.

## 5 — Derived metrics service

`domain/services/exercise_metrics.py` — pure functions, no I/O.

```python
def parse_sample_series(data: str) -> tuple[float | None, ...]:
    """Split Polar's comma-separated sample string.

    Polar's swagger states the list "can contain null-values which indicate a situation where sensor
    was offline" — those become `None`, as do empty segments. A value that is present but not numeric
    is also `None`; one bad reading must not discard the series.
    """


def heart_rate_stats(
    samples: Sequence[float | None], *, api_average: int | None, api_maximum: int | None
) -> HeartRateStats:
    """Combine Polar's own average/maximum with a minimum derived from the samples.

    Polar's figures win where they exist — they are what Polar Flow shows and what the account export
    agrees with. Only the minimum is genuinely ours.

    Non-positive samples are discarded before taking the minimum: a 0 bpm reading is a sensor
    dropout, not a heart rate, and a "minimum: 0" in the archive would be actively misleading.
    """


def downsample_per_minute(
    samples: Sequence[float | None], *, recording_rate_seconds: int | None
) -> tuple[int | None, ...]:
    """Average the sample series into one rounded value per minute.

    The full 1 Hz series is ~5 000 values per session and is deliberately kept out of the archive; a
    per-minute curve is ~87 values for the same session and is what lets an agent see the *shape* of
    an effort — warm-up, intervals, fade — instead of only its totals.

    A bucket whose samples are all missing yields `None`, not 0. Returns an empty tuple when
    `recording_rate_seconds` is `None` (Polar documents this for RR data), zero, or greater than 60.
    """
```

Bucket size is `60 // recording_rate_seconds`. Handle a final short bucket. Do not silently pad.

## 6 — Profile entity

The user chose to include their Polar profile so intensity can be normalised. `GET /v3/users/{id}`
returns `birthdate`, `gender`, `height` (cm), `weight` (kg), plus name fields.

`domain/entities/profile.py`:

```python
@dataclass(frozen=True, kw_only=True)
class UserProfile:
    user_id: str
    birthdate: date | None = None
    gender: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None

    def age(self, *, on: date) -> int | None: ...

    def estimated_max_heart_rate(self, *, on: date) -> int | None:
        """The classic `220 - age` estimate.

        It is a population formula with a standard deviation of roughly 10 bpm, not this user's
        measured maximum — the archive README must say so, and nothing should present a derived
        "% of max" as precise.
        """
```

**Do not map the name fields.** `first-name` / `last-name` are in the payload and have no analytical
use; leaving them unmapped keeps them out of `exercises.json` by construction. They still land in
`data/raw/` verbatim, which is correct — the raw store keeps payloads untouched.

## 7 — Manifest and report entities

`domain/entities/exercise_export.py`:

```python
@dataclass(frozen=True, kw_only=True)
class SportSummary:
    sport: str
    session_count: int
    total_duration_seconds: float
    total_calories: int


@dataclass(frozen=True, kw_only=True)
class ExerciseManifest:
    tool_name: str
    tool_version: str
    generated_at: datetime
    date_range: DateRange
    availability: SourceAvailability
    exercise_count: int
    total_duration_seconds: float
    total_calories: int
    sports: tuple[SportSummary, ...] = field(default_factory=tuple)
    profile: UserProfile | None = None
    history_window_warning: str | None = None


@dataclass(frozen=True, kw_only=True)
class ExerciseExportReport:
    archive_path: Path
    archive_size_bytes: int
    manifest: ExerciseManifest
    exercises: tuple[Exercise, ...] = field(default_factory=tuple)
```

The totals and the per-sport breakdown are the direct answer to the user's "an agent must know how
many calories for a duration of effort" — they belong in the manifest so that question is answerable
without reading `exercises.json` at all. Build them in a small `domain/services/exercise_summary.py`
function, not inside the archiver: it is business logic and the archiver is infrastructure.

## 8 — Constants

`domain/const.py`:

```python
POLAR_EXERCISE_WINDOW_DAYS: Final[int] = 30  # /v3/exercises retention — NOT the nights' 28
EXERCISE_ARCHIVE_NAME_TEMPLATE: Final[str] = "polarexport-exercises-{date_min}_{date_max}.zip"
EXERCISE_DIR_NAME: Final[str] = "exercise"
PROFILE_FILENAME: Final[str] = "profile.json"
```

The window really is different — 30 days for exercises, 28 for sleep and recovery. `dates.py`'s
`is_outside_history_window` hardcodes `POLAR_HISTORY_WINDOW_DAYS`. Generalise it with a keyword-only
`window_days: int = POLAR_HISTORY_WINDOW_DAYS` parameter so the night call sites are untouched and
the exercise use case can pass 30. Do not fork the function.

## Files

| File | Change |
|---|---|
| `polarexport/domain/utils/durations.py` | new — `parse_iso_duration` |
| `polarexport/domain/utils/dates.py` | `is_outside_history_window` takes `window_days` |
| `polarexport/domain/enums.py` | add `SampleType`, `LoadInterpretation` |
| `polarexport/domain/const.py` | add the four constants above |
| `polarexport/domain/value_objects/heart_rate_stats.py` | new |
| `polarexport/domain/value_objects/heart_rate_zone.py` | new |
| `polarexport/domain/value_objects/speed_stats.py` | new |
| `polarexport/domain/value_objects/training_load.py` | new |
| `polarexport/domain/entities/exercise.py` | new |
| `polarexport/domain/entities/profile.py` | new |
| `polarexport/domain/entities/exercise_export.py` | new |
| `polarexport/domain/services/exercise_metrics.py` | new |
| `polarexport/domain/services/exercise_summary.py` | new |

## Tests

One test file per source file, mirrored. Factories in `tests/unit/factories/` — `DataclassFactory`
for every entity and value object added here (`ExerciseFactory`, `UserProfileFactory`,
`HeartRateStatsFactory`, `HeartRateZoneFactory`, `TrainingLoadFactory`, `SpeedStatsFactory`,
`ExerciseManifestFactory`, `SportSummaryFactory`).

**Use the real captured numbers as fixtures.** They are in this document and they are known-good:

- `parse_iso_duration`: `"PT5221.533S"` → `5221.533`; `"PT16M18S"` → `978`; `"PT2H44M"` → `9840`;
  `"PT0S"` → `0.0`; `"P1D"` → `None`; `"nonsense"` → `None`; `""` → `None`.
- `heart_rate_stats`: feed a series whose minimum is 70 and confirm `minimum == 70` while `average`
  and `maximum` come back as the API's 121 / 175, *not* recomputed. Separately: a series containing
  `0` and `None` must still yield 70, proving dropouts are discarded.
- `downsample_per_minute`: 120 samples at `recording_rate_seconds=1` → 2 values; at
  `recording_rate_seconds=5` → 10 values; a trailing partial bucket is kept; an all-`None` bucket
  yields `None`; `recording_rate_seconds=None` and `=0` and `=90` each yield `()`.
- `Exercise.sport_label`: `KICKBOXING_MARTIAL_ARTS` → `"Kickboxing Martial Arts"`; falls back to
  `sport` when `detailed_sport_info` is `None`; `None` when both are `None`.
- `Exercise.average_speed_kmh`: 10 000 m over `PT1H` → `10.0`; `None` when distance is `None`, when
  duration is `None`, and when duration is `0`.
- `Exercise.calories_per_hour`: 786 kcal over 5221.533 s → ≈ 542; `None` on a zero duration.
- `UserProfile.age` / `estimated_max_heart_rate`: birthdate 1990-03-15 evaluated on 2026-08-20 → 36
  and 184; the day before the birthday → 35; `None` when `birthdate` is `None`.
- `exercise_summary`: sessions across two sports aggregate into two `SportSummary` entries sorted by
  total duration descending, with sessions missing `calories` contributing 0 rather than raising.

Error branches (`None` inputs, zero durations, unparseable values) belong in these unit tests — there
is no integration path to reach them, and this phase has no I/O.

## Acceptance criteria

- No framework imports anywhere in this phase: no `pydantic`, no `httpx`, no `typer`, no filesystem.
- Every field Polar may omit is `X | None`, and no sentinel (`-1.0`, `0.0` for an unavailable load)
  is representable as a real value in the archive.
- `Exercise.heart_rate.minimum` is populated from samples and is documented as derived.
- `is_outside_history_window` still behaves identically for all existing night call sites.
- `make lint` clean, `make test` green at 100 % branch coverage.
