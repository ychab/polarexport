from pydantic import HttpUrl
from pydantic import field_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from polarexport import BASE_DIR


class PolarSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POLAR_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # None until `polarexport auth` has run (or the pair is set by hand). Required only where the
    # token is actually used — see cli/dependencies.get_polar_client().
    ACCESS_TOKEN: str | None = None  # bearer token from the OAuth exchange
    USER_ID: str | None = None  # x_user_id from that same response

    # Only used to (re-)run the auth flow by hand; see docs/authentication.md.
    # Deliberately optional so the tool runs with just the two values above.
    #
    # CLIENT_ID/CLIENT_SECRET identify the *application* (Credentials tab at
    # admin.polaraccesslink.com). ACCESS_TOKEN/USER_ID identify the *user's grant to that
    # application* and are what the API actually authenticates with. CLIENT_ID is not USER_ID.
    CLIENT_ID: str | None = None
    CLIENT_SECRET: str | None = None
    REDIRECT_URI: HttpUrl | None = None

    BASE_URL: HttpUrl = HttpUrl("https://www.polaraccesslink.com")
    OAUTH_TOKEN_URL: HttpUrl = HttpUrl("https://polarremote.com/v2/oauth2/token")
    OAUTH_AUTHORIZATION_URL: HttpUrl = HttpUrl("https://flow.polar.com/oauth2/authorization")

    HTTP_TIMEOUT: float = 30.0
    HTTP_MAX_RETRIES: int = 5

    @field_validator("ACCESS_TOKEN", "USER_ID", mode="before")
    @classmethod
    def _empty_string_is_absent(cls, value: str | None) -> str | None:
        return value or None


polar_settings = PolarSettings()
