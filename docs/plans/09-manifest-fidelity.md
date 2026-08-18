# Phase 9 — Manifest fidelity

**Depends on:** phases 4–8 (all complete). **Needs a Polar token:** no.

## Goal

`manifest.json` currently contains two fields that are **fabricated rather than measured**. The
archive is fed to an AI agent as ground truth, so a manifest that quietly lies is worse than one that
omits the field entirely — the agent has no way to detect the lie and will reason from it.

Reproduce before changing anything:

```bash
# store SLEEP for five days, store nothing for the other four sources, export all five
# → manifest.json reports every source "available" and every request count 0
```

Observed on 2026-08-18 with a store holding **only** sleep payloads:

```json
"source_availability": {"sleep":"available","recharge":"available","skin-temperature":"available",
                        "sleepwise":"available","heart-rate":"available"},
"request_counts": {"sleep":0,"recharge":0,"skin-temperature":0,"sleepwise":0,"heart-rate":0}
```

Both are wrong. Four of those sources have zero bytes on disk, and the sync that populated the store
issued real requests.

---

## Problem 1 — `source_availability` is hardcoded

`polarexport/application/use_cases/night_export.py`:

```python
source_availability={
    source: SourceAvailability.AVAILABLE if source in night_in.sources else SourceAvailability.NOT_REQUESTED
    for source in NightSource
},
```

Every requested source is asserted `available` without consulting the store. This value also feeds
`$SOURCE_AVAILABILITY_TABLE` in the archive's bundled `README.md`, so the falsehood is stated twice
in every archive.

`SourceAvailability` has no member for the common case "requested, consent fine, but nothing on
disk for this range":

| Member | Means |
|---|---|
| `AVAILABLE` | data present |
| `UNAVAILABLE` | 403 — consent missing |
| `NOT_REQUESTED` | not in `--source` |

### Decision required before implementing

Do not guess — pick one and state it in the commit message:

- **A (recommended).** Add `NO_DATA = "no_data"` to `SourceAvailability`. In the export use case, a
  requested source resolves to `AVAILABLE` when it produced at least one mapped entity, else
  `NO_DATA`. Honest, self-describing, and keeps `UNAVAILABLE` meaning exactly what its comment says.
- **B.** Reuse `UNAVAILABLE` for the empty case. Smaller diff, but conflates "you never granted
  consent" with "your watch had nothing" — two problems with different user remedies.

If A: document the new member in the archive `README.md` template so the receiving agent can
interpret it, and check `_render_source_availability_table` still renders correctly.

## Problem 2 — `request_counts` is always zero

```python
request_counts={source: 0 for source in sources_requested},
```

`NightSyncUseCase` measures this correctly (`SourceSyncStat.requests`, sourced from
`SourceFetchResult.request_count`) and reports it via `SyncReport`. The CLI holds both reports — but
`night_logic` runs sync and export as independent calls and never passes the sync numbers into the
export.

### Decision required

- **A (recommended).** Drop `request_counts` from `ExportManifest` entirely. It is provenance about
  *how the store was filled*, which is a property of the sync, not of the archive. `--no-refresh`
  exports have no meaningful value for it at all. Removing a field beats shipping a zero.
- **B.** Thread it through: `NightExportUseCase.export(..., request_counts: Mapping[NightSource, int] | None)`,
  populated by `night_logic` from `sync_report`, `None` under `--no-refresh` and serialized as
  `null`. Preserves the field, at the cost of coupling two use cases the CLI currently keeps
  independent.

Whichever is chosen, `manifest.json` must never again contain a hardcoded literal presented as a
measurement.

---

## Files touched

```
polarexport/domain/enums.py                                    # option A of problem 1
polarexport/domain/entities/export.py                          # option A of problem 2
polarexport/application/use_cases/night_export.py
polarexport/infrastructure/adapters/archivers/serializers.py
polarexport/infrastructure/adapters/archivers/templates/README.md
polarexport/infrastructure/entrypoints/cli/commands/night.py   # export table column
```

## Tests

- Unit, `tests/unit/application/use_cases/test_night_export.py`: a requested source with zero stored
  payloads is **not** reported `AVAILABLE`; a requested source with payloads is.
- Integration, `tests/integration/infrastructure/adapters/archivers/test_zip.py`: assert the rendered
  `manifest.json` and the archive `README.md` table agree with what the store actually held.
- If problem 2 option B is chosen, add a CLI unit test proving `--no-refresh` serializes `null`
  rather than `0`.

## Acceptance criteria

- [ ] Exporting a range where only `sleep` has data yields a manifest that does not claim the other
      four sources are available.
- [ ] No field in `manifest.json` is a hardcoded constant standing in for a measurement.
- [ ] The archive `README.md` explains every `source_availability` value it can emit.
- [ ] `make lint` clean, `make test` green at 100% branch coverage.
