# Phase 11 — Layering cleanup and test-suite gaps

**Depends on:** phases 4–8. **Needs a Polar token:** no.

## Goal

Four small violations of rules `CLAUDE.md` states explicitly. None changes behaviour today; each one
is the kind of thing that quietly becomes load-bearing before it gets fixed. Low risk, do them
together.

---

## 1. The export use case touches the filesystem

`CLAUDE.md`: *"Use cases never print and never touch the filesystem directly."*

`polarexport/application/use_cases/night_export.py`:

```python
return ExportReport(
    archive_path=archive_path,
    archive_size_bytes=archive_path.stat().st_size,   # <- filesystem I/O in the application layer
    ...
)
```

It is also a blocking syscall on the event loop, and it forces every unit test of the use case to
create a real file on disk just to satisfy a mock archiver (see the `archive_path` fixture in
`tests/unit/application/use_cases/test_night_export.py`, which writes `b"archive-content"` for no
reason other than this line).

**Fix.** The archiver already knows the size it wrote. Change `NightArchiverPort.write` to return the
path *and* the byte count — either a small frozen `ArchiveResult` dataclass beside the port, or a
`tuple[Path, int]`. Prefer the dataclass; the port is a public interface and a named field beats a
positional int. Update `ZipNightArchiver`, the use case, and the unit fixtures (which can then stop
writing real files).

## 2. A store adapter imports from a provider adapter

`polarexport/infrastructure/adapters/stores/filesystem.py`:

```python
from polarexport.infrastructure.adapters.providers.polar.endpoints import API_NAME
```

The filesystem store is not Polar-specific and should not depend on the Polar client package. Move
`API_NAME` somewhere neutral — `polarexport/domain/const.py` is the natural home given it is a stable
identifier baked into the on-disk layout, and `endpoints.py` can re-export or import it.

## 3. The API name exists twice

`polarexport/application/use_cases/night_sync.py` declares its own copy:

```python
_POLAR_API_NAME: Final[str] = "polar-accesslink-v3"
```

while `endpoints.py` declares `API_NAME` with the identical value. Two sources of truth for a string
that determines an on-disk directory name. They agree today; nothing enforces that.

Related latent inconsistency in the same area — worth fixing while you are here:
`FilesystemNightStore._path_for` derives the directory from `self._api` (constructor arg) while
`_write_sync` writes `stored.api` into the envelope. A `StoredPayload` whose `api` differs from the
store's would be filed under one API name and self-describe as another. Either derive the path from
`stored.api` on write, or reject the mismatch — do not leave both.

Collapse all of this to one constant after fixing item 2.

## 4. Missing integration tests for the use cases

`tests/integration/application/use_cases/` contains only `__init__.py`. Phase 4 specified integration
coverage there, and `CLAUDE.md` names integration tests the primary focus with the mirror rule as
"one test file per source file — never consolidate".

The CLI integration test (`tests/integration/infrastructure/entrypoints/cli/commands/test_night.py`)
does exercise both use cases end to end, which is why coverage is still 100% — so this is a
structural gap, not a coverage gap. Judgement call worth making deliberately:

- **A.** Add `test_night_sync.py` and `test_night_export.py` under
  `tests/integration/application/use_cases/` — real `FilesystemNightStore` on `tmp_path`, real
  `PolarNightMapper`, real `ZipNightArchiver`, WireMock-backed client for sync. Follows the stated
  convention; some overlap with the CLI test.
- **B.** Delete the empty directory and note in `CLAUDE.md` that use-case integration coverage lives
  in the CLI test. Honest about what the suite actually does.

Do not leave an empty directory implying tests that do not exist.

---

## Also worth a decision (not a defect)

The archive's `raw/` entries are bare payloads: `NightArchiverPort.write` receives
`Mapping[NightSource, Mapping[date, dict[str, Any]]]`, so the store's provenance envelope
(`fetched_at`, `api`, `schema_version`) is stripped before it reaches the archiver. Phase 7 flagged
this deliberately rather than inventing fields.

Consequence: an archive cannot tell its reader *when* a payload was fetched or which API version
produced it — exactly the questions an agent analysing stale data would want answered. Consider
passing `StoredPayload` through to the archiver instead of the unwrapped dict, and writing the full
envelope into `raw/`. Cost: the archiver's signature carries an application-layer type (already true
of `ExportManifest`, so no new precedent).

## Acceptance criteria

- [ ] No `application/` module performs filesystem I/O.
- [ ] No adapter package imports from a sibling adapter package.
- [ ] Exactly one definition of the API-name constant.
- [ ] `tests/integration/application/use_cases/` either holds tests or no longer exists.
- [ ] `make lint` clean, `make test` green at 100% branch coverage.
