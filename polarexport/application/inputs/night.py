from pathlib import Path

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from polarexport.domain.enums import NightSource
from polarexport.domain.value_objects.date_range import DateRange


class NightSyncInput(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    date_range: DateRange
    sources: frozenset[NightSource] = frozenset(NightSource)
    force_refresh: bool = False  # re-fetch dates already present in the store
    limit: int | None = Field(default=None, ge=1)

    @field_validator("sources")
    @classmethod
    def _sources_non_empty(cls, sources: frozenset[NightSource]) -> frozenset[NightSource]:
        if not sources:
            raise ValueError("sources must not be empty")
        return sources


class NightExportInput(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    date_range: DateRange
    sources: frozenset[NightSource] = frozenset(NightSource)
    include_raw: bool = True
    output_dir: Path
    force: bool = False  # overwrite an existing archive
    limit: int | None = Field(default=None, ge=1)

    @field_validator("sources")
    @classmethod
    def _sources_non_empty(cls, sources: frozenset[NightSource]) -> frozenset[NightSource]:
        if not sources:
            raise ValueError("sources must not be empty")
        return sources
