# Phase 28 — `speed.minimum_kmh` is sensor noise, not a pace

**Depends on:** phase 27, done.
**Needs a Polar token:** no — the committed asset's walking session is enough.
**Size:** small. One commit.

## Where this came from

Phase 27 shipped the `speed` block correctly: the key is always present, `null` for indoor sessions,
`average_kmh` and `maximum_kmh` are sound, and the units are right. Only `minimum_kmh` is wrong.

Phase 27 told the implementer to exclude zero samples so the minimum would stop being `0.0`. That was
done, and it did not fix the problem — it only moved it. A live archive gives:

| Session | `minimum_kmh` | In plain terms |
|---|---|---|
| Running | **0.0004** | 40 cm per hour |
| Walking | **0.0285** | 28 metres per hour |
| Walking | **0.1852** | 185 metres per hour |

None of these is a pace. They are stopped samples that happen to carry float noise instead of an
exact zero, so the `> 0` filter waves them through.

The asset's walking session shows why the filter can never work as written. Of 4 257 samples: 305 are
exactly `0`, but only **10** fall between 0 and 0.5 km/h and only **28** below 1 km/h — while the 5th
percentile of the moving samples is **3.114 km/h** and the median is 4.581. The minimum is therefore
drawn from a ten-sample noise tail sitting far below the real distribution. Taking `min()` over that
returns the worst artefact in the series, every time, by construction.

The README now makes a promise the data does not keep — it says the field is the "slowest **moving**
sample" and that "zero samples are excluded as pauses, so this is never `0`". Literally true. But
`0.0004 km/h` is a pause, and presenting it as a moving pace is worse than the `0.0` phase 27 set out
to remove: `0` at least reads as obviously absent, whereas `0.0004` looks like a measurement.

## The real problem

A raw minimum over a stop-start activity is not a meaningful statistic and no threshold makes it one.
Raising the cutoff to 1 km/h just returns whatever sample sits nearest above 1 km/h — still a single
outlier, now with an arbitrary constant attached. The statistic has to become robust, not
better-filtered.

## 1 — Replace the raw minimum with a percentile

In `_speed_stats_from_samples`, compute the field from the **5th percentile of moving samples**
rather than their minimum. Define "moving" with a named module constant —
`_SPEED_MOVING_THRESHOLD_KMH = 1.0` — with a comment saying it exists to drop stopped samples that
carry float noise instead of an exact zero, and citing the 28-samples-below-1-km/h figure as the
evidence it is not arbitrary.

Use `statistics.quantiles(moving, n=20)[0]`. That needs at least two data points; fall back to
`min(moving)` when there are fewer, and return `None` when there are no moving samples at all (which
is what already happens for indoor sessions — keep that behaviour exactly).

For the asset's walk this yields roughly **3.11 km/h** instead of 0.0285 — a slow but real walking
pace, which is what the field was always meant to convey.

**Rename it.** `minimum_kmh` describing a percentile is the same dishonesty in a new place. Call it
`slowest_sustained_kmh`, in both `SpeedStats` and the serialized JSON. The archive has no backwards
compatibility to protect — phase 27 is one commit old and unreleased.

## 2 — Add `moving_average_kmh`

Phase 27 deliberately refused this on the grounds that the request asked for three figures and this
would be a fourth. That reasoning no longer holds: with the minimum becoming a percentile, the block
has no plain "how fast were you actually moving" number, and for a run that is the single most useful
figure in it. It is the mean of the same moving samples already being computed — nearly free.

Keep `average_kmh` as it is (mean over all present samples including zeros) so it stays comparable to
`average_speed_kmh`. The pair is the point: `average_kmh` includes stopped time, `moving_average_kmh`
does not, and the gap between them is how much of the session was spent stationary.

## 3 — Fix the README

`templates/exercise-README.md`, the speed rows. Drop the "never `0`" claim — it was true and
misleading at once. State for each field what it is computed from, and say plainly that a raw minimum
speed is not reported **because** a stop-start session makes it meaningless. An agent reading the
archive should understand why the obvious statistic is absent, or it will assume the export forgot it.

## 4 — Tests

- Mapper unit test built from a series with a deliberate noise tail — a handful of values around
  `0.0004` beneath a realistic 3–5 km/h body — asserting `slowest_sustained_kmh` lands in the body,
  not the tail. This is the regression the phase exists for; write it first and watch it fail against
  the current code.
- Mapper unit test: a series with exactly one moving sample returns that sample, no crash from
  `quantiles`.
- Mapper unit test: all-zero indoor series still returns `None` (exists — keep green).
- Serializer and integration tests updated for the renamed field and the new one.
- Integration: the walking session's `slowest_sustained_kmh` is greater than 1.0 — a blunt assertion
  that noise is no longer reaching the archive.

## Acceptance

- No session in a real archive reports a sub-1 km/h pace for a walk or a run.
- `average_kmh` unchanged; `moving_average_kmh` present and greater than `average_kmh` for any session
  containing pauses.
- The README no longer claims a minimum that is not reported.
- `make lint` clean, `make test` green at 100 % branch coverage.
