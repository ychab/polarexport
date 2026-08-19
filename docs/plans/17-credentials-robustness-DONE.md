# Phase 17 — Credentials robustness & stale messages

> Depends on: phases 15–16 (complete). Needs a Polar token: **no** — every item is reachable with a
> hand-written credentials file and the local store.

## Where this came from

The 2026-08-19 review of phases 15 and 16. Both phases are green — `make lint` clean, `make test` at
376 passed / 100 % branch coverage, and all four phase-16 fidelity fixes verified against the real
store (`celsius: 33.828125`, 97 sleep heart-rate samples, 91 HRV + 98 breathing samples, SleepWise
`grade: 7.4` with inertia and circadian quality). The token does not appear in any archive member.
A fresh clone with no `.env` and no `data/` still prints `--version` and fails `night` cleanly.

What follows are four defects found *around* that work, not in it. Item 1 is a genuine crash; the
rest are correctness-of-message issues.

---

## 1. A malformed credentials file crashes with a traceback

`JsonCredentialsStore._read_sync` catches `json.JSONDecodeError` and returns `None`, but then indexes
the envelope directly. Valid JSON with the wrong shape — a hand-edited file, a truncated write from
another tool, or a future `schema_version: 2` — escapes as a bare `KeyError`:

```
$ echo '{"schema_version": 2, "user": "x"}' > data/auth/credentials.json
$ polarexport night --limit 1
...
KeyError: 'user_id'
```

This violates the port's own contract. `CredentialsStorePort.read` documents:

> Returns: The stored credentials, or `None` if `path` doesn't exist **or can't be parsed**.

It is also the exact regression class phase 12 existed to remove: an unhandled traceback where a
sentence belongs.

Reproduced for all three shapes:

| File contents | Current | Wanted |
|---|---|---|
| `not json at all` | `None` + warning ✅ | unchanged |
| `{"schema_version": 2, "user": "x"}` | `KeyError: 'user_id'` | `None` + warning |
| envelope missing `expires_in` | `KeyError: 'expires_in'` | `None` + warning |
| `obtained_at: "not-a-date"` | `ValueError: Invalid isoformat string` | `None` + warning |

**Fix.** Widen the `except` in `_read_sync` to `(json.JSONDecodeError, KeyError, ValueError, TypeError)`
around *both* the parse and the `StoredCredentials` construction, keeping the existing
`logger.warning("Failed to parse stored credentials, skipping", extra={"path": str(path)})`. Returning
`None` makes `_resolve_credentials` fall through to `MissingCredentialsError`, which the `night`
callback already turns into "Run `polarexport auth` to set them up" — the right advice for a file that
can't be read.

Also **validate `schema_version`**: it is written but never checked on read. If it is not `1`, log a
warning naming the version found and return `None` rather than guessing at the shape. Reuse the
`_SCHEMA_VERSION` constant.

Do **not** log the file's contents in the warning — it holds a bearer token. The path is enough.

## 2. `expires_in` is stored but never consulted

Phase 15 fixed half of what it set out to fix. `expires_in` and `obtained_at` now survive the round
trip — `auth` writes them, `JsonCredentialsStore.read` parses them back into `StoredCredentials` — but
`grep -rn "expires_in" polarexport/` shows nothing reads them. A user whose token has expired gets
Polar's raw 401.

**Fix.** Add a read-only property to `StoredCredentials` (domain entity, pure Python, no clock inside):

```python
def is_expired(self, *, now: datetime) -> bool:
    return now >= self.obtained_at + timedelta(seconds=self.expires_in)
```

Pass `now` in — the entity must not call `datetime.now()` itself, matching how `NightExportUseCase.export`
takes `generated_at` and `AuthLoginUseCase.login` takes `obtained_at`.

In `_resolve_credentials` (`cli/dependencies.py`), when the stored credentials are expired, log a
warning and **still return them**. Do not refuse to proceed: Polar's `expires_in` is on the order of a
year, the clock may be wrong, and a token that still works must keep working. The value of the check is
the message on failure, not gatekeeping.

Then make item 3's 401 message say so.

## 3. The 401 message still points at `.env`

`cli/commands/night.py:164`, unchanged since before phase 15:

```
Authentication failed (401 Unauthorized). Check POLAR_ACCESS_TOKEN in .env — see docs/authentication.md.
```

After phase 15 the normal place for a token is `data/auth/credentials.json`; `.env` is the manual
override. The message sends the user to the wrong file in the common case.

**Fix.** Rewrite it to name the file the token actually came from and the command that fixes it. With
item 2 in place, the handler can distinguish the two cases:

- token was stored and is past its expiry → "Your Polar token expired on `<date>`. Run `polarexport auth`
  to authorize again."
- otherwise → "Authentication failed (401 Unauthorized). Run `polarexport auth` to authorize again, or
  check `POLAR_ACCESS_TOKEN` in `.env` if you set it by hand — see `docs/authentication.md`."

Threading the resolved-credential provenance from `_resolve_credentials` out to the callback is the
fiddly part. The simplest shape that respects the layering: have `_resolve_credentials` log the
provenance (it already does, at DEBUG) and have the callback re-read the credentials file to decide
which sentence to print. Do not widen `night_logic`'s return type to carry it — `*_logic` returns the
reports and nothing else.

While in this handler, check the two neighbours for the same staleness. `ProviderRateLimitError` and
`httpx.RequestError` both say "Nights already fetched are saved in `data/`" — still true after phase 15,
but `data/raw/` is now more precise. Update both.

Also update the comment on `domain/exceptions.py:16`, which still reads
`# POLAR_ACCESS_TOKEN or POLAR_USER_ID not set`. It now means "neither the settings nor the credentials
file yielded a token".

## 4. `NoNightDataError` leaks a dataclass repr into the CLI

```
No night data found for DateRange(date_min=datetime.date(2026, 7, 23), date_max=datetime.date(2026, 8, 19))
```

`night_export.py:68` interpolates the `DateRange` value object, which has no `__str__`, so Python falls
back to the dataclass repr.

**Fix.** Add `__str__` to `DateRange` returning `f"{self.date_min.isoformat()} to {self.date_max.isoformat()}"`.
Do not touch `__repr__` — debugging and test failure output benefit from the full form. Grep for other
f-string interpolations of `DateRange` and of `date` objects in user-facing messages while you are
there; use `.isoformat()` explicitly wherever the result reaches `typer.secho`.

---

## Also: `docs/runbook.md` is stale

It is the pre-phase-1 bootstrap script — it tells the reader to `cp` museflow's settings, to pick
Sonnet 5, and to open `docs/plans/01-scaffolding.md`, which is now `01-scaffolding-DONE.md`. Step 2
step 5 says "Append POLAR_ACCESS_TOKEN and POLAR_USER_ID to .env", which phases 13 and 15 replaced with
`polarexport auth`.

It is a historical artifact of the build, not user documentation, and nothing links to it from
`README.md`. **Delete it**, or move it to `docs/plans/00-runbook-historical.md` with a one-line header
saying it describes the original build sequence and is kept for provenance only. Prefer deleting —
git history keeps it. Do not attempt to "update" it into current documentation; `README.md` and
`docs/authentication.md` already cover everything it would say.

---

## Files

| File | Change |
|---|---|
| `polarexport/infrastructure/adapters/stores/json_credentials.py` | widen `except` in `_read_sync`; validate `schema_version` |
| `polarexport/domain/entities/credentials.py` | add `is_expired(*, now)` |
| `polarexport/infrastructure/entrypoints/cli/dependencies.py` | warn on expired credentials in `_resolve_credentials` |
| `polarexport/infrastructure/entrypoints/cli/commands/night.py` | rewrite the 401 message; `data/` → `data/raw/` in two neighbours |
| `polarexport/domain/value_objects/date_range.py` | add `__str__` |
| `polarexport/domain/exceptions.py` | update the `MissingCredentialsError` comment |
| `docs/runbook.md` | delete |

## Tests

- `tests/unit/infrastructure/adapters/stores/test_json_credentials.py` — parametrized over the four
  malformed shapes in item 1's table, each asserting `read()` returns `None` and logs a warning; one
  asserting the warning text never contains the token value. One for `schema_version: 2`.
- `tests/unit/domain/entities/test_credentials.py` — `is_expired` at, before and after the boundary.
- `tests/unit/infrastructure/entrypoints/cli/commands/test_night.py` — the expired-token 401 message
  and the not-expired one, as separate cases.
- `tests/unit/domain/value_objects/test_date_range.py` — `__str__` renders both dates ISO, `__repr__`
  still carries the field names.
- Integration: a malformed `data/auth/credentials.json` on `tmp_path` makes `night` exit 1 with the
  "No Polar credentials found" sentence and **no traceback** — assert on the absence of `KeyError` in
  the captured output. This is the regression test for item 1 and the reason this phase exists.

## Acceptance criteria

- `make lint` clean, `make test` green at 100 % branch coverage.
- Every file in item 1's table returns `None` from `read()` instead of raising.
- `polarexport night` against a malformed credentials file prints one sentence and exits 1.
- `grep -rn "POLAR_ACCESS_TOKEN in .env" polarexport/` returns nothing.
- `grep -rn "DateRange(date_min=" ` over a captured CLI session returns nothing.
- `docs/runbook.md` is gone and nothing references it.
