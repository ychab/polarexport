# Phase 23 — Polar exercise adapter

**Depends on:** phases 21 and 22 (entities to map into, ports to implement).
**Needs a Polar token:** **yes** — the first task is capturing live assets.
**Size:** large. Can ship as three commits: assets + DTOs, mappers, client.

## Where this came from

Phases 21 and 22 defined what an exercise is and what the ports promise. This phase is the only one
that talks to Polar.

## 0 — Capture live assets first

Same rule phase 5 followed: **build the DTOs from what comes back, not from this document.** Before
writing any schema, run one authenticated request and save the response:

```
GET /v3/exercises?samples=true&zones=true   ->  tests/assets/polar/exercises.json
GET /v3/users/{user_id}                     ->  tests/assets/polar/user-profile.json
```

Then trim them for the WireMock `__files/` directory the same way the existing night assets are
trimmed — two or three sessions is plenty, and the sample strings can be cut to a few dozen values.

**Scrub the profile asset before committing it.** `GET /v3/users/{id}` returns `first-name`,
`last-name`, `birthdate`, `gender`, `height`, `weight` and `member-id`. Replace the name fields and
`member-id` with obvious placeholders. Keep `birthdate` — the age derivation needs something
realistic to test against — but use a fabricated date, not the real one. The exercise asset needs no
scrubbing beyond what is already there; `polar_user` carries the numeric user id, which the existing
night assets already contain.

Never write the access token into an asset, a fixture or a mapping file.

## 1 — Endpoints

`infrastructure/adapters/providers/polar/endpoints.py`:

```python
EXERCISES: Final[str] = "/v3/exercises"
USER: Final[str] = "/v3/users/{user_id}"
```

Both verified live on 2026-08-20. Do **not** add the transactional
`/v3/users/{user-id}/exercise-transactions` paths — Polar's own swagger marks that resource
deprecated in favour of the non-transactional one, `GET` on it returns `405`, and committing a
transaction *consumes* the data for the client, which would silently destroy the ability to re-fetch.

## 2 — DTOs

`infrastructure/adapters/providers/polar/schemas.py`, `extra="allow"` as always.

**Polar mixes naming conventions inside a single response, and this is the trap in this phase.** The
live capture shows:

| Field | Actual key |
|---|---|
| sample series entries | `sample_type`, `recording_rate` — **underscores**, though the swagger documents `sample-type` / `recording-rate` |
| training load | `cardio-load`, `cardio-load-interpretation`, `muscle-load`, `perceived-load`, `user-rpe` — **hyphens** |
| running index | `running-index` — hyphen, per swagger |
| everything else on the exercise | `start_time`, `detailed_sport_info`, `heart_rate_zones` — underscores |

Use Pydantic aliases with `populate_by_name=True`, and **read the captured asset to confirm each key
rather than trusting either the swagger or this table**. Where swagger and reality disagree, reality
wins — that is exactly the correction phase 5 had to make for the sleepwise paths.

DTOs to add: `ExerciseDTO`, `HeartRateDTO` (`average`, `maximum` — there is no `minimum`),
`HeartRateZoneDTO`, `ExerciseSampleDTO`, `TrainingLoadProDTO`, `UserProfileDTO`.

Every field optional. `heart_rate_zones`, `samples` and `route` only appear when the matching query
parameter was passed, and the energy-source fields (`fat_percentage` and friends) only appear on
devices that support them — the Polar Flow app session in the capture has none of them while the
Ignite 3 sessions do.

## 3 — Mappers

`infrastructure/adapters/providers/polar/mappers.py` — standalone functions wrapped by a
`PolarExerciseMapper` implementing `ExerciseMapperPort`, mirroring `PolarNightMapper`.

Four rules that need to be right:

**Timestamps.** `start_time` is a *naive local* string (`"2026-08-18T11:32:08"`) and
`start_time_utc_offset` is minutes (`120`). Build an aware datetime with
`timezone(timedelta(minutes=offset))` and keep the local offset — the same choice the night export
made, and for the same reason: the local wall-clock time of a training session is meaningful context.
`upload_time` is already UTC with a `Z`. `Exercise.date` is the **local** calendar date of
`start_time`, so a 23:30 session belongs to that day, not to the UTC day after.

**Load sentinels.** When `<x>-load-interpretation` is `NOT_AVAILABLE`, map both the interpretation
and the value to `None`. The live capture has `"muscle-load": -1.0` and `"perceived-load": 0.0`
paired with that interpretation; `-1.0` is a sentinel and `0.0` is indistinguishable from a real
zero, so the interpretation is the only reliable signal. An unknown interpretation string maps to
`None` with `logger.warning`, never raises — Polar can add a value at any time and an export must not
die on it.

**Samples.** Select by `SampleType`: type `0` feeds `heart_rate_stats` and `downsample_per_minute`;
type `1` feeds `SpeedStats`; type `10` is distance. `sample_type` arrives as a **string** (`"0"`) —
coerce before comparing.

**Speed units are not confirmed.** The swagger does not document them and every session in the
capture was indoor, so the speed and distance series were present but entirely zero. Therefore:

- `Exercise.average_speed_kmh` comes from `distance / duration` (phase 21) — units certain.
- `SpeedStats` from the sample series must be populated **only** if the phase's own live capture
  includes an outdoor session that lets you check the sample units against the summary `distance`.
  If it does not, leave `speed` as `None`, add a `# TODO` naming what to verify, and say plainly in
  the archive README that sample-derived speed is not yet available. Do not guess a unit and multiply
  by 3.6 on faith — a wrong pace is worse than a missing one.

Add a mapper test asserting a series of all-zero speed samples does not produce a `SpeedStats` of
zeroes masquerading as a real measurement.

## 4 — Client

Extend `PolarAccessLinkClient` to implement `ExerciseProviderPort` and `ProfileProviderPort` as well
as `NightProviderPort`. One client: same bearer auth, same semaphore, same tenacity policy, same
`HttpClientMixin`. Do not create a second client class.

```python
async def fetch_exercises(self, *, with_samples: bool, with_zones: bool) -> ExerciseFetchResult: ...
async def fetch_profile(self) -> dict[str, Any] | None: ...
```

Status policy, consistent with the night paths:

| Status | Meaning | Behaviour |
|---|---|---|
| `200` + `[]` | no sessions in the window | `AVAILABLE`, empty payloads — **not** an error |
| `403` | consent missing | `UNAVAILABLE`, empty payloads, warning logged, no raise |
| `404` | on the profile endpoint only | `None` profile, warning logged |
| `429` / `5xx` / network | transient | retried by the existing tenacity policy |

`request_count` is 1 for a successful exercise fetch — worth asserting in a test, because it is the
clearest statement that this endpoint is not per-date.

Log the endpoint and the session count, never the token.

## Files

| File | Change |
|---|---|
| `tests/assets/polar/exercises.json` | new — live capture |
| `tests/assets/polar/user-profile.json` | new — live capture, **scrubbed** |
| `tests/assets/wiremock/polar/__files/exercises.json` | new — trimmed |
| `tests/assets/wiremock/polar/__files/user-profile.json` | new — trimmed, scrubbed |
| `tests/assets/wiremock/polar/mappings/get_exercises_200.json` | new |
| `tests/assets/wiremock/polar/mappings/get_exercises_403.json` | new |
| `tests/assets/wiremock/polar/mappings/get_user_profile_200.json` | new |
| `.../providers/polar/endpoints.py` | add `EXERCISES`, `USER` |
| `.../providers/polar/schemas.py` | add the six DTOs |
| `.../providers/polar/mappers.py` | add exercise + profile mappers, `PolarExerciseMapper` |
| `.../providers/polar/client.py` | implement both new ports |

## Tests

Integration first, per the project's philosophy — WireMock plus the real client:

- The `200` mapping maps end to end into `Exercise` entities with the captured values: the kickboxing
  session's `calories == 786`, `heart_rate.average == 121`, `heart_rate.maximum == 175`, a derived
  `heart_rate.minimum` matching the trimmed asset's own minimum, five zones, and `sport_label ==
  "Kickboxing Martial Arts"`.
- `request_count == 1`.
- `403` yields `UNAVAILABLE` with no exception and no payloads.
- An empty `[]` response yields `AVAILABLE` with no payloads — reuse the existing
  `__files/empty-array.json`.
- The profile maps into `UserProfile` with the scrubbed birthdate, and `age` computes from it.
- Mark every integration class `@pytest.mark.wiremock`.

Unit tests for the branches integration cannot reach cleanly:

- `NOT_AVAILABLE` interpretation nulls both value and interpretation, for all three load kinds.
- An unrecognised interpretation string yields `None` and logs a warning rather than raising.
- A missing `start_time_utc_offset` still produces a usable datetime — decide and document whether it
  is treated as UTC or as an unmapped session, and test the decision.
- A malformed `duration` string leaves `duration_seconds` as `None` and the rest of the session maps.
- Samples present but with an unknown `sample_type` are ignored, not mapped into the wrong field.
- A session with no `samples` key at all maps with `heart_rate.minimum is None` — the common case for
  `?samples=false`.

## Acceptance criteria

- The DTOs match the captured asset key for key, including the mixed hyphen/underscore naming.
- No sentinel value (`-1.0`, an unavailable `0.0`) can reach an entity.
- `403` never raises; an empty window never raises.
- No token in any asset, mapping, fixture or log line; the profile asset carries no real name.
- `make lint` clean, `make test` green at 100 % branch coverage.
