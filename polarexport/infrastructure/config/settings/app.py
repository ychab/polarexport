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

    DATA_DIR: Path = BASE_DIR / "data"  # the single root: raw/, export/, auth/
    EXPORT_DIR: Path | None = None  # override; defaults to DATA_DIR / "export"

    EXPORT_CONCURRENCY: int = Field(default=5, ge=1, le=20)  # in-flight Polar requests

    @property
    def RAW_DIR(self) -> Path:
        return self.DATA_DIR / "raw"

    @property
    def AUTH_DIR(self) -> Path:
        return self.DATA_DIR / "auth"

    @property
    def RESOLVED_EXPORT_DIR(self) -> Path:
        return self.EXPORT_DIR if self.EXPORT_DIR is not None else self.DATA_DIR / "export"


app_settings = AppSettings()
