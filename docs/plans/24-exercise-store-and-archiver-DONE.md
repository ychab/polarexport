# Phase 24 — Exercise store and zip archiver

**Depends on:** phases 21 and 22. Independent of phase 23 — this phase needs no network and can be
built in parallel with it.
**Needs a Polar token:** no. Real filesystem on `tmp_path`.
**Size:** large. Two commits: store, then archiver.

## Where this came from

Phase 22's `ExerciseStorePort`, `ProfileStorePort` and `ExerciseArchiverPort` need implementations.

## 1 — `FilesystemExerciseStore`

`infrastructure/adapters/stores/filesystem_exercise.py`. Mirror `FilesystemNightStore` closely:
synchronous work in private `_*_sync` methods, `asyncio.to_thread` at the boundary, atomic writes
(temp file in the same directory, then `Path.replace()`), a provenance envelope, and a `_status.json`
for availability.

Layout, extending the existing `data/raw/<api>/<source>/…` convention:

```
data/raw/polar-accesslink-v3/exercise/2026/08/2026-08-18-54klrKbL.json
data/raw/polar-accesslink-v3/exercise/_status.json
```

`<YYYY-MM-DD>-<id>` as the filename. Date first so the directory sorts chronologically; id appended
because — unlike nights — a day can hold several sessions. That is the whole reason this store cannot
reuse `FilesystemNightStore`: its path is one file per source per date.

Envelope, same shape as the night store's:

```json
{
  "schema_version": 1,
  "api": "polar-accesslink-v3",
  "id": "54klrKbL",
  "date": "2026-08-18",
  "fetched_at": "2026-08-20T06:52:55+00:00",
  "payload": { }
}
```

There is no `payload: null` case here. For nights, a null payload records "Polar was asked about this
date and had nothing", which is what stops endless re-fetching. Exercises have no per-date question to
ask — an id exists only because Polar returned a session — so a stored record always has a payload.
Write that reasoning into the module docstring; it is the kind of asymmetry that looks like an
oversight later.

Methods:

- `write(stored)` — atomic, creates `YYYY/MM/` as needed.
- `read(date_range)` — walk only the `YYYY/MM` directories the range touches, not the whole tree, and
  filter on the envelope's `date`. Returns a mapping keyed by id.
- `known_ids()` — walk the whole tree and collect ids. Take them from the **filename**, not by
  parsing every file: the id is the segment after the first three `-`-separated date parts, and
  reading a few hundred JSON files to answer "do I have this id" is wasteful. Note that Polar ids are
  alphanumeric and can themselves contain no `-`, but split defensively with `maxsplit` anyway.
- `write_availability` / `read_availability` — same `_status.json` pattern as the night store,
  minus the per-source dimension.

A corrupt or unreadable file must be skipped with a warning, never crash a read — the same contract
phase 17 established for `JsonCredentialsStore`. Reuse that shape: catch
`(json.JSONDecodeError, KeyError, ValueError, TypeError)`, log, continue.

## 2 — `JsonProfileStore`

`infrastructure/adapters/stores/json_profile.py`. One file, `data/raw/polar-accesslink-v3/profile.json`,
same envelope discipline (`schema_version`, `api`, `fetched_at`, `payload`), same atomic write, same
skip-on-unparseable behaviour returning `None`.

Mode `0600`, like `credentials.json`: it carries the user's birthdate, gender, height and weight, and
Polar's payload also includes their real name. Do this with `os.fchmod(fd, 0o600)` on the temp file
before the replace, and comment *why* — phase 19 had to retrofit exactly that comment onto the
archiver after the mode turned out to be an accident of `tempfile.mkstemp`.

## 3 — Share the atomic-zip write

`ZipNightArchiver._write_sync` already does: refuse-if-exists-unless-force, `mkstemp`, `fchmod 0600`,
write entries, `unlink` on any `BaseException`, `replace()` into place. The exercise archiver needs
all of it identically.

Extract the mechanism into `infrastructure/adapters/archivers/atomic_zip.py`:

```python
def write_zip_atomic(target: Path, entries: Mapping[str, str], *, force: bool) -> int:
    """Write `entries` as a zip at `target`, atomically, mode 0600. Returns the size in bytes."""
```

`entries` maps archive path to text content. Both archivers then only decide *what* goes in.

Keep this small and resist building an archiver base class — the two archivers share a file-writing
mechanism, not a domain. `ZipNightArchiver` must come out behaviourally identical; its existing tests
are the regression suite and none of them should need editing. If one does, the extraction changed
behaviour and is wrong.

## 4 — `ZipExerciseArchiver`

`infrastructure/adapters/archivers/zip_exercise.py` implementing `ExerciseArchiverPort`, with
`infrastructure/adapters/archivers/exercise_serializers.py` alongside it, mirroring the existing
`serializers.py` split.

Archive contents:

```
polarexport-exercises-2026-07-22_2026-08-20.zip
├── manifest.json
├── README.md
├── exercises.json
└── raw/exercise/2026-08-18-54klrKbL.json
```

`exercises.json`, sorted by `start_time` ascending:

```json
{
  "date_range": {"date_min": "2026-07-22", "date_max": "2026-08-20"},
  "exercise_count": 3,
  "exercises": [
    {
      "id": "54klrKbL",
      "start_time": "2026-08-18T11:32:08+02:00",
      "date": "2026-08-18",
      "sport": "KICKBOXING_MARTIAL_ARTS",
      "sport_label": "Kickboxing Martial Arts",
      "duration_seconds": 5221.533,
      "calories": 786,
      "calories_per_hour": 542.0,
      "distance_km": null,
      "average_speed_kmh": null,
      "heart_rate": {"average": 121, "maximum": 175, "minimum": 70},
      "heart_rate_zones": [
        {"index": 0, "lower_limit": 98, "upper_limit": 118, "seconds": 941},
        {"index": 1, "lower_limit": 118, "upper_limit": 137, "seconds": 978}
      ],
      "heart_rate_per_minute": [98, 112, 131, 128, 141],
      "training_load": {
        "cardio_load": 81.1622,
        "cardio_load_interpretation": "HIGH",
        "muscle_load": null,
        "muscle_load_interpretation": null
      },
      "device": "Polar Flow app",
      "running_index": null,
      "fat_percentage": null
    }
  ]
}
```

Emit **every** key even when `null`, as `nights.json` does — an absent key and a null key read
differently to a consumer, and phase 16 settled this for nights.

`heart_rate_per_minute` is omitted entirely (not nulled) when `include_samples` is `False`, and the
README says which mode produced the archive.

`manifest.json` carries the totals that make the archive answerable on its own:

```json
{
  "tool_name": "polarexport",
  "tool_version": "0.2.0",
  "generated_at": "2026-08-20T09:12:39+00:00",
  "date_range": {"date_min": "2026-07-22", "date_max": "2026-08-20"},
  "availability": "available",
  "exercise_count": 3,
  "total_duration_seconds": 12979.364,
  "total_calories": 1911,
  "sports": [
    {"sport": "AEROBICS", "session_count": 2, "total_duration_seconds": 7757.8, "total_calories": 1125},
    {"sport": "KICKBOXING_MARTIAL_ARTS", "session_count": 1, "total_duration_seconds": 5221.5, "total_calories": 786}
  ],
  "profile": {"birthdate": "1990-03-15", "gender": "MALE", "height_cm": 175.0, "weight_kg": 71.0},
  "history_window_warning": null
}
```

## 5 — The archive README template

`infrastructure/adapters/archivers/templates/exercise-README.md`, rendered by
`exercise_serializers._render_readme`. This file is the contract with the AI agent reading the
archive, so it has to carry semantics, not just field names. It must state:

- **Units**, explicitly: `duration_seconds` seconds, `distance_km` kilometres (Polar's API returns
  metres — the conversion happens here), `calories` kilocalories, heart rates bpm, zone `seconds`
  seconds (Polar sends ISO-8601 durations — also converted here).
- **Which figures are Polar's and which are derived.** `heart_rate.average` and `.maximum` are
  Polar's own; `.minimum` does not exist in the API and is derived from the per-second series;
  `average_speed_kmh` and `calories_per_hour` are derived. An agent weighing evidence should know
  which is which.
- **What the heart-rate zones mean** — five zones, `lower_limit`/`upper_limit` in bpm, `seconds` as
  time spent in that zone, and that the zone boundaries are the user's own Polar settings, so time in
  Z3 is a personal intensity statement rather than an absolute one.
- **What `cardio_load` means**, with the `LoadInterpretation` scale rendered as a table the way the
  night README renders `ContinuityClass`. Say that `muscle_load` and `perceived_load` are `null` on
  devices that do not measure them, which for this user's watches is all of them.
- **`heart_rate_per_minute`** — one averaged bpm value per minute of the session, starting at
  `start_time`; the underlying per-second series is in `data/raw/` locally but is deliberately not
  shipped. Say the resolution plainly so nobody reads the array as per-second.
- **The profile block and its caveat** — `estimated_max_heart_rate` is `220 - age`, a population
  formula with roughly ±10 bpm of spread, not a measured maximum. Any "% of max" an agent computes
  inherits that error.
- **The 30-day retention caveat**, and that it differs from the night export's 28.
- **`sport` vs `sport_label`** — `sport` is Polar's raw token, `sport_label` is the readable form, and
  the top-level `sport` field on Polar's payload is frequently the useless `"OTHER"`, which is why
  `detailed_sport_info` is what gets exported.

## Files

| File | Change |
|---|---|
| `.../stores/filesystem_exercise.py` | new |
| `.../stores/json_profile.py` | new |
| `.../archivers/atomic_zip.py` | new — extracted from `zip.py` |
| `.../archivers/zip.py` | use `write_zip_atomic`; behaviour unchanged |
| `.../archivers/zip_exercise.py` | new |
| `.../archivers/exercise_serializers.py` | new |
| `.../archivers/templates/exercise-README.md` | new |

## Tests

Integration, on `tmp_path` with the real store and real archiver:

- Write three sessions across two months, then `read` a range covering only one — only that month's
  sessions come back, proving the directory walk is scoped and correct.
- Two sessions on the **same day** both round-trip, with distinct filenames. This is the case the
  night store cannot represent and the main reason this store exists.
- `known_ids()` returns all three ids after writing, and an empty frozenset on an empty store.
- Availability round-trips through `_status.json`.
- The archive opens with `zipfile` and contains exactly `manifest.json`, `README.md`,
  `exercises.json` and the expected `raw/exercise/*.json` entries; with `include_raw=False` the
  `raw/` entries are gone.
- `include_samples=False` produces entries with no `heart_rate_per_minute` key at all.
- The archive is mode `0600` and the profile file is mode `0600`.
- `manifest.json` totals equal the sum of the sessions, and `sports` is sorted deterministically.
- Re-running without `--force` raises `ArchiveAlreadyExistsError` and leaves the existing file
  untouched — assert the mtime or content is unchanged, not just that it raised.

Unit tests for the error branches:

- A corrupt JSON file in the store is skipped with a warning; the other sessions still read.
- A file whose envelope is missing `id` or `date` is skipped, not crashed on.
- An unreadable profile returns `None`.
- `write_zip_atomic` leaves no temp file behind when entry writing raises — force a failure and
  assert the directory contains neither the target nor a `.tmp` file.

## Acceptance criteria

- `ZipNightArchiver`'s existing tests pass **unmodified** after the extraction.
- Two sessions on one day are storable and retrievable.
- Every file this phase writes — archive and profile — is mode `0600` by explicit decision, with a
  comment saying why.
- `make lint` clean, `make test` green at 100 % branch coverage.
