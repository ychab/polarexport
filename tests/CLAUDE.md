# Tests

Testing conventions live in two places:
- **Main CLAUDE.md** (`../CLAUDE.md`) — philosophy, file mirror, fixture rules, CLI pattern, factories, markers
- **CONVENTIONS.md** (`../CONVENTIONS.md`) — the longer-form testing strategy

Two things specific to this project:

- **`@pytest.mark.wiremock` is mandatory** on any integration class that talks to the WireMock Polar
  server. It pins the class to a single xdist worker so stub mappings don't race.
- **Coverage measures the tests too** (`source = ["polarexport", "tests"]`). An unused fixture body or
  a skipped test body counts as uncovered and will fail the 100% gate. Introduce a helper only in the
  phase that exercises it.
