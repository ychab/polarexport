# Phase 6 — Local data store

**Depends on:** phase 4 (independent of phases 5 and 7). **Needs a Polar token:** no.

## Goal

Implement `NightStorePort` as a filesystem store under `data/`. This is what defeats the 28-day API
window: every payload ever fetched stays on disk, so local history grows without bound while Polar's
window never moves.

## Reference

```
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/adapters/database/repositories/track.py
```
Same role in the architecture (a port implementation that persists and retrieves), different medium —
crib the method shapes and error handling, not the SQLAlchemy.

---

## On-disk layout

```
data/
└── polar-accesslink-v3/
    ├── sleep/2026/08/2026-08-15.json
    ├── nightly-recharge/2026/08/2026-08-15.json
    ├── skin-temperature/2026/08/2026-08-15.json
    ├── sleepwise/2026/08/2026-08-15.json
    └── continuous-heart-rate/2026/08/2026-08-15.json
```

- Top level is the **API identity** (`endpoints.API_NAME`), so a future v4 store sits alongside
  without collision or migration.
- Then the `NightSource` enum value — the same vocabulary as the `--source` flag and the archive's
  `raw/` directories. One vocabulary, three places.
- Then `YYYY/MM/` partitioning. A year of five sources is ~1800 files; without partitioning a single
  directory would hold hundreds of entries and `ls` becomes useless. Month directories keep it
  browsable by hand, which matters for a store the user is expected to trust and inspect.
- One night per file, named `YYYY-MM-DD.json` — the date is the **night's date as Polar reports it**,
  not the fetch date.

## File format

```json
{
  "schema_version": 1,
  "api": "polar-accesslink-v3",
  "source": "sleep",
  "date": "2026-08-15",
  "fetched_at": "2026-08-17T09:12:44+00:00",
  "payload": { "...": "untouched Polar response" }
}
```

- `payload: null` means **Polar was asked and had nothing**. This is a real, useful record — it is what
  stops a dead night being re-requested on every run.
- The envelope is provenance. `fetched_at` tells you how fresh a night is; `api` tells the export path
  which mapper applies; `schema_version` gives us a migration hook we will probably never need but
  cost nothing now.
- `indent=2`, `ensure_ascii=False`. These files are meant to be readable — the user should be able to
  `cat` one and understand it.

**The access token must never appear in a stored file.**

---

## `polarexport/infrastructure/adapters/stores/filesystem.py`

```python
class FilesystemNightStore(NightStorePort):
    def __init__(self, data_dir: Path, api: str = API_NAME) -> None: ...

    async def write(self, stored: StoredPayload) -> None: ...
    async def read(self, source: NightSource, date_range: DateRange) -> Mapping[date, StoredPayload]: ...
    async def missing(self, source: NightSource, dates: Sequence[date], *, today: date) -> tuple[date, ...]: ...
```

### `write`
- `mkdir(parents=True, exist_ok=True)` on the month directory.
- **Atomic**: write to a temp file in the same directory, then `Path.replace()`. A killed run must
  never leave a truncated JSON file that later parses as garbage — the store is the durable asset here,
  and a corrupt night is worse than a missing one.
- Overwrites unconditionally; the caller decides whether to re-fetch.

### `read`
- Iterate the dates in the range, read the ones present, skip the ones absent.
- A file that fails to parse → log a **warning** with the path and skip it. One bad file must not sink
  an export. Do not delete it; the user may want to inspect it.

### `missing`
```python
stored = self._read_index(source, dates)
return tuple(
    day for day in dates
    if day not in stored
    or (stored[day].payload is None and not is_outside_history_window(day, today=today))
)
```
The second clause is the subtle one: a night stored as empty is retried **only while it is still
inside Polar's 28-day window**, because a watch may sync days late. Once the date falls outside the
window, Polar will never have it and the empty verdict is final. Both branches need a test.

Implement this by stat-ing/reading only the candidate paths — never walk the whole `data/` tree.

### Blocking I/O
`pathlib` is synchronous while the port is `async`. Wrap the file work in `asyncio.to_thread` rather
than pretending — and say so in a comment.

---

## Tests

**Integration** (`tests/integration/infrastructure/adapters/stores/test_filesystem.py`) — the real
store against `tmp_path`:
- `write` then `read` round-trips a payload, including the `None` payload case;
- the directory layout is exactly `<api>/<source>/<YYYY>/<MM>/<YYYY-MM-DD>.json` — assert the literal
  path;
- `write` twice overwrites cleanly;
- `read` over a range with holes returns only the present dates;
- a corrupt file → warning via `caplog`, other dates still returned;
- the access token string appears in no file under `data/`.

**Unit** — `missing()` truth table, which is the logic worth being careful about:

| stored? | payload | inside window | expected |
|---|---|---|---|
| no | — | yes | missing |
| no | — | no | missing |
| yes | present | yes | not missing |
| yes | present | no | not missing |
| yes | `None` | yes | **missing** (retry — device may sync late) |
| yes | `None` | no | **not missing** (final) |

Plus: atomic-write cleanup when serialisation fails mid-write (inject via a fixture-based patch, never
an inline `mock.patch`), and `mkdir` on a fresh `data_dir`.

Build inputs from the phase-3 polyfactory factories.

---

## Acceptance criteria

```bash
make lint
make test    # green at 100 % branch coverage
```

Plus a manual check: write a few nights into a scratch `data_dir`, then `tree` it and `cat` one file.
The layout should be obvious without documentation, and the file should be readable as-is.
