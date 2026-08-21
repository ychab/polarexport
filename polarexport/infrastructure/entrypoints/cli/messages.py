import asyncio
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from polarexport.application.ports.stores.credentials import CredentialsStorePort
from polarexport.domain.const import CREDENTIALS_FILENAME
from polarexport.infrastructure.config.settings.app import app_settings


def unauthorized_message(get_credentials_store: Callable[[], CredentialsStorePort]) -> str:
    """Build the message for a 401 response, shared by every command that hits Polar.

    Takes the store getter as a parameter rather than importing one directly: each caller passes its
    own module-level `get_credentials_store`, so a test that patches that name in the caller's module
    keeps controlling this message without patching `cli.messages` itself.
    """
    stored = asyncio.run(get_credentials_store().read(app_settings.AUTH_DIR / CREDENTIALS_FILENAME))
    if stored is not None and stored.is_expired(now=datetime.now(UTC)):
        expired_at = stored.obtained_at + timedelta(seconds=stored.expires_in)
        return (
            f"Your Polar token expired on {expired_at.date().isoformat()}. Run `polarexport auth` to authorize again."
        )
    return (
        "Authentication failed (401 Unauthorized). Run `polarexport auth` to authorize again, or check "
        "`POLAR_ACCESS_TOKEN` in `.env` if you set it by hand — see `docs/authentication.md`."
    )
