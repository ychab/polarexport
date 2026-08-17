# Phase 5 — Polar AccessLink adapter

**Depends on:** phase 4. **Needs a Polar token:** **yes.**

## Prerequisite (user action)

`.env` must contain a working `POLAR_ACCESS_TOKEN` and `POLAR_USER_ID`. The full one-time procedure is
in **`docs/authentication.md`** — follow it exactly. Note that `POLAR_CLIENT_ID` is *not* the user id
and `POLAR_CLIENT_SECRET` is *not* the access token; the token comes from the OAuth exchange at
`https://polarremote.com/v2/oauth2/token`, and `POST /v3/users` must have succeeded (or returned
`409`) before any data endpoint works.

If `.env` is not ready, **stop and tell the user** — do not fabricate payloads.

## Reference — read these first

```
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/adapters/providers/spotify/library.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/adapters/providers/spotify/{schemas,mappers,exceptions}.py
/home/yannick/Projects/PERSONAL/museflow/museflow/infrastructure/adapters/http.py
/home/yannick/Projects/PERSONAL/museflow/tests/assets/wiremock/spotify/{mappings,__files}/
/home/yannick/Projects/PERSONAL/museflow/tests/integration/utils/wiremock.py
/home/yannick/Projects/PERSONAL/museflow/tests/integration/infrastructure/adapters/providers/spotify/
```

---

## Goal

Implement `NightProviderPort` (raw payload fetching) and `NightMapperPort` (payload → entity) against
Polar AccessLink v3.

**The provider returns raw payloads, never entities.** The mapper is a separate object used later by
the export path, reading from `data/`. Keep them independent — that is what lets a mapper fix be
applied retroactively to nights already on disk.

---

## ⚠️ First task, before writing any DTO

**Call the real API and save what comes back.** The field names below come from Polar's public docs
and are unverified against a real account.

```bash
set -a; source .env; set +a
API=https://www.polaraccesslink.com
D=$(date -d '2 days ago' +%F); FROM=$(date -d '7 days ago' +%F); TO=$(date +%F)
mkdir -p tests/assets/polar

for path in "sleep/$D" "nightly-recharge/$D" "continuous-heart-rate/$D"; do
  name=$(basename "$path"); dir=$(dirname "$path")
  curl -sS -H "Authorization: Bearer $POLAR_ACCESS_TOKEN" "$API/v3/users/$path" \
    | tee "tests/assets/polar/${dir}.json"
done

for path in "skin-temperature" "sleep-wise/alertness" "sleep-wise/circadian-bedtime"; do
  curl -sS -H "Authorization: Bearer $POLAR_ACCESS_TOKEN" "$API/v3/users/$path?from=$FROM&to=$TO" \
    | tee "tests/assets/polar/$(echo "$path" | tr '/' '-').json"
done
```

Build the DTOs from **these files**, not from this document. Then correct phase 3's provisional
`SleepStage` / `ContinuityClass` / `NightlyRechargeStatus` enum values against the real hypnogram
codes.

If an endpoint returns `403`, consent for that source is not granted on your account: record it,
exercise the `UNAVAILABLE` path, and **do not remove the source**. `204`/empty on a range endpoint is
normal.

**Scrub the assets before committing** — no real `polar_user` URL, no user id, no device serial.
Replace with placeholders.

---

## Files — `polarexport/infrastructure/adapters/providers/polar/`

### `endpoints.py`

```python
SLEEP: Final[str] = "/v3/users/sleep/{date}"
NIGHTLY_RECHARGE: Final[str] = "/v3/users/nightly-recharge/{date}"
CONTINUOUS_HEART_RATE: Final[str] = "/v3/users/continuous-heart-rate/{date}"
SKIN_TEMPERATURE: Final[str] = "/v3/users/skin-temperature"
SLEEPWISE_ALERTNESS: Final[str] = "/v3/users/sleep-wise/alertness"
SLEEPWISE_CIRCADIAN_BEDTIME: Final[str] = "/v3/users/sleep-wise/circadian-bedtime"

API_NAME: Final[str] = "polar-accesslink-v3"   # written into every StoredPayload envelope
```

### `exceptions.py`

```python
class PolarApiError(Exception): ...
class PolarNotFoundError(PolarApiError): ...    # 404 — no data for that date
class PolarForbiddenError(PolarApiError): ...   # 403 — consent missing for this source
class PolarRateLimitError(PolarApiError): ...   # 429 after retries exhausted
```
Never put the access token in an exception message.

### `schemas.py`

Pydantic DTOs matching the API shape **exactly** — same names, same nesting, no renaming, no logic.
Suffix `DTO`: `SleepDTO`, `NightlyRechargeDTO`, `SkinTemperatureDTO`, `AlertnessDTO`,
`CircadianBedtimeDTO`, `ContinuousHeartRateDTO`, plus any list-envelope the range endpoints return.

Omittable fields are `X | None = None`. Set `model_config = ConfigDict(extra="allow")` so a new Polar
field never breaks an export.

### `mappers.py`

```python
class PolarNightMapper(NightMapperPort):
    def to_sleep(self, payload: Mapping[str, Any]) -> Sleep:
        return _sleep_dto_to_entity(SleepDTO.model_validate(payload))
    ...
```

A class implementing the port, delegating to standalone `_*_dto_to_entity` functions where the real
work lives: timezone-aware datetime parsing, seconds normalisation, hypnogram key handling, building
`SleepStages`. Entities stay dumb; mappers stay explicit.

It is **stateless** — construct it anywhere, no I/O, no settings.

### `client.py`

```python
class PolarAccessLinkClient(HttpClientMixin, NightProviderPort):
    def __init__(self, access_token: str, user_id: str, base_url: HttpUrl,
                 timeout: float = 30.0, concurrency: int = 5) -> None:

    async def fetch(self, source: NightSource, dates: Sequence[date]) -> SourceFetchResult: ...
```

- Multiple inheritance with `HttpClientMixin`, like museflow's Spotify/Gemini adapters. Used as
  `async with PolarAccessLinkClient(...) as client:`.
- `Authorization: Bearer {access_token}` built in one private helper. **Never logged** — log the user
  id and the endpoint instead.
- `fetch` dispatches on `source` with `match` and a `case _: raise ValueError(...)` fallback (museflow's
  dispatcher idiom).
- Per-date sources (`sleep`, `recharge`, `heart-rate`) fan out with `asyncio.gather` bounded by
  `asyncio.Semaphore(concurrency)`. Range sources (`skin-temperature`, `sleepwise`) issue one request
  covering `min(dates)`…`max(dates)` and split the response by date.
- `sleepwise` merges two endpoints into one payload per date:
  `{"alertness": ..., "circadian_bedtime": ...}` — nothing is lost.
- **Status policy**, implemented once in a private `_get(...)`:
  - `404` → `PolarNotFoundError`, caught by `fetch` and recorded as `payloads[date] = None`. Not an
    error; this is a gap.
  - `403` → `PolarForbiddenError`; the whole source becomes `SourceAvailability.UNAVAILABLE` with no
    payloads. Other sources continue.
  - `204` / empty body → same as 404 for that date.
  - `429` after retries → `PolarRateLimitError`. Other `httpx.HTTPStatusError`s propagate.
  - `200` → return the untouched `dict`. **Do not parse into a DTO here** — the provider's job is
    transport, not interpretation.
- Log `RateLimit-Limit` / `RateLimit-Usage` response headers at DEBUG.
- `SourceFetchResult.request_count` counts actual HTTP calls made.

---

## Carried over from phase 1 — three things this phase must add

1. **`tests/integration/utils/wiremock.py`** — the `WireMockContext` admin-API helper. Phase 1 left it
   out because coverage measures test code and an unexercised helper fails the 100 % gate. Port it
   from `/home/yannick/Projects/PERSONAL/museflow/tests/integration/utils/wiremock.py`, simplified to
   the single Polar server (no `scenario` support unless you actually use it — unused branches will
   cost you coverage).

2. **`pytest_collection_modifyitems` in `tests/conftest.py`** — phase 1 registered the `polar_live`
   and `wiremock` markers but did **not** add the hook, because with no marked tests its branches
   were unreachable. Add it now, alongside the marked tests that exercise both branches:
   ```python
   @pytest.hookimpl(tryfirst=True)
   def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
       skip_live = pytest.mark.skip(reason="need --polar-live option to run")
       for item in items:
           if item.get_closest_marker("polar_live") and not config.getoption("--polar-live"):
               item.add_marker(skip_live)
           if item.get_closest_marker("wiremock"):
               item.add_marker(pytest.mark.xdist_group("wiremock-polar"))
   ```
   museflow's union-find helper handles several servers; we have one, so a fixed group name is enough.

3. **A coverage `omit` for the live tests.** `source` includes `tests`, so a `polar_live` test skipped
   in the default run counts as uncovered and will break `fail_under = 100`. Put the live tests in a
   dedicated directory and omit it:
   ```toml
   [tool.coverage.run]
   omit = ["*/__pycache__/*", "tests/integration/live/*"]
   ```
   Mirror museflow's `tests/integration/live/` layout.

## WireMock assets

Mirror museflow's layout under `tests/assets/wiremock/polar/`:

```
__files/     # response bodies — the scrubbed captures from tests/assets/polar/
mappings/    # request→response stubs, one JSON file per scenario
```

Stub at minimum: a `200` for each of the six endpoints, a `404` night, a `403` source, a `429`, and a
`500`. Use URL path patterns so a stub covers any date. The container is defined in the phase-1
`docker-compose.yml` (`wiremock-polar`, admin `http://localhost:8081`, https `https://localhost:8444`).

Port museflow's `tests/integration/utils/wiremock.py` admin-API helper for resetting stubs between
tests, simplified to the single server.

---

## Tests

`tests/{unit,integration}/infrastructure/adapters/providers/polar/test_{client,mappers,schemas}.py`.

**Unit — `pytest-httpx`**, no Docker. One test per status branch: 200, 404, 403, 204, 429-after-retries,
500. Assert the `Authorization` header is sent, and assert **the token never appears in
`caplog.text`** — make that explicit; it is the one security property here.

**Unit — mappers.** Feed `tests/assets/polar/*.json` through each mapper and assert the resulting
entity, including the `None` cases when a field is absent, and a malformed payload raising cleanly.

**Integration — WireMock.** Mark every class `@pytest.mark.wiremock` (required; it pins them to one
xdist worker). Drive the full `fetch()` for each source against the stubs and assert the
`SourceFetchResult`: payload keys, `None` for gap dates, availability, request count. Also assert the
semaphore bounds concurrency — 10 dates with `concurrency=2` still issues exactly 10 requests.

**Live.** One `@pytest.mark.polar_live` test per source hitting the real API, skipped unless
`--polar-live` is given. Assert only that the call succeeds and maps without raising — never assert on
specific values.

---

## Acceptance criteria

```bash
make lint
make test                                              # includes the WireMock integration suite
uv run pytest ./tests --polar-live -m polar_live -v    # green against the real API
```

Plus: `tests/assets/polar/*.json` and `tests/assets/wiremock/polar/**` exist and are scrubbed of
personal identifiers, and phase 3's provisional enum values are corrected against the live hypnogram.
