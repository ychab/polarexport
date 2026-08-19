import asyncio
import logging
import secrets
import webbrowser
from datetime import UTC
from datetime import datetime
from pathlib import Path

import httpx
from httpx import codes

import typer

from polarexport.application.inputs.auth import AuthLoginInput
from polarexport.application.use_cases.auth_login import AuthLoginUseCase
from polarexport.domain.const import CREDENTIALS_FILENAME
from polarexport.domain.entities.auth import AuthReport
from polarexport.domain.exceptions import AuthorizationDeniedError
from polarexport.domain.exceptions import AuthorizationStateMismatchError
from polarexport.domain.exceptions import AuthorizationTimeoutError
from polarexport.domain.exceptions import CredentialsAlreadyExistError
from polarexport.infrastructure.adapters.providers.polar.auth import PolarOAuthClient
from polarexport.infrastructure.config.settings.app import app_settings
from polarexport.infrastructure.config.settings.polar import polar_settings
from polarexport.infrastructure.entrypoints.cli.dependencies import get_auth_callback_receiver
from polarexport.infrastructure.entrypoints.cli.dependencies import get_credentials_store
from polarexport.infrastructure.entrypoints.cli.dependencies import get_polar_oauth_client

logger = logging.getLogger(__name__)


async def auth_logic(
    auth_in: AuthLoginInput, *, client: PolarOAuthClient, state: str, obtained_at: datetime
) -> AuthReport:
    async with client:
        use_case = AuthLoginUseCase(
            auth_provider=client,
            auth_callback_receiver=get_auth_callback_receiver(auth_in.redirect_uri),
            credentials_store=get_credentials_store(),
        )
        return await use_case.login(auth_in, state=state, obtained_at=obtained_at)


def _is_invalid_grant(e: httpx.HTTPStatusError) -> bool:
    try:
        return e.response.json().get("error") == "invalid_grant"
    except ValueError:
        return False


def auth(
    # identity
    member_id: str | None = typer.Option(
        None, "--member-id", help="Stable identifier for you within your app. Default: the Polar user id."
    ),
    # credentials
    client_id: str | None = typer.Option(None, "--client-id", help="Default: POLAR_CLIENT_ID."),
    client_secret: str | None = typer.Option(
        None, "--client-secret", help="Default: POLAR_CLIENT_SECRET. Never echoed; prompt with hide_input=True."
    ),
    redirect_uri: str | None = typer.Option(
        None, "--redirect-uri", help="Default: POLAR_REDIRECT_URI. Must match the admin console exactly."
    ),
    # processing config
    credentials_file: Path | None = typer.Option(
        None, "--credentials-file", help="Default: data/auth/credentials.json."
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Print the URL instead of launching a browser (headless / SSH)."
    ),
    timeout: float = typer.Option(
        300.0, "--timeout", min=10.0, help="Seconds to wait for the callback. Default 300, min 10."
    ),
    # force
    force: bool = typer.Option(False, "--force", help="Overwrite credentials already present at --credentials-file."),
) -> None:
    """Authorize polarexport against your Polar account."""
    resolved_client_id = client_id if client_id is not None else polar_settings.CLIENT_ID
    if resolved_client_id is None:
        typer.secho(
            "POLAR_CLIENT_ID is not set. Get it from the Credentials tab at "
            "https://admin.polaraccesslink.com, then pass --client-id or set it in .env.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    resolved_client_secret = client_secret if client_secret is not None else polar_settings.CLIENT_SECRET
    if resolved_client_secret is None:
        resolved_client_secret = typer.prompt("Polar client secret", hide_input=True)

    resolved_redirect_uri = (
        redirect_uri
        if redirect_uri is not None
        else (str(polar_settings.REDIRECT_URI) if polar_settings.REDIRECT_URI is not None else None)
    )
    if resolved_redirect_uri is None:
        typer.secho(
            "POLAR_REDIRECT_URI is not set. Register a redirect URI at https://admin.polaraccesslink.com "
            "first, then pass --redirect-uri or set POLAR_REDIRECT_URI in .env.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    resolved_credentials_file = (
        credentials_file if credentials_file is not None else app_settings.AUTH_DIR / CREDENTIALS_FILENAME
    )

    state = secrets.token_urlsafe(32)
    client = get_polar_oauth_client(client_id=resolved_client_id, client_secret=resolved_client_secret)
    authorization_url = client.authorization_url(redirect_uri=resolved_redirect_uri, state=state)

    if no_browser:
        typer.secho(f"Open this URL in a browser to authorize polarexport:\n{authorization_url}")
    else:
        typer.secho("Opening your browser to authorize with Polar...")
        webbrowser.open(authorization_url)

    auth_in = AuthLoginInput(
        member_id=member_id,
        redirect_uri=resolved_redirect_uri,
        credentials_file=resolved_credentials_file,
        force=force,
        timeout=timeout,
    )
    obtained_at = datetime.now(UTC)

    try:
        report = asyncio.run(auth_logic(auth_in, client=client, state=state, obtained_at=obtained_at))
    except AuthorizationDeniedError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except AuthorizationStateMismatchError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except AuthorizationTimeoutError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except CredentialsAlreadyExistError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except OSError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == codes.UNAUTHORIZED:
            typer.secho(
                "Authentication failed (401 Unauthorized) exchanging the code for a token. Check "
                "--client-id / --client-secret (or POLAR_CLIENT_ID / POLAR_CLIENT_SECRET).",
                fg=typer.colors.RED,
                err=True,
            )
        elif status == codes.FORBIDDEN:
            typer.secho(
                "Registration failed (403 Forbidden) — a consent is missing. Review them at "
                "https://account.polar.com.",
                fg=typer.colors.RED,
                err=True,
            )
        elif status == codes.BAD_REQUEST and _is_invalid_grant(e):
            typer.secho(
                "The authorization code was rejected (invalid_grant) — it expired (10 minutes), was "
                "already used, or --redirect-uri does not match the admin console exactly. Re-run "
                "polarexport auth to get a fresh code.",
                fg=typer.colors.RED,
                err=True,
            )
        else:
            raise
        raise typer.Exit(code=1) from e

    typer.secho(f"Authorized as Polar user {report.user_id} ✅", fg=typer.colors.GREEN)
    typer.secho(f"Registered with your application (member-id: {report.member_id})", fg=typer.colors.GREEN)
    typer.secho(f"Credentials written to {report.credentials_path}", fg=typer.colors.GREEN)
    typer.secho("Next: polarexport night", fg=typer.colors.GREEN)
