# Phase 15 — Credentials belong in the store, not in `.env`

**Depends on:** phases 12–14 (complete). **Needs a Polar token:** at the end, to re-run `auth` once.
**Size:** medium. Do this before phase 16 — it moves files that phase 16 does not touch, and doing
them in the other order means resolving a pointless conflict in `settings/app.py`.

## Goal

`polarexport auth` currently writes `POLAR_ACCESS_TOKEN` and `POLAR_USER_ID` into `.env`. That is the
wrong file for them.

`.env` is **configuration the user authors**: `POLAR_CLIENT_ID`, `POLAR_CLIENT_SECRET`,
`POLAR_REDIRECT_URI`, log levels. It is hand-edited, copied from `.env.example`, and read by
pydantic-settings. `POLAR_ACCESS_TOKEN` and `POLAR_USER_ID` are neither authored nor configuration —
they are **state the tool produces**, with a lifetime, that a command overwrites. Storing them in
`.env` is what forced `DotenvCredentialsStore` to grow line-preserving surgery and a `--force` guard
just to avoid clobbering lines the user wrote by hand. Move them to their own file and the store
becomes a plain atomic overwrite.

It also costs real information today: `PolarOAuthClient.exchange_code()` already parses `expires_in`
into `OAuthTokens`, and `DotenvCredentialsStore.write()` accepts only `access_token` and `user_id`,
so **the expiry is thrown away on every authorization**. A JSON file can hold it.

Same reasoning as museflow, which keeps Spotify tokens in `repositories/auth.py` (a store) and only
client credentials in `.env`. polarexport has no database, so the store is a file.

## Decisions already made — do not re-litigate

The user chose both of these explicitly on 2026-08-19.

1. **Credentials live inside the data root**, at `data/auth/credentials.json`.
2. **Single data root.** `data/` becomes the one place: `raw/`, `export/`, `auth/`.

## Target layout

```
polarexport/
├── .env                       # POLAR_CLIENT_ID / POLAR_CLIENT_SECRET / POLAR_REDIRECT_URI, log config
└── data/                      # POLAREXPORT_DATA_DIR — gitignored in full
    ├── raw/
    │   └── polar-accesslink-v3/
    │       └── sleep/
    │           ├── _status.json
    │           └── 2026/08/2026-08-15.json
    ├── export/
    │   └── polarexport-nights-2026-07-22_2026-08-18.zip
    └── auth/
        └── credentials.json   # 0600
```

### `credentials.json`

```json
{
  "schema_version": 1,
  "api": "polar-accesslink-v3",
  "user_id": "60233839",
  "access_token": "…",
  "obtained_at": "2026-08-18T16:42:05.123456+00:00",
  "expires_in": 473040000
}
```

`obtained_at` + `expires_in` are new — they exist so a later phase can warn "your Polar token expires
in N days". **Do not build that warning in this phase**; just persist the two values honestly. `api`
mirrors `StoredPayload.api` so a future v4 grant is distinguishable.

## ⚠️ This puts a bearer token inside `data/`

CLAUDE.md currently reads:

> Never log the access token, never put it in an exception message, and never write it into
> `data/`, an archive, or a manifest.

The chosen layout contradicts the `data/` clause. **Amend the rule rather than quietly violating
it.** New wording:

> Never log the access token, never put it in an exception message, and never write it into
> `data/raw/`, an archive, or a manifest. The one file that may hold it is
> `data/auth/credentials.json`, mode 0600.

The compensating controls are not optional, because `data/` is the directory whose entire purpose is
to be accumulated, backed up, and eventually handed to someone:

- `data/auth/` is created mode **0700**, `credentials.json` mode **0600**, set on the temp file
  descriptor before any bytes are written — never widened afterwards.
- `ZipNightArchiver` must keep writing **only what it is handed**. It must never glob or walk the
  data root. Verify this is still true; it is today.
- A regression test (see below) asserts a real end-to-end export produces an archive whose bytes
  never contain the token, with a credentials file present on disk.

## Settings

In `config/settings/app.py`:

```python
DATA_DIR: Path = BASE_DIR / "data"              # the single root
EXPORT_DIR: Path | None = None                  # override; defaults to DATA_DIR / "export"
```

Add read-only properties `RAW_DIR`, `AUTH_DIR`, and `RESOLVED_EXPORT_DIR` (or resolve in
`cli/dependencies.py` — either is fine, pick one and be consistent). `POLAREXPORT_EXPORT_DIR` stays
overridable because `--output-dir` and CI both rely on pointing archives elsewhere; it simply gains a
derived default instead of a hardcoded `BASE_DIR / "export"`.

`PolarSettings.ACCESS_TOKEN` / `USER_ID` stay as they are — optional, `None` by default. They remain
the **override**, not the primary source (see below).

## Credential resolution order

pydantic-settings cannot read a JSON file, and teaching it to would drag file I/O into a settings
singleton evaluated at import time — exactly the crash phase 12 fixed. So resolution lives in
`cli/dependencies.get_polar_client()`:

1. `polar_settings.ACCESS_TOKEN` / `USER_ID` if set (environment or `.env`) — **wins**.
2. Otherwise `CredentialsStorePort.read()`.
3. Otherwise `MissingCredentialsError`, whose message already points at `polarexport auth`.

Order matters: the environment must win so CI, `POLAR_ACCESS_TOKEN=… polarexport night`, and the
hand-rolled flow in `docs/authentication.md` all keep working unchanged. Log at DEBUG which source
won — **the source, never the value**.

## Files

**New**

- `polarexport/domain/entities/credentials.py` — `StoredCredentials` frozen dataclass
  (`user_id`, `access_token`, `api`, `obtained_at`, `expires_in`). Give it the same masking
  `__repr__` as `OAuthTokens`, for the same reason.
- `polarexport/infrastructure/adapters/stores/json_credentials.py` — `JsonCredentialsStore`.
- `tests/unit/infrastructure/adapters/stores/test_json_credentials.py`
- `tests/integration/infrastructure/adapters/stores/test_json_credentials.py`

**Changed**

- `polarexport/application/ports/stores/credentials.py` — `write()` gains `obtained_at` and
  `expires_in`; `env_path` becomes `path`; add `read() -> StoredCredentials | None`.
- `polarexport/application/inputs/auth.py` — `env_file` → `credentials_file`.
- `polarexport/domain/entities/auth.py` — `AuthReport.env_path` → `credentials_path`.
- `polarexport/application/use_cases/auth_login.py` — pass `expires_in` and an `obtained_at` through
  to the store. `obtained_at` is a clock read: take it as a keyword arg on `login()` the way
  `NightExportUseCase.export()` takes `generated_at`. Use cases do not call `datetime.now()`.
- `polarexport/infrastructure/config/settings/app.py` — as above.
- `polarexport/infrastructure/adapters/stores/filesystem.py` — root is now `raw/`.
- `polarexport/infrastructure/entrypoints/cli/dependencies.py` — resolution order, `get_night_store`
  points at `RAW_DIR`, `get_credentials_store` returns the JSON store, plus the legacy-layout check.
- `polarexport/infrastructure/entrypoints/cli/commands/auth.py` — `--env-file` → `--credentials-file`
  (a rename, not an alias: nothing is released). Success output prints the credentials path.
- `polarexport/infrastructure/entrypoints/cli/commands/night.py` — default `--output-dir`.

**Deleted**

- `polarexport/infrastructure/adapters/stores/dotenv.py` and both of its test files. Do not keep it
  "just in case" — the manual path in `docs/authentication.md` is a `.env` edit by hand, which needs
  no adapter.

## Migration

The store currently holds ~28 days across five sources, all of it still inside Polar's retention
window, so a re-sync would rebuild it. That will not be true in a month, and silently orphaning a
year of accumulated nights is exactly the failure this store exists to prevent.

Do **not** auto-move files. In `get_night_store()`, if `DATA_DIR / <api>` exists as a directory (the
old layout), emit one warning naming the exact commands:

```
data/polar-accesslink-v3/ is the pre-0.2 layout. Move it with:
  mkdir -p data/raw && mv data/polar-accesslink-v3 data/raw/
  mkdir -p data/export && mv export/*.zip data/export/
```

One branch, one test, no filesystem surgery on the user's behalf.

## Tests

- `JsonCredentialsStore`: round-trip; `read()` on a missing file returns `None`; `read()` on corrupt
  JSON logs a warning and returns `None` (mirror `FilesystemNightStore._read_availability_sync`);
  refuses to overwrite without `force`; overwrites with `force`; the written file is mode `0o600` and
  its parent `0o700`; a failed write leaves no `.tmp` behind.
- `get_polar_client()` resolution: settings-win, file-win, neither → `MissingCredentialsError`. Unit,
  with an `AsyncMock` store.
- Legacy-layout warning fires exactly once for the old tree and not for the new one.
- **Security (non-negotiable).** Extend the existing
  `test__access_token_never_appears_in_stored_files` into an end-to-end integration test: write a
  credentials file containing a known dummy token under `tmp_path / "data" / "auth"`, run a real
  export into `tmp_path`, then assert the dummy token appears in **no** archive member's bytes and in
  no `caplog.text`. Read the zip back with `zipfile`, do not trust the file list.
- Update every existing test that references `.env` writing, `env_file`, or `env_path`.

## Acceptance criteria

- `make lint` clean, `make test` green at 100 % branch coverage.
- `polarexport auth --help` shows `--credentials-file`; no `--env-file` remains anywhere.
- On a fresh clone with no `.env` and no `data/`: `polarexport --version` and `--help` still work
  (phase 12's guarantee), and `polarexport night` still names `polarexport auth` in its error.
- After a real `polarexport auth`: `data/auth/credentials.json` exists, is `-rw-------`, contains
  `obtained_at` and `expires_in`, and **`.env` is byte-identical to what it was before the run**.
- `polarexport night` works with the token only in `credentials.json` and `POLAR_ACCESS_TOKEN` unset.
- `POLAR_ACCESS_TOKEN=… polarexport night` still overrides the file.
- `grep -r POLAR_ACCESS_TOKEN data/raw export` finds nothing.

## Docs to update

- `CLAUDE.md` — the token rule quoted above, and the "Local store" section's layout line.
- `README.md` — Configuration and Getting Started; `.env` no longer receives the token.
- `.env.example` — drop `POLAR_ACCESS_TOKEN` / `POLAR_USER_ID` from the authored section, or keep
  them commented as the documented manual override with a line saying `polarexport auth` writes
  `data/auth/credentials.json` instead.
- `docs/authentication.md` — step 5 ("write `.env`") becomes the manual override, not the norm.
- `docs/plans/00-overview.md` — the locked-decisions table still says persistence is "None"; it now
  has a defined on-disk contract.
