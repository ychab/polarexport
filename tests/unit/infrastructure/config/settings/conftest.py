import pytest

# Every variable the two settings models read. `.envrc` (direnv) exports POLAREXPORT_DEBUG and
# `dotenv`-loads the real `.env`, so on a developer machine these tests would otherwise assert
# against the developer's own credentials instead of the models' declared defaults.
_SETTINGS_ENV_VARS = (
    "POLAREXPORT_DEBUG",
    "POLAREXPORT_LOG_LEVEL_CLI",
    "POLAREXPORT_LOG_HANDLERS_CLI",
    "POLAREXPORT_DATA_DIR",
    "POLAREXPORT_EXPORT_DIR",
    "POLAREXPORT_EXPORT_CONCURRENCY",
    "POLAR_ACCESS_TOKEN",
    "POLAR_USER_ID",
    "POLAR_CLIENT_ID",
    "POLAR_CLIENT_SECRET",
    "POLAR_REDIRECT_URI",
    "POLAR_BASE_URL",
    "POLAR_HTTP_TIMEOUT",
    "POLAR_HTTP_MAX_RETRIES",
)


@pytest.fixture(autouse=True)
def isolated_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every settings variable from the environment so these tests see the model defaults.

    Settings tests are the one place where ambient environment is the subject under test rather than
    background noise; each test opts back in to exactly the variables it needs.
    """
    for name in _SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
