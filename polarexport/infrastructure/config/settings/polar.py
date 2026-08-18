from pydantic import Field
from pydantic import HttpUrl
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

    # Required at export time.
    ACCESS_TOKEN: str = Field(..., min_length=1)  # bearer token from the OAuth exchange
    USER_ID: str = Field(..., min_length=1)  # x_user_id from that same response

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

    HTTP_TIMEOUT: float = 30.0
    HTTP_MAX_RETRIES: int = 5


polar_settings = PolarSettings()
