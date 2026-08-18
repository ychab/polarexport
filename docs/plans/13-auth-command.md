# Phase 13 — `polarexport auth`: one command instead of six manual steps

**Depends on:** phase 12 (**hard prerequisite** — the CLI cannot currently start without the very
credentials this command creates). **Needs a Polar token:** no for the build; yes for the final
manual end-to-end check.

## Goal

Replace the six hand-run steps in `docs/authentication.md` (build an authorization URL by hand, run
`python3 -m http.server` to catch the redirect, copy a code out of a log line, `curl` a token
exchange, `curl` a user registration, hand-append to `.env`) with:

```bash
polarexport auth
```

which opens the browser, catches the callback itself, exchanges the code, registers the account, and
writes `.env`. `docs/authentication.md` stays, demoted to the manual fallback and troubleshooting
reference.

## ⚠️ Naming: there is no `--email` in this flow

The request was for something like `polarexport auth --email`. Polar's OAuth flow has no email
parameter anywhere — identity is established by logging into flow.polar.com in the browser, not by
anything the CLI sends. The only free-text identifier in the flow is `member-id`, in the
`POST /v3/users` registration body: an arbitrary stable string you choose to identify yourself
*within your own registered application*.

So the option is **`--member-id`**, and an email address is a perfectly good value for it:

```bash
polarexport auth --member-id yannick@example.com
```

Do not add an `--email` alias. It would imply Polar does something with the address, and it does not.

## The flow to implement

Endpoints (all confirmed against `docs/authentication.md`, which was validated by hand):

| Step | Request |
|---|---|
| 1 | Browser → `GET https://flow.polar.com/oauth2/authorization?response_type=code&client_id=…&redirect_uri=…&scope=accesslink.read_all&state=…` |
| 2 | Polar → `GET {redirect_uri}?code=…&state=…` (caught by a local one-shot HTTP listener) |
| 3 | `POST https://polarremote.com/v2/oauth2/token`, HTTP Basic `client_id:client_secret`, form `grant_type=authorization_code&code=…&redirect_uri=…` → `{access_token, token_type, expires_in, x_user_id}` |
| 4 | `POST https://www.polaraccesslink.com/v3/users`, `Authorization: Bearer …`, JSON `{"member-id": "…"}` → `200` registered / `409` already registered (both success) / `403` consent missing |
| 5 | Write `POLAR_ACCESS_TOKEN` + `POLAR_USER_ID` into `.env` |

`x_user_id` **is** `POLAR_USER_ID`.

### Non-negotiable details

- **Send and verify `state`.** `secrets.token_urlsafe(32)`, compared against the callback's `state`
  before the code is used. A mismatch aborts with a clear error. It is the only defence the local
  listener has against a stray request landing on that port.
- **The authorization code is single-use and expires in 10 minutes.** Failures must say so.
- **`409` from step 4 is success**, not an error. It means "already registered".
- **Never log, echo, `repr()` or write to a report the access token.** This is the standing project
  rule and this command is the one place the token is in memory. The success output prints the user
  id and the `.env` path — never the token, not even truncated.

## Architecture

Layering is not optional here; the command is doing network I/O, socket listening and file writing,
and each belongs behind its own port.

```
application/inputs/auth.py                          AuthLoginInput (Pydantic)
application/ports/providers/auth.py                 AuthProviderPort (ABC)
application/ports/receivers/callback.py             AuthCallbackReceiverPort (ABC)
application/ports/stores/credentials.py             CredentialsStorePort (ABC)
application/use_cases/auth_login.py                 AuthLoginUseCase
domain/entities/auth.py                             OAuthTokens, AuthReport
domain/exceptions.py                                + four new exceptions
infrastructure/adapters/providers/polar/auth.py     PolarOAuthClient(HttpClientMixin, AuthProviderPort)
infrastructure/adapters/receivers/local_http.py     LocalHttpCallbackReceiver
infrastructure/adapters/stores/dotenv.py            DotenvCredentialsStore
infrastructure/entrypoints/cli/commands/auth.py     the command
```

### Ports

```python
class AuthProviderPort(ABC):
    @abstractmethod
    def authorization_url(self, *, redirect_uri: str, state: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, code: str, *, redirect_uri: str) -> OAuthTokens: ...

    @abstractmethod
    async def register_user(self, *, access_token: str, member_id: str) -> bool:
        """Returns True if newly registered, False if already registered (409)."""


class AuthCallbackReceiverPort(ABC):
    @abstractmethod
    async def wait_for_code(self, *, expected_state: str, timeout: float) -> str: ...
```

`authorization_url` is deliberately sync — it builds a string, it does not perform I/O.

### `OAuthTokens` must redact itself

```python
@dataclass(frozen=True, kw_only=True)
class OAuthTokens:
    access_token: str
    user_id: str
    expires_in: int

    def __repr__(self) -> str:
        return f"OAuthTokens(user_id={self.user_id!r}, access_token='***', expires_in={self.expires_in})"
```

Without this, one `logger.debug(f"{tokens}")` or one pytest assertion failure dumps the real token
into a log or CI output. Write a unit test asserting `"***" in repr(tokens)` and that the real token
value is absent from it.

### `LocalHttpCallbackReceiver`

- Binds to the host/port parsed from `redirect_uri`. Serves exactly one request, then closes.
- Use `asyncio.start_server` and parse the request line directly, or `http.server` in
  `asyncio.to_thread`. Prefer the asyncio version — no thread to join, and the timeout is a plain
  `asyncio.timeout(...)`.
- Answers the browser with a small HTML page ("Authorization complete — you can close this tab"),
  so the user does not see a connection-refused page and wonder whether it worked.
- On timeout raises `AuthorizationTimeoutError`; on `state` mismatch `AuthorizationStateMismatchError`;
  if Polar redirects with `?error=access_denied` (user hit "Deny") raise `AuthorizationDeniedError`
  rather than sitting until the timeout.
- **Binding can fail** (port already in use — the user may still have `python3 -m http.server 8000`
  running from the old manual flow). Catch `OSError` and say which port and why.

### `DotenvCredentialsStore`

- Preserves every other line in `.env` — comments, ordering, unrelated keys. Rewrite only
  `POLAR_ACCESS_TOKEN` and `POLAR_USER_ID`, appending them if absent.
- Creates the file if missing.
- **Atomic write** (temp file in the same directory + `Path.replace()`), consistent with
  `FilesystemNightStore`.
- **`chmod 0600`** on the result. A file holding a long-lived bearer token should not be world
  readable, and the temp file must be created with those permissions rather than widened afterwards.
- Refuses to clobber an existing token unless `--force`, raising `CredentialsAlreadyExistError`.
  Overwriting a working token by accident costs a full browser round trip to recover.

### Settings

The token exchange lives on a different host from the data API, and both must be redirectable for
WireMock. Add to `PolarSettings`:

```python
OAUTH_TOKEN_URL: HttpUrl = HttpUrl("https://polarremote.com/v2/oauth2/token")
OAUTH_AUTHORIZATION_URL: HttpUrl = HttpUrl("https://flow.polar.com/oauth2/authorization")
REDIRECT_URI: HttpUrl | None = None   # already exists
```

`REDIRECT_URI` has no safe default — it must match what is registered at
admin.polaraccesslink.com character for character. If it is unset, fail with a message naming the
admin console, do not silently guess `http://localhost:8000/...`.

## CLI contract

```
polarexport auth [OPTIONS]

  --member-id      TEXT    Stable identifier for you within your app. Default: the Polar user id.
  --client-id      TEXT    Default: POLAR_CLIENT_ID.
  --client-secret  TEXT    Default: POLAR_CLIENT_SECRET. Never echoed; prompt with hide_input=True.
  --redirect-uri   TEXT    Default: POLAR_REDIRECT_URI. Must match the admin console exactly.
  --env-file       PATH    Default: BASE_DIR / ".env".
  --no-browser             Print the URL instead of launching a browser (headless / SSH).
  --timeout        FLOAT   Seconds to wait for the callback. Default 300, min 10.
  --force                  Overwrite credentials already present in the env file.
```

Option order per `CLAUDE.md`: filters → processing config → cap. There is no filter here, so:
identity (`--member-id`), then credentials, then config, then `--force`.

Register in `main.py` next to `night`:

```python
app.command(name="auth", help="Authorize polarexport against your Polar account")(auth.auth)
```

`auth_logic` returns an `AuthReport` and **prints nothing** — the callback owns every `typer.secho`,
including the "opening your browser" line. This is the rule `night` already follows.

### Output on success

```
Authorized as Polar user 12345678 ✅
Registered with your application (member-id: yannick@example.com)
Credentials written to /home/…/polarexport/.env
Next: polarexport night
```

### Error messages, all red on stderr with exit code 1

| Condition | Message must say |
|---|---|
| `POLAR_CLIENT_ID`/`SECRET` missing | where to get them (admin.polaraccesslink.com → Credentials tab) |
| `REDIRECT_URI` missing | it must be registered in the admin console first |
| port already in use | which port, and that the old `python3 -m http.server` may still be running |
| timeout | that the browser tab was never completed, and to just re-run |
| user denied consent | that consent was declined |
| `state` mismatch | that the callback did not match the request; re-run |
| `invalid_grant` from step 3 | code expired (10 min), already used, or redirect URI mismatch |
| `401` from step 3 | wrong client id/secret |
| `403` from step 4 | consents missing, review at account.polar.com |
| env file already has a token | re-run with `--force` |

That table is lifted from the Troubleshooting section already in `docs/authentication.md` — the
diagnoses are known, they just need to reach the user at the moment of failure.

## Tests

Per `CLAUDE.md`: one test file per source file, integration first, unit for error branches, all typed.

**Unit** (`AsyncMock` ports):
- `test_auth_login.py` — state mismatch, timeout, denied, `409` treated as success, `--force` gating,
  and that the returned `AuthReport` contains no token.
- `test_dotenv.py` — preserves unrelated keys and comments, appends when absent, replaces when
  present, refuses without force, resulting file mode is `0o600`, write is atomic.
- `test_auth.py` (adapter) — `invalid_grant`, `401`, `403`, malformed token response, via `pytest-httpx`.
- `test_local_http.py` — `OSError` on bind, timeout, `?error=access_denied`, state mismatch.
- `test_auth.py` (CLI) — the three classes `TestAuthParserCommand`, `TestAuthCommand`, `TestAuthLogic`.

**Integration**:
- WireMock stubs for `POST /v2/oauth2/token` and `POST /v3/users` (200 and 409). Add them under
  `tests/assets/wiremock/polar/`. Mark the class `@pytest.mark.wiremock` — mandatory, see
  `tests/CLAUDE.md`.
- Real `LocalHttpCallbackReceiver` on an ephemeral port, driven by an `httpx` GET to the callback URL
  from the test itself. Real `DotenvCredentialsStore` on `tmp_path`.
- One happy-path CLI `TestAuthLogic` with the browser launch stubbed by a fixture (never
  `mock.patch` inside the test body).

**Security test, non-negotiable:** assert the access token string appears in **neither** captured
logs nor the `AuthReport` nor `repr(tokens)`. Use a distinctive dummy such as
`"tok-must-never-be-logged"` and assert it is absent from `caplog.text`.

## Docs

- **`docs/authentication.md`** — new section at the top: "The fast path: `polarexport auth`". Keep the
  manual six steps below it under "Doing it by hand", and keep the whole Troubleshooting table.
  Remove the parenthetical "or so a future `polarexport auth login` command can automate it" — note
  that the shipped command is `polarexport auth`, not `auth login`.
- **`README.md`** — Getting Started becomes `polarexport auth` then `polarexport night`. The
  Configuration section must state that `POLAR_CLIENT_ID` / `POLAR_CLIENT_SECRET` /
  `POLAR_REDIRECT_URI` are now *inputs to `auth`*, not merely stored for reference.
- **`.env.example`** — comment the two token fields as "written by `polarexport auth`".
- **`CLAUDE.md`** — the "Scope" section currently reads "exactly one command, `night`". That stops
  being true. Update it to name both commands and restate that sport sessions remain out of scope.
- **`docs/plans/00-overview.md`** — the "Locked decisions" table says "No OAuth code in this build".
  Amend that row rather than leaving a contradiction in the project's own overview.

## Acceptance criteria

- [ ] On a checkout with no `.env`, `polarexport auth` runs, opens the browser, and completes without
      any manual `curl`.
- [ ] `.env` afterwards contains a working `POLAR_ACCESS_TOKEN` / `POLAR_USER_ID`, has mode `0600`,
      and every pre-existing line is intact.
- [ ] `polarexport night` works immediately afterwards with no further setup.
- [ ] Re-running `auth` without `--force` refuses; with `--force` it replaces the token.
- [ ] `--no-browser` prints a URL that works when pasted into a browser on another machine.
- [ ] The access token appears in no log line, no terminal output, and no test output at any log level.
- [ ] `make lint` clean, `make test` green at 100% branch coverage.

## Manual end-to-end check (needs the real account)

Do this last, and note in `docs/summary.md` that it was done:

```bash
mv .env .env.backup                       # keep the working token safe
uv run polarexport auth --member-id yannick@example.com
diff <(sort .env) <(sort .env.backup)     # expect only the token pair to differ, if at all
uv run polarexport night --date-min $(date -d '3 days ago' +%F)
```
