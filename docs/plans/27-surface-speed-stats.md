# Phase 27 — Surface speed statistics in the archive

**Depends on:** phases 23 and 24, both done.
**Needs a Polar token:** no — `tests/assets/polar/exercises.json` already holds an outdoor session.
**Size:** small. One commit.

## Where this came from

The original request asked for "speed (min, max, avg for jogging)". The archive currently ships
`average_speed_kmh` and nothing else: **there is no `speed` block in `exercises.json` at all**, so two
of the three requested figures are missing.

The cause is a hand-off gap between two phases that were written to be parallelisable:

- **Phase 23 did its job.** It said populate `SpeedStats` only if the live capture contained an
  outdoor session that let the sample units be verified. The capture did — a 5.008 km walk — and the
  units were checked honestly: the type-1 series averages 4.36 against a `distance / duration` of
  4.235 km/h, so the series is already km/h and the "multiply by 3.6" trap was correctly avoided.
  `_speed_stats_from_samples` is sound and tested.
- **Phase 24 was written against the other branch.** Its serializer assumed speed would be
  unavailable, so `_serialize_exercise` never emits it.

The result is dead data: `Exercise.speed` is assigned in `mappers.py:255` and read nowhere in the
codebase. Coverage stayed at 100 % because the mapper is unit-tested directly, which is exactly the
kind of gap coverage cannot catch.

## 1 — Fix the stale entity docstring first

`polarexport/domain/entities/exercise.py`, the `average_speed_kmh` property, still says the
sample-derived figures in `speed` "are not [trustworthy] — see phase 23". That was written in phase 21,
*before* phase 23 verified the units. It now contradicts the verified mapper it points at.

Rewrite it to say what is actually true: both figures are trustworthy and they measure different
things. `average_speed_kmh` is the whole-session average including stopped time; the `speed` block
comes from the sample series. Keep both — an agent comparing them can see how much of a session was
spent stationary.

## 2 — Do not ship `minimum_kmh` as it stands

`_speed_stats_from_samples` takes `min()` over every present sample, including zeros. The walking
session in the asset has **305 zero samples out of 4 257** — every pause, traffic light and GPS
dropout — so `minimum_kmh` would be `0.0` for essentially any outdoor session. "Minimum speed:
0 km/h" tells an agent nothing.

This is also inconsistent with the codebase's own precedent. `heart_rate_stats` in
`domain/services/exercise_metrics.py` deliberately drops non-positive samples, with the reasoning that
a zero is a dropout and `"minimum: 0"` would be "actively misleading". Speed deserves the same
treatment.

Change the minimum to the smallest **positive** sample and leave the average over all present samples
(so it stays comparable to `average_speed_kmh`). Say so in the docstring, in the same voice as
`heart_rate_stats`. For the asset's walk that gives a minimum of `0.0285` rather than `0.0`.

A moving-average variant — averaging only positive samples, 4.697 km/h for that walk — is genuinely
useful for a runner, but it is a *fourth* statistic and the request asked for three. Do not add it
here; note it as a possible follow-up and move on.

## 3 — Serialize the block

`exercise_serializers.py::_serialize_exercise`. Add `speed` next to `average_speed_kmh`, so the two
speed views sit together:

```json
"speed": {
  "average_kmh": 4.36,
  "maximum_kmh": 12.4725,
  "minimum_kmh": 0.0285
}
```

`null` for the whole block when there is no usable series — which is every indoor session, where Polar
returns the field as all zeros. The existing "a series with no positive value is treated as absent"
rule in the mapper already handles that; make sure the serializer emits `"speed": null` rather than
dropping the key, matching the README's "every key is present even when its value is `null`" promise.

Round `maximum_kmh` and `minimum_kmh` to 4 decimals as `average_kmh` already is. `12.4725` is fine;
an unrounded float artefact in the archive is not.

## 4 — Document it

`templates/exercise-README.md`, the `exercises.json` field table. Add rows for the three `speed`
fields and — this is the part that matters for an agent reading the archive — state plainly how they
differ from `average_speed_kmh`:

| Field | Unit | Meaning |
|---|---|---|
| `average_speed_kmh` | km/h | **Derived** from `distance_km / duration`. Includes stopped time |
| `speed.average_kmh` | km/h | Mean of Polar's per-second speed series, including zero samples. Close to `average_speed_kmh`; a large gap means the series has gaps |
| `speed.maximum_kmh` | km/h | Fastest recorded sample |
| `speed.minimum_kmh` | km/h | Slowest **moving** sample — zero samples are excluded as pauses, so this is never `0` |

Add one line saying the whole block is `null` for indoor sessions, and one saying the units were
verified against a session with a known distance rather than assumed.

## 5 — Tests

- Mapper unit test: the all-zero indoor series still yields `None` (this test exists — keep it green).
- Mapper unit test: a series containing zeros yields a **positive** `minimum_kmh`, not `0.0`. This is
  the regression this phase exists to prevent.
- Serializer unit test: a session with speed emits the three fields; one without emits `"speed": null`
  with the key present.
- Integration: assert the walking session in the archive carries a `speed` block whose `average_kmh`
  is within ~0.5 km/h of its `average_speed_kmh` — that closeness is the evidence the units are right,
  so make it an assertion rather than a comment.

## Acceptance

- `exercises.json` carries `speed` for the outdoor sessions and `"speed": null` for the indoor ones.
- No `minimum_kmh` of `0.0` for a session that was moving.
- `grep -rn "\.speed\b" polarexport/` shows a reader, not just the mapper's writer.
- The `average_speed_kmh` docstring no longer calls the `speed` block untrustworthy.
- `make lint` clean, `make test` green at 100 % branch coverage.
