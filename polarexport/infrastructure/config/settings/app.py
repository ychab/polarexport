from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from polarexport import BASE_DIR
from polarexport.infrastructure.types import LogHandler
from polarexport.infrastructure.types import LogLevel


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POLAREXPORT_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DEBUG: bool = False

    LOG_LEVEL_CLI: LogLevel = "WARNING"
    LOG_HANDLERS_CLI: list[LogHandler] = ["cli", "cli_alert"]

    DATA_DIR: Path = BASE_DIR / "data"  # accumulating raw-payload store
    EXPORT_DIR: Path = BASE_DIR / "export"  # generated zip archives

    EXPORT_CONCURRENCY: int = Field(default=5, ge=1, le=20)  # in-flight Polar requests


app_settings = AppSettings()
