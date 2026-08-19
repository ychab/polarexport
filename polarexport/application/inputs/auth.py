from pathlib import Path

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class AuthLoginInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    member_id: str | None = None  # defaults to the Polar user id if not given
    redirect_uri: str
    credentials_file: Path
    force: bool = False
    timeout: float = Field(default=300.0, ge=10.0)
