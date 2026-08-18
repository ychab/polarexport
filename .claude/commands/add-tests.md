# Add Tests for a Source File

You are generating tests for an existing polarexport source file, targeting 100% branch coverage.

File to test: **$ARGUMENTS**

## Process

### 1. Read and analyze the source file
- Read the file at the given path
- Identify every branch: `if/else`, early returns, exception paths, loop bodies, optional chaining
- Note all dependencies (ports, external services) that will need to be mocked or injected

### 2. Determine test type(s) needed
- **Integration test** (primary): use real collaborators — `PolarAccessLinkClient` against WireMock,
  `FilesystemNightStore` on `tmp_path`, `ZipNightArchiver`, real `PolarNightMapper`. Write these first.
- **Unit test** (gap-filling): use mocks (`AsyncMock`/`Mock` against the port ABC). Write these for
  branches hard to reach via integration (e.g., specific error handling, internal helper functions,
  edge cases).
- **Do NOT** write a unit test for a happy path already covered by an integration test — this is
  duplication, not coverage. If the integration test covers the nominal flow, unit tests only need to
  cover unreachable-via-integration branches.
- **Do NOT** create a fake (in-memory) store or archiver implementation. Use `AsyncMock`/`Mock` in unit
  tests, and the real filesystem/zip adapters on `tmp_path` in integration tests.

### 3. Check for existing fixtures and factories
Before creating new fixtures or factories, check:
- `tests/unit/conftest.py` and `tests/integration/conftest.py` — shared fixtures
- `tests/unit/factories/` — entity, input, and port-payload factories
- Reuse existing ones; create new ones only when necessary

### 4. Create factory files (if needed)

**Unit factory — domain entity:**
```python
# tests/unit/factories/entities/<name>.py
class EntityFactory(DataclassFactory[Entity]):
    __model__ = Entity
```

**Unit factory — Pydantic input schema:**
```python
# tests/unit/factories/inputs/<name>.py
class EntityInputFactory(ModelFactory[EntityInput]):
    __model__ = EntityInput
```

### 5. Write the tests

**Test class structure:**
```python
class TestMyThing:
    async def test__nominal(self, ...) -> None: ...
    async def test__<branch_condition>(self, ...) -> None: ...
    async def test__<error_case>(self, ...) -> None: ...
```

**Integration test pattern:**
```python
@pytest.mark.wiremock
class TestNightLogic:
    async def test__nominal(
        self,
        tmp_path: Path,
        today: date,
        generated_at: datetime,
    ) -> None:
        result = await night_logic(sync_in, export_in, today=today, generated_at=generated_at)
        assert result.archive_path.exists()
```

**Unit test pattern:**
```python
async def test__raises_when_no_data(
    self,
    mock_night_store: mock.AsyncMock,
) -> None:
    mock_night_store.read.return_value = {}
    with pytest.raises(NoNightDataError):
        await use_case.export(export_in, today=today, generated_at=generated_at)
```

### 6. Coverage rules
- Every `if` branch needs at least one test for the truthy path and one for the falsy path
- Every `except` block needs a test that triggers it
- Every early `return` needs a test
- Every `for` loop needs: a test with items AND a test with an empty collection (if reachable)

### 7. Typing
All test functions, fixtures, and helpers must have full type annotations. Return type of test functions is `None`.

### 8. Verify
After writing tests, run:
```bash
make test-unit         # fast, no Docker
make test-integration  # starts WireMock
```
If coverage is below 100%, identify the missing branches and add tests. Remember coverage measures
`tests/` too — an unused helper or a skipped test body counts as uncovered.

## Conventions reminders
- Test method naming: `test__<scenario>` or `test__<method>__<scenario>`
- Class naming: `Test<SubjectClass>` or `Test<SubjectFunction>`
- `mock.AsyncMock` for async ports (`NightProviderPort`, `NightStorePort`, `NightArchiverPort`),
  `mock.Mock` for sync ports (`NightMapperPort`)
- Add new shared fixtures to the appropriate `conftest.py`, not inside the test file
- Integration classes touching WireMock need `@pytest.mark.wiremock`
