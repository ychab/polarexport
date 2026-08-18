# Phase 14 — The manifest still cannot say "consent missing"

**Depends on:** phase 9 (complete). **Needs a Polar token:** no.
**Size:** small. Good candidate to bundle with phase 12 in one session.

## Goal

Phase 9 fixed the fabricated `source_availability` by measuring it — a requested source is
`AVAILABLE` when it produced at least one mapped entity, else `NO_DATA`. That is a real improvement,
but it left one of the four enum members unreachable from the archive.

`SourceAvailability.UNAVAILABLE` means "403 — consent missing". It is produced correctly by
`PolarAccessLinkClient` (four sites in `client.py`), carried into `SourceFetchResult`, and reported
in `SourceSyncStat.availability`, which the CLI's Sync table displays. But `NightExportUseCase`
derives availability purely from what it could map out of the store, and the store holds nothing for
a 403 source. So:

**A source the user has not consented to is reported in `manifest.json` as `no_data`.**

Those are different problems with different remedies. `no_data` means "your watch recorded nothing —
nothing to do". `unavailable` means "go to account.polar.com and grant consent". The archive is read
by an AI agent that has no other way to tell them apart, and the user reading the export table sees
the same conflation.

Verify before changing anything: revoke one source's consent at account.polar.com (or stub a 403 in
WireMock), run a sync + export, and read `manifest.json`.

## Why phase 9 did not do this

Phase 9 chose option A for `request_counts` — drop it rather than couple the two use cases —
precisely because `night_logic` runs sync and export as independent calls. This item needs the
opposite: some sync knowledge must reach the export. That is why it is its own phase and its own
decision, not an oversight to fix silently.

## Decision required before implementing

Do not guess — pick one and state it in the commit message.

- **A (recommended).** Record availability in the store. `StoredPayload` already carries a provenance
  envelope; a 403 is provenance too. Write a per-source marker (e.g. `data/<api>/<source>/_status.json`
  holding `{"availability": "unavailable", "observed_at": …}`) that the sync writes and the export
  reads through a new `NightStorePort.read_availability(source) -> SourceAvailability | None`.
  Keeps the two use cases decoupled — they keep communicating only through the store, which is the
  design the whole tool is built on — and it survives `--no-refresh`, where there is no sync at all
  to ask.
- **B.** Thread it through the CLI: `NightExportUseCase.export(..., availability_overrides:
  Mapping[NightSource, SourceAvailability] | None)`, populated by `night_logic` from `sync_report`.
  Smaller diff. But under `--no-refresh` there is no sync report, so the archive silently loses the
  distinction again — which is the same class of bug being fixed here.

Option A costs more and is the one that actually holds. Pick B only if the extra store surface is
judged not worth it, and if so, document the `--no-refresh` limitation in the archive `README.md`.

## Secondary item, same file

`NightSyncUseCase._sync_source` returns a hardcoded `availability=SourceAvailability.AVAILABLE` on
its early-return path:

```python
if not missing:
    return SourceSyncStat(availability=SourceAvailability.AVAILABLE, fetched=0, skipped=skipped, ...)
```

Nothing was asked of Polar on that path, so nothing was measured — this is the same "hardcoded
literal presented as a measurement" that phase 9 set out to eliminate, just in the sync report
rather than the manifest. If option A is chosen it fixes itself: read the stored marker instead.
Under option B, state the wrinkle in a comment at minimum.

## Files touched

Option A:
```
polarexport/application/ports/stores/night.py
polarexport/infrastructure/adapters/stores/filesystem.py
polarexport/application/use_cases/night_sync.py
polarexport/application/use_cases/night_export.py
polarexport/infrastructure/adapters/archivers/templates/README.md   # if the wording needs it
```

## Tests

- Unit, `test_night_export.py`: a source recorded `UNAVAILABLE` reports `unavailable` in the manifest,
  **not** `no_data` — and a source with genuinely no payloads still reports `no_data`. Both, in the
  same test module; the whole point is that they are distinguishable.
- Integration, `tests/integration/application/use_cases/test_night_sync.py`: a WireMock 403 for one
  source leaves the other sources syncing normally *and* leaves a durable record that a later export
  can read.
- Integration, `test_zip.py`: `manifest.json` and the rendered archive `README.md` agree, with
  `unavailable` present in both.

## Acceptance criteria

- [ ] A source with missing consent is reported `unavailable` in `manifest.json`; a source with
      consent but no recorded nights is reported `no_data`.
- [ ] The distinction survives `--no-refresh` (option A), or its loss is documented in the archive
      `README.md` (option B).
- [ ] All four `SourceAvailability` members are reachable in a real export, and each is explained in
      the archive `README.md`.
- [ ] No `SourceSyncStat` or `ExportManifest` field is a hardcoded literal standing in for a
      measurement.
- [ ] `make lint` clean, `make test` green at 100% branch coverage.
