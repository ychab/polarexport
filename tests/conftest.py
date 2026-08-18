import logging
from collections.abc import Iterable

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


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_live = pytest.mark.skip(reason="need --polar-live option to run")
    for item in items:
        if item.get_closest_marker("polar_live") and not config.getoption("--polar-live"):
            item.add_marker(skip_live)
        if item.get_closest_marker("wiremock"):
            item.add_marker(pytest.mark.xdist_group("wiremock-polar"))


@pytest.fixture(scope="session", autouse=True)
def anyio_backend() -> str:
    """
    Configure anyio backend for all async tests.
    @see https://anyio.readthedocs.io/en/stable/testing.html#using-async-fixtures-with-higher-scopes
    """
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def configure_logging() -> Iterable[None]:
    from polarexport.infrastructure.config.loggers import configure_loggers

    configure_loggers(level="DEBUG", handlers=["null"], propagate=True)
    yield
    logging.shutdown()
