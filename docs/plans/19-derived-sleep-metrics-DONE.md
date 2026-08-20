# Phase 19 — Derived sleep metrics & audit corrections

> Depends on: phases 15–18 (complete). Needs a Polar token: **no** — the local store already holds
> everything this phase needs.

## Where this came from

The 2026-08-20 audit of the export `polarexport-nights-2026-07-24_2026-08-20.zip` against a second
Polar account export (`polar-user-data-export_b084424e…zip`, generated 2026-08-05), overlapping on
13 nights (2026-07-24 → 2026-08-05).

**The audit came back clean.** Every value polarexport exports matches the account export exactly
where both carry it — continuity, continuity class, all three group scores, device id, and, once
units are normalised, interruptions and stage durations:

| Field | Ours | Account export |
|---|---|---|
| `continuity` / `continuity_class` | 2.3 / 2 | `continuityIndex` 2.3 / `continuityClass` 2 |
| `group_solidity_score` | 62.8425 | 62.8425 |
| `total_interruption_duration` | 2040 s | `PT34M` |
| `stages.light_seconds` | 18240 s | `PT5H4M` |
| `heart_rate_variability_avg` | 83 | `meanNightlyRecoveryRmssd` 83 |
| `beat_to_beat_avg` | 1209 | `meanNightlyRecoveryRri` 1209 |

Continuity in particular is a **direct Polar metric**, not something computed locally, and it matched
on all 13 overlapping nights with no drift. The only true value difference is `sleep_score`, which
AccessLink rounds to an integer (78) where the account export keeps four decimals (77.9029) — Polar's
rounding, not ours, and nothing to fix.

Phase 18 is verified: the legacy-layout warning now prints exactly once under the default handlers,
`["cli"]` alone still emits it, and warnings land on stderr. `make lint` clean, `make test` green at
396 passed / 100 % branch coverage.

What follows is one small feature the audit justified with hard numbers, plus three corrections to
documentation the audit proved imprecise.

---

## 1. Add `efficiency_percent` as a derived property on `Sleep`

`docs/api-vs-account-export.md` currently lists sleep efficiency under what AccessLink does not give,
noting it "is derivable … so nothing is truly lost here". Phase 16's plan suggested computing it and
it was never done. The audit confirms the derivation is not approximate — it is exact:

```
asleep = light + deep + rem            = 27330 s   (account: asleepDuration PT7H35M30S = 27330 s)
span   = sleep_end_time - sleep_start  = 29370 s   (account: sleepSpan       PT8H9M30S  = 29370 s)
27330 / 29370 * 100 = 93.0541          (account: efficiencyPercent 93.05413687436159)
```

Agreement to four decimal places on the audited night. Both inputs are already in `nights.json`, so
this is pure presentation — an agent reading the archive currently has to know the formula and that
`unrecognized_seconds` is excluded from "asleep".

**Implement** as a `@property` on the `Sleep` entity, not a stored field — it is dynamic and derived,
which is exactly what CLAUDE.md reserves `@property` for:

```python
@property
def efficiency_percent(self) -> float | None:
    if self.stages is None or self.sleep_start_time is None or self.sleep_end_time is None:
        return None
    span_seconds = (self.sleep_end_time - self.sleep_start_time).total_seconds()
    if span_seconds <= 0:
        return None
    asleep = self.stages.light_seconds + self.stages.deep_seconds + self.stages.rem_seconds
    return asleep / span_seconds * 100
```

Return `None` rather than raising when any input is absent — every field it reads is `X | None`, and a
night with no stages is normal, not an error. Guard `span_seconds <= 0` explicitly; do not `assert`.

Note `unrecognized_seconds` is deliberately excluded from `asleep`: the account export's
`asleepDuration` (27330 s) equals light + deep + rem exactly, and `phaseDurations.unknown` is its own
bucket alongside `wake`. Put that reasoning in a short comment — it is the kind of thing a later reader
would otherwise "fix" wrongly.

Add it to `_serialize_sleep` in `archivers/serializers.py` and document it in the archive `README.md`
template beside the other sleep fields: units (percent), the formula, and that Polar's own
`efficiencyPercent` agrees to four decimals. Then update the "Sleep efficiency, span and type"
section of `docs/api-vs-account-export.md` — efficiency moves from "not handed over" to "derived and
present in `nights.json`"; `sleepSpan`, `asleepDuration`, `sleepType` and `feedback` stay listed as
account-export only.

## 2. `sleep_cycles` is not off by one — document the fencepost

The audit compared AccessLink's `sleep_cycles` against the number of entries in the account export's
`sleepResult.sleepCycles.cycles.sleepCycleModels`, on all 13 overlapping nights:

```
ours   5  6  5  5  5  6  6  7  5  4  3  6  7
acct   6  7  6  6  6  7  7  8  6  5  4  7  8
diff  +1 +1 +1 +1 +1 +1 +1 +1 +1 +1 +1 +1 +1
```

Constant `+1`, never anything else. `sleepCycleModels` entries are cycle *boundaries* — each carries a
`secondsFromSleepStart` and a `sleepDepthStart` — so *n+1* boundaries delimit *n* cycles and the two
sources agree exactly. **Nothing to fix here.** The point of writing it down is so that the next person
to run this comparison does not "correct" `sleep_cycles` by adding one. Add it to
`docs/api-vs-account-export.md` under the per-cycle section.

## 3. Correct the "Per-cycle sleep detail" section

That section currently says the account export "has the full array of individual cycles". That
undersells and mis-describes it. What it actually carries is a **sleep-depth curve**: each boundary is
`{"secondsFromSleepStart": 49695, "sleepDepthStart": 0.8860457}` — a normalised 0–1 depth at each
cycle boundary, not a per-cycle record with stage breakdowns. Rewrite the section to say that, since
"array of individual cycles" invites someone to look for something that is not there.

## 4. Decide the export archive's file mode

`data/export/*.zip` lands at mode **0600**, and nothing in `archivers/zip.py` chose that — it falls out
of `tempfile.mkstemp`, which creates at 0600, followed by `tmp_path.replace(target)` which preserves
it. `credentials.json`'s 0600 is deliberate and documented; the archive's is an accident of the
atomic-write mechanism.

0600 is defensible — these archives are personal health data. But an archive whose entire purpose is
to be attached to a prompt or handed to someone should have a mode that was *chosen*. Make it explicit
in `_write_sync` with a one-line comment saying which it is and why:

- keep 0600 → `os.fchmod(fd, 0o600)` before writing, matching `JsonCredentialsStore`; or
- widen to honour the user's umask → `os.fchmod(fd, 0o666 & ~current_umask())`.

**Recommend keeping 0600** and stating the reason (nightly biometrics, same class of data as the
token). The value is that it becomes a decision with a test pinning it, not an artifact of `mkstemp`.

---

## Files

| File | Change |
|---|---|
| `polarexport/domain/entities/sleep.py` | add `efficiency_percent` property |
| `polarexport/infrastructure/adapters/archivers/serializers.py` | serialize it |
| `polarexport/infrastructure/adapters/archivers/templates/README.md` | document it |
| `polarexport/infrastructure/adapters/archivers/zip.py` | make the archive mode explicit |
| `docs/api-vs-account-export.md` | items 1, 2 and 3 |

## Tests

- `tests/unit/domain/entities/test_sleep.py` — the audited night reproduces 93.0541 to four decimals
  (use the real numbers above, they are a known-good fixture); `None` when stages, start or end is
  absent; `None` when start equals end; `unrecognized_seconds` does not count toward asleep.
- `tests/unit/infrastructure/adapters/archivers/test_serializers.py` — `efficiency_percent` present in
  the serialized sleep dict, and `None` for a `Sleep` lacking stages.
- `tests/integration/…/test_zip.py` — the written archive's mode is 0600.

## Acceptance criteria

- `make lint` clean, `make test` green at 100 % branch coverage.
- A real export's `nights.json` carries `efficiency_percent` on every night that has stages and a
  start/end time, and `null` on the rest.
- `docs/api-vs-account-export.md` no longer lists efficiency as unavailable, explains the `sleep_cycles`
  fencepost, and describes the depth curve accurately.
