# Phase 16 — Fields the API returns and `nights.json` drops

**Depends on:** phase 15 (do 15 first — it moves `data/` and would conflict).
**Needs a Polar token:** yes, to capture live SleepWise and skin-temperature assets.
**Size:** medium-large. The four items are independent; they can ship as four commits.

## Where this came from

The user downloaded the full account export from flow.polar.com
(`polar-user-data-export.zip`, 243 MB, 4 881 files) and asked whether `polarexport night` misses
anything. It was audited against the local store on 2026-08-19. Findings:

**The premise that skin temperature is missing is wrong.** `data/raw/…/skin-temperature/` holds 28 of
28 nights, `manifest.json` reports `"skin-temperature": "available"`, and the watch records it —
1 117 nights of it in the account export, spanning 2023-07-18 to 2026-08-05, as
`generic-period-*.json` files with `measurementType: "TM_SKIN_TEMPERATURE"`,
`sensorLocation: "SL_DISTAL"` and a 5-minute sample series. What differs is **resolution**: the
account export has ~102 samples per night; AccessLink returns one nightly aggregate. That part is a
genuine API limitation and is documented, not fixed, by this phase.

**What is a real defect** is that four things the API *does* return never reach `nights.json`. They
survive only in `raw/`, so an agent reading the merged document cannot see them. Measured on the
stored payload for 2026-08-05:

| Dropped | Where it is now | Size |
|---|---|---|
| `sleep_time_skin_temperature_celsius` (33.83 °C) | in `raw/`, discarded by the mapper | scalar |
| `sleep.heart_rate_samples` | in `raw/`, not in `SleepDTO` | 97 points |
| `recharge.hrv_samples` / `breathing_samples` | in the DTO, not in the entity | 91 / 98 points |
| SleepWise grade, validity, inertia, circadian detail | in the DTO, flattened away by the mapper | ~15 fields |

And three fields ship as dead weight in every single night: `skin_temperature.sleep_start`,
`.sleep_end`, `.samples` are always `null`, `null`, `[]` because AccessLink never populates them.

## 1 — Skin temperature: keep the absolute value, drop the dead fields

`_skin_temperature_dto_to_entity` maps only `deviation_from_baseline_celsius`. The DTO already parses
`sleep_time_skin_temperature_celsius` and it is thrown away.

- `SkinTemperature`: add `celsius: float | None = None`. **Remove** `sleep_start`, `sleep_end` and
  `samples` — AccessLink has no per-sample skin-temperature endpoint, so they are unreachable, not
  merely unpopulated. Remove `SkinTemperatureSample` from `domain/types.py` once nothing uses it.
- Mapper: map both fields.
- `_serialize_skin_temperature`: emit `celsius` and `deviation`; drop the three dead keys.
- `SkinTemperatureDTO`'s docstring claims "unverified, no Elixir-capable device on hand… built from
  the official swagger.yaml, not a live capture". **That is now false** — there are 28 live payloads
  on disk. Replace it with the verified shape and the capture date.

Both numbers matter and neither derives the other: `celsius` is the measured distal skin temperature
during sleep, `deviation` is the signed departure from *this user's own* rolling baseline. An agent
looking for illness or cycle signal wants the deviation; one correlating with room temperature wants
the absolute. Say so in the archive README.

## 2 — Sleep-window heart rate

The sleep endpoint returns its own `heart_rate_samples`, an `"HH:MM" -> bpm` map keyed on the **same
97 timestamps as the hypnogram**. `SleepDTO` does not declare it, so `extra="allow"` keeps it in
`raw/` and nothing else sees it.

- `SleepDTO`: add `heart_rate_samples: dict[str, int] | None = None`.
- `domain/types.py`: add `type HeartRateByTime = dict[str, int]`. Do not reuse `Hypnogram` — same
  shape, different meaning.
- `Sleep`: add `heart_rate_samples: HeartRateByTime | None = None`.
- Mapper and `_serialize_sleep`.

**Document that this is not the same series as `NightSource.HEART_RATE`.** The continuous-heart-rate
source returns 951 samples for the whole day at 5-minute spacing, which `night_merger` clips to the
sleep window (87 points for 2026-08-05). The sleep endpoint's series is Polar's own, aligned to
hypnogram transitions. Keeping both is right; letting an agent double-count them is not. Add a
sentence to the archive README template distinguishing them.

## 3 — Nightly Recharge sample series

`NightlyRechargeDTO` declares `hrv_samples` and `breathing_samples`; `NightlyRecharge` has neither,
so the mapper silently drops 91 + 98 points per night.

- `NightlyRecharge`: add `hrv_samples: dict[str, int] | None = None` and
  `breathing_samples: dict[str, float] | None = None`.
- Mapper and `_serialize_recharge`.

`nights.json` is 380 KB for 28 nights today. Items 2 and 3 together roughly double it. That is the
right trade — it is a JSON file in a zip, and the samples are the point of the export — but note it
in the phase's commit message so it is not a surprise.

## 4 — SleepWise fidelity

`_sleepwise_dto_to_entity` carries a comment admitting the shape was guessed:

> The domain SleepWise entity predates a live SleepWise payload (this account has no supported
> device) and models an hourly (hour, label) view rather than Polar's richer hourly_data objects.
> Best-effort projection until the entity is revisited with real data.

**That time has come** — 27 of 28 nights on disk carry a full SleepWise payload. The projection to
`tuple[int, str]` discards `validity`, `end_time`, and every top-level field, and the circadian half
is reduced to `sleep_gate_start_time` / `sleep_gate_end_time`, dropping
`preferred_sleep_period_start_time` / `_end_time`, `quality` and `validity` entirely.

- New value object `polarexport/domain/value_objects/alertness_hour.py`:
  `AlertnessHour(start_time, end_time, alertness_level, validity)`, frozen. Remove the
  `type AlertnessHour = tuple[int, str]` alias from `domain/types.py`.
- `SleepWise` gains, from alertness: `grade`, `grade_type`, `grade_classification`,
  `grade_validity_seconds`, `validity`, `sleep_inertia`, `sleep_type`, `result_type`,
  `period_start_time`, `period_end_time`, `sleep_timezone_offset_minutes`; and from circadian:
  `circadian_validity`, `circadian_quality`, `preferred_sleep_period_start_time`,
  `preferred_sleep_period_end_time`. Keep the existing `sleep_time` / `wake_time` /
  `bedtime_window_*` names — they are the readable ones.
- Delete the stale comment and the "unverified / account has no SleepWise data" docstrings on
  `AlertnessDTO` and `CircadianBedtimeDTO`.
- Mapper and `_serialize_sleepwise`.

Capture a real payload to `tests/assets/polar/sleepwise.json` from the store and build the
integration test on it. **Coverage gotcha:** `[tool.coverage.run] source` includes `tests`, so add
the asset and its loader in this phase only, and make sure a test actually reads it.

## Also: document what AccessLink cannot reach

New `docs/api-vs-account-export.md`, and a short "What is not in here" section in the archive
`README.md` template so the receiving agent knows the boundary without being told. From the audit:

- **History.** 28 days, against 2023-07 → 2026-08 in the account export. Already warned about; repeat
  it here because it is the largest single gap.
- **Every baseline.** The account export ships `sleepScoreBaseline`, `remScoreBaseline`,
  `n3ScoreBaseline`, `continuityScoreBaseline`, `efficiencyScoreBaseline`,
  `groupSolidityScoreBaseline`, `longInterruptionsScoreBaseline`, `groupRefreshScoreBaseline`,
  `sleepTimeAverageMinutes`, and on the recharge side `meanBaselineRri`, `sdBaselineRri`,
  `meanBaselineRmssd`, `sdBaselineRmssd`, `meanBaselineRespirationInterval`,
  `sdBaselineRespirationInterval`. AccessLink returns **none** of them. Without baselines an agent
  cannot tell "is 83 ms RMSSD good *for this person*" — it has to derive its own from the window.
- **Sleep-score components.** AccessLink gives 3 of ~10 (`group_duration_score`,
  `group_solidity_score`, `group_regeneration_score`). The account export adds `continuityScore`,
  `efficiencyScore`, `remScore`, `n3Score`, `longInterruptionsScore`, `sleepTimeOwnTargetScore`,
  `sleepTimeRecommendationScore`, `scoreRate`.
- **Interruption counts.** AccessLink gives durations only (`short_interruption_duration` 1350 s,
  `long_interruption_duration` 690 s). The export also gives `totalCount` 36, `shortCount` 31,
  `longCount` 5 — 36 interruptions in 34 minutes reads very differently from 5.
- **Sleep efficiency, span and type.** `efficiencyPercent` (93.05), `sleepSpan`, `asleepDuration`,
  `sleepType` (`SLEEP_PLUS_STAGES`), and the `feedback` code are absent. Efficiency is derivable from
  `sleep_start_time`/`sleep_end_time` and the stage totals — consider computing it as a `@property`
  on `Sleep` rather than pretending it is unavailable.
- **Hypnogram resolution.** AccessLink is minute-keyed with numeric codes; the account export is
  30-second state changes with named states (`NONREM2`, `NONREM3`, `REM`, `WAKE`).
- **Per-cycle detail.** AccessLink gives `sleep_cycles: 7`, a count. The export has the array.
- **Skin-temperature series**, `sensorLocation`, and skin-contact intervals (`type: 8`
  `generic-period` records) — aggregate only via the API, as above.
- **PPI / beat-to-beat samples.** 48 `ppi_samples_*` files in the account export, no AccessLink
  endpoint at all.

Frame it as "here is the boundary and why", not as a bug list. Do **not** add a scraper for
flow.polar.com and do not add an account-export importer — both are out of scope for this phase, and
the second is worth its own discussion first.

## Tests

- One unit test per mapper change asserting the new field survives the round trip, and one asserting
  the removed skin-temperature fields are gone from the serialized night.
- Update `tests/assets/polar/*.json` where the shape is now verified, and the factories under
  `tests/unit/factories/` for every changed entity.
- An integration test that exports a night carrying all four newly-kept things and re-opens the zip
  to assert they are in `nights.json` — not just in `raw/`. That single assertion is the whole point
  of the phase.
- `merge_nights` is unaffected; check its tests still compile against the changed entities.

## Acceptance criteria

- `make lint` clean, `make test` green at 100 % branch coverage.
- A real `polarexport night` produces a `nights.json` where, for a night with full data:
  `sleep.heart_rate_samples` is non-empty, `recharge.hrv_samples` and `.breathing_samples` are
  non-empty, `skin_temperature.celsius` is a number and `skin_temperature` has no `samples` /
  `sleep_start` / `sleep_end` keys, and `sleepwise.grade` is a number.
- No mapper or DTO docstring still claims a shape is unverified when a live payload exists on disk.
- `docs/api-vs-account-export.md` exists and the archive README's "what is not in here" section
  matches it.
