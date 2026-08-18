# Phase 7 — Zip archiver

**Depends on:** phase 4 (independent of phases 5 and 6). **Needs a Polar token:** no.

## Goal

Implement `NightArchiverPort` as a zip writer. This is the actual product: the archive is what gets
attached to a prompt, so its legibility to an AI agent is the design constraint.

Everything it writes comes from the local `data/` store, never from the API.

## Reference

```
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/entrypoints/cli/commands/taste/export.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/adapters/http.py   # async-adapter shape
```

---

## Archive contents

```
polarexport-nights-2026-07-20_2026-08-16.zip
├── manifest.json
├── README.md
├── nights.json
└── raw/
    ├── sleep/2026-08-15.json
    ├── nightly-recharge/2026-08-15.json
    ├── skin-temperature/2026-08-15.json
    ├── sleepwise/2026-08-15.json
    └── continuous-heart-rate/2026-08-15.json
```

`raw/` is present only when `include_raw` is true. The `raw/<source>/` directory names are exactly the
`NightSource` enum values.

### `nights.json`

A single JSON object, not a bare array — an envelope leaves room to grow and tells the reader what it
is holding:

```json
{
  "schema_version": 1,
  "date_range": {"date_min": "2026-07-20", "date_max": "2026-08-16"},
  "night_count": 21,
  "nights": [ { "date": "2026-07-20", "sleep": {...}, "recharge": {...}, "skin_temperature": {...}, "sleepwise": {...}, "heart_rate": {...} } ]
}
```

Rules:
- Nights sorted ascending by date.
- Missing sources serialise as `null`, never as `{}` or an omitted key — the reader must be able to
  distinguish "not measured" from "measured as zero".
- Timestamps as ISO-8601 with offset, exactly as Polar reported them. Do not normalise to UTC: the
  local offset is meaningful sleep context.
- Stable key order (`sort_keys` off, but build the dicts in a fixed order) and `indent=2`. The file is
  read by a human and a model, not parsed at scale.
- `ensure_ascii=False`.

### `manifest.json`

Serialised from `ExportManifest`:

```json
{
  "tool": "polarexport",
  "tool_version": "0.1.0.dev0",
  "generated_at": "2026-08-16T14:03:11+00:00",
  "api": "polar-accesslink-v3",
  "date_range": {"date_min": "...", "date_max": "..."},
  "night_count": 21,
  "sources": {
    "sleep": {"availability": "available"},
    "skin-temperature": {"availability": "unavailable"}
  },
  "gaps": ["2026-07-22", "2026-07-29"],
  "oldest_fetched_at": "2026-07-20T08:00:00+00:00",
  "newest_fetched_at": "2026-08-17T09:12:44+00:00",
  "history_window_warning": "Polar AccessLink v3 retains only the last 28 days; dates before 2026-07-20 come from the local store."
}
```

The `*_fetched_at` pair comes from the `StoredPayload` envelopes and tells the reader how fresh the
underlying capture is — an archive can legitimately contain nights captured months apart, since it is
built from the accumulating `data/` store.

**The access token and user id must never appear in the manifest.**

### `README.md`

A template shipped inside the package (a module-level string constant or a `.md` file loaded via
`importlib.resources` — prefer the latter, and register it in
`[tool.hatch.build.targets.wheel]` so it ships in the wheel). Rendered with the manifest values.

It must let an AI agent interpret `nights.json` **without consulting Polar's documentation**:

- What this archive is and where it came from.
- The 28-day retention caveat and what `gaps` means.
- A field-by-field table for each source: name, unit, and meaning. Be explicit about units —
  durations in **seconds**, temperature as a **deviation in °C**, `sleep_goal` in seconds.
- The scales: `continuity` (1.0–5.0, higher is better), `continuity_class`, `sleep_score` (1–100),
  `sleep_charge` / `ans_charge` / `nightly_recharge_status` (1–6, higher is better), `sleep_rating`.
- The hypnogram encoding: `"HH:MM" → stage code`, with the code→stage mapping table generated from the
  `SleepStage` enum so it can never drift from the code.
- That `null` means "not reported by the device", distinct from zero.
- A note that `raw/` holds the untouched API payloads if a field is missing from `nights.json`.
- That nights may have been captured at different times (see `oldest_fetched_at` /
  `newest_fetched_at`), because the archive is built from a local store that accumulates over time
  rather than from a single API call.

Generate the scale tables from `domain/enums.py` (via the `label` properties added in phase 3) rather
than hardcoding them twice.

---

## `polarexport/infrastructure/adapters/archivers/zip.py`

```python
class ZipNightArchiver(NightArchiverPort):
    async def write(self, nights, manifest, raw, *, output_dir, include_raw, force) -> Path: ...
```

Behaviour:
1. `output_dir.mkdir(parents=True, exist_ok=True)`.
2. Target name from `ARCHIVE_NAME_TEMPLATE`. If it exists and `not force` → raise
   `ArchiveAlreadyExistsError`.
3. Write to a temporary file **in the same directory** (`tempfile.NamedTemporaryFile(dir=output_dir, delete=False)`
   or a `.partial` suffix), then `Path.replace()` into place — an interrupted run must never leave a
   half-written `.zip` that looks valid.
4. `zipfile.ZipFile(..., mode="w", compression=zipfile.ZIP_DEFLATED)`. Heart-rate samples compress
   extremely well; deflate is worth it.
5. On any exception, unlink the temp file before re-raising.

Serialisation helpers (`_serialize_night`, `_serialize_manifest`, `_render_readme`) live in this module
or a sibling `serializers.py` — keep `write()` short enough to read in one screen.

`zipfile` is synchronous. Either accept the blocking call with a comment (the archive is small and
this is a CLI, not a server) or wrap it in `asyncio.to_thread`. **Pick one and say why in a comment.**
Recommendation: `asyncio.to_thread`, since the port is `async` and pretending otherwise is misleading.

---

## Tests

- **Integration** (`tests/integration/infrastructure/adapters/archivers/test_zip.py`) — the real
  archiver writing into `tmp_path`, then re-opened with `zipfile` to assert:
  - the exact entry list with and without `include_raw`;
  - `nights.json` round-trips to the expected structure, with `null` for absent sources;
  - `manifest.json` matches the `ExportManifest`;
  - `README.md` is non-empty and mentions the 28-day caveat and every requested source;
  - **the access token string does not appear anywhere in the archive** — read every entry and assert.
- **Unit** — error branches: existing archive without `force` → `ArchiveAlreadyExistsError`; existing
  archive with `force` → overwritten; `output_dir` that does not exist → created; a serialisation
  failure mid-write → temp file cleaned up and no `.zip` left behind (inject the failure with a
  fixture-based patch, never an inline `mock.patch`).
- Build inputs from the phase-3 polyfactory factories.

---

## Acceptance criteria

```bash
make lint
make test    # green at 100 % branch coverage
```

Plus a manual eyeball: generate an archive in a scratch dir from factory data, unzip it, and **read
`README.md` as if you were the receiving AI**. If a field's unit or scale is ambiguous, the README is
not done.
