import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--polar-live",
        action="store_true",
        default=False,
        help="Run live Polar AccessLink API tests (requires a valid POLAR_ACCESS_TOKEN).",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "polar_live: mark test as requiring live Polar API access")
    config.addinivalue_line(
        "markers",
        "wiremock: test uses the WireMock Polar server — groups tests onto a single xdist "
        "worker so stub mappings don't race",
    )


@pytest.fixture(scope="session", autouse=True)
def anyio_backend() -> str:
    """
    Configure anyio backend for all async tests.
    @see https://anyio.readthedocs.io/en/stable/testing.html#using-async-fixtures-with-higher-scopes
    """
    return "asyncio"
