# Phase 12 — First-run bootstrap: the CLI must start without credentials

**Depends on:** phases 1–11 (all complete). **Needs a Polar token:** no.
**Blocks:** phase 13 (`polarexport auth`) — do this one first.

## Goal

Right now polarexport cannot run at all until `.env` already contains a valid token. That is fatal
for phase 13: the command whose entire job is to *create* the credentials cannot start, because
importing the CLI requires them to already exist.

Reproduce on a clean checkout (no `.env`, no `POLAR_*` exported):

```bash
git clone <repo> /tmp/fresh && cd /tmp/fresh
uv run polarexport --version
```

Observed on 2026-08-18:

```
Traceback (most recent call last):
  File ".../cli/main.py", line 8, in <module>
    from polarexport.infrastructure.entrypoints.cli.commands import night
  File ".../cli/commands/night.py", line 30, in <module>
    from polarexport.infrastructure.config.settings.polar import polar_settings
  File ".../config/settings/polar.py", line 38, in <module>
    polar_settings = PolarSettings()
pydantic_core._pydantic_core.ValidationError: 2 validation errors for PolarSettings
ACCESS_TOKEN
  Field required [type=missing, input_value={}, input_type=dict]
USER_ID
  Field required [type=missing, input_value={}, input_type=dict]
```

`--version`, `--help` and every future command are equally dead. A first-time user's first
interaction with the tool is a pydantic stack trace naming internal module paths.

## Cause

`polarexport/infrastructure/config/settings/polar.py`:

```python
ACCESS_TOKEN: str = Field(..., min_length=1)
USER_ID: str = Field(..., min_length=1)
...
polar_settings = PolarSettings()   # module-level singleton, evaluated at import
```

The two fields are required, the singleton is built at import time, and `cli/main.py` imports
`commands/night.py`, which imports the singleton. So the requirement is enforced at *import* time
for *every* invocation, rather than at the point where a token is actually needed — which is only
inside `get_polar_client()`.

This is a layering issue as much as a UX one: needing a Polar token to print a version number is
the settings module reaching further than its job.

## Fix

Move enforcement from import time to use time.

1. **`config/settings/polar.py`** — make the pair optional:
   ```python
   ACCESS_TOKEN: str | None = None  # None until `polarexport auth` has run
   USER_ID: str | None = None
   ```
   Keep `min_length=1` semantics by rejecting empty strings in a validator, so `POLAR_ACCESS_TOKEN=`
   is treated as absent rather than as a valid empty token.

2. **`domain/exceptions.py`** — add `MissingCredentialsError(PolarExportError)`.

3. **`cli/dependencies.py`** — `get_polar_client()` raises `MissingCredentialsError` when either
   value is `None`, before constructing the client. This is the single place that needs them.

4. **`cli/commands/night.py`** — catch `MissingCredentialsError` in the `night()` callback and print
   an actionable message, red, on stderr, exit code 1:
   ```
   No Polar credentials found. Run `polarexport auth` to set them up, or see docs/authentication.md
   to do it by hand.
   ```
   Until phase 13 lands, word it pointing at `docs/authentication.md` only; phase 13 updates it.

5. **`client.py`** — `PolarAccessLinkClient` takes `access_token: str` / `user_id: str` (still
   non-optional). The `None` check belongs in the dependency factory, not the adapter.

### Also worth fixing while here

`client.py` reads `polar_settings.HTTP_MAX_RETRIES` inside the `@retry(...)` decorator, which is
evaluated once at class-definition time. The setting is therefore un-overridable per instance and
frozen at import. Pass the retry count through the constructor, or read it inside a
`stop=` callable. Do not leave a settings read in a decorator argument.

## Files touched

```
polarexport/infrastructure/config/settings/polar.py
polarexport/domain/exceptions.py
polarexport/infrastructure/entrypoints/cli/dependencies.py
polarexport/infrastructure/entrypoints/cli/commands/night.py
polarexport/infrastructure/adapters/providers/polar/client.py
tests/unit/infrastructure/config/settings/test_polar.py
tests/unit/infrastructure/entrypoints/cli/test_dependencies.py
tests/unit/infrastructure/entrypoints/cli/commands/test_night.py
```

Note `tests/unit/infrastructure/config/settings/conftest.py` already strips every `POLAR_*` /
`POLAREXPORT_*` variable from the environment for settings tests — the existing
`test__access_token_required` / `test__user_id_required` tests assert the *old* required behaviour
and must be rewritten, not deleted: they become "absent credentials produce `None`, not a crash".

## Tests

- Unit, settings: with no `POLAR_ACCESS_TOKEN` / `POLAR_USER_ID` in the environment and
  `_env_file=None`, `PolarSettings()` constructs successfully and both fields are `None`.
- Unit, settings: `POLAR_ACCESS_TOKEN=""` is treated as absent (`None`), not as a valid token.
- Unit, dependencies: `get_polar_client()` raises `MissingCredentialsError` when either value is
  `None` — one test per field, so both branches are covered.
- Unit, CLI: `night` with credentials absent exits 1 with the actionable message on stderr and no
  traceback.
- **Regression test for the actual bug:** importing `polarexport.infrastructure.entrypoints.cli.main`
  with the environment stripped must not raise. Put it in `tests/unit/infrastructure/entrypoints/cli/test_main.py`
  using `importlib.reload` inside a fixture (never `mock.patch` inline, per `CLAUDE.md`).

## Acceptance criteria

- [ ] `uv run polarexport --version` and `--help` succeed on a checkout with no `.env` and no
      `POLAR_*` variables exported. Verify with a real `git clone` to a temp dir, not just by
      unsetting variables in the current shell — the real `.env` is read via `BASE_DIR` and will mask
      the bug otherwise.
- [ ] `polarexport night` without credentials prints one actionable line, exits 1, shows no traceback.
- [ ] No settings value is read at decorator-evaluation or import time outside the settings module.
- [ ] `make lint` clean, `make test` green at 100% branch coverage.
