from pathlib import Path

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from polarexport.domain.value_objects.date_range import DateRange


class ExerciseSyncInput(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    # No date_range: `GET /v3/exercises` has no date filter, so there is nothing to narrow a fetch
    # by. Date filtering is the export use case's job, applied to what is already in the store.
    with_samples: bool = True  # needed for minimum heart rate and the per-minute curve
    with_zones: bool = True  # free on the same request
    force_refresh: bool = False


class ExerciseExportInput(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    date_range: DateRange
    sports: frozenset[str] = frozenset()  # empty = every sport
    include_raw: bool = True
    include_samples: bool = True  # the per-minute curve in exercises.json
    output_dir: Path
    force: bool = False
    limit: int | None = Field(default=None, ge=1)
