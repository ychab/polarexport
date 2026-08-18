# Phase 10 — CLI error handling gaps

**Depends on:** phase 8. **Needs a Polar token:** no (WireMock reproduces every case).

## Goal

Three failure modes a normal user will hit reach the terminal as an unhandled Python traceback. For a
CLI this is a defect: a traceback tells the user nothing actionable and looks like a crash.

`polarexport/infrastructure/entrypoints/cli/commands/night.py` catches exactly four things:

```python
except httpx.HTTPStatusError as e:      # and re-raises unless status == 401
except NoNightDataError as e:
except (InvalidDateRangeError, ArchiveAlreadyExistsError) as e:
```

## Uncovered failure modes

| Trigger | Current behaviour | Should be |
|---|---|---|
| Polar still 429s after the tenacity policy is exhausted | `PolarRateLimitError` traceback | red message: rate limited, retry later; the store keeps what it already fetched |
| No network / DNS failure / Polar down | `httpx.ConnectError` traceback | red message naming the base URL; suggest `--no-refresh` to build from `data/` |
| Any non-401 HTTP status surviving retries (e.g. 500) | re-raised, traceback | red message with the status code |

The rate-limit case is the most likely of the three: a full 28-day × 5-source sync is ~90 requests
against an API with published rate limits, and `NightProviderPort.fetch` already documents
`Raises: PolarRateLimitError` — the contract is declared and simply not honoured by the caller.

`PolarRateLimitError` also crosses a layer boundary: it is defined in
`infrastructure/adapters/providers/polar/exceptions.py`, and the CLI would import it from there,
which is fine (both are infrastructure) — but note the port docstring in the **application** layer
already names it, which is a small leak worth deciding on. Either promote a neutral
`ProviderRateLimitError` into `domain/exceptions.py` and have the adapter subclass it, or amend the
port docstring to describe the condition without naming an adapter class.

## Implementation

Extend the `try` block in `night()` (the callback owns all output — `night_logic` must stay silent,
per `CLAUDE.md`):

```python
except PolarRateLimitError as e:
    typer.secho(..., fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1) from e
except httpx.RequestError as e:          # ConnectError, ReadTimeout, ...
    ...
except httpx.HTTPStatusError as e:       # widen: handle 401 specially, all others gracefully
    ...
```

Keep the existing 401 message and its pointer to `docs/authentication.md`.

Partial-sync note for the messages: because every fetched payload is written to `data/` as it
arrives, a mid-run failure is not a lost run. Say so — it changes what the user does next.

## Files touched

```
polarexport/infrastructure/entrypoints/cli/commands/night.py
polarexport/domain/exceptions.py                        # only if the neutral-exception option is taken
polarexport/application/ports/providers/night.py        # docstring, same condition
```

## Tests

`tests/unit/infrastructure/entrypoints/cli/commands/test_night.py`, class `TestNightCommand` — the
existing autouse mock of `night_logic` makes this cheap. One test per row of the table above:
`side_effect` the exception, assert exit code 1, assert the message lands on **stderr**, and assert
no traceback is printed.

## Acceptance criteria

- [ ] No unhandled traceback for rate limiting, connection failure, or a 5xx.
- [ ] Every message is red, on stderr, exit code 1, and says what to do next.
- [ ] `night_logic` still prints nothing.
- [ ] `make lint` clean, `make test` green at 100% branch coverage.
