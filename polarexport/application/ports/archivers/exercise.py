from abc import ABC
from abc import abstractmethod
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.exercise_export import ExerciseManifest


@dataclass(frozen=True, kw_only=True)
class ArchiveResult:
    path: Path
    size_bytes: int


class ExerciseArchiverPort(ABC):
    """A port for writing exercise export archives to local storage."""

    @abstractmethod
    async def write(
        self,
        exercises: Sequence[Exercise],
        manifest: ExerciseManifest,
        raw: Mapping[str, dict[str, Any]],
        *,
        output_dir: Path,
        include_raw: bool,
        include_samples: bool,
        force: bool,
    ) -> ArchiveResult:
        """Write the export archive and return its path and size.

        Args:
            exercises: The mapped exercises to include in the archive.
            manifest: The manifest describing the export.
            raw: The raw payloads to optionally bundle alongside the mapped exercises, keyed by id.
            output_dir: The directory the archive is written to.
            include_raw: Whether to bundle `raw` inside the archive.
            include_samples: Whether to keep `heart_rate_per_minute` on each exercise, or strip it
                before writing — the flag reaches the archiver rather than mutating the (frozen)
                entities, which stay the mapper's untouched output.
            force: Whether to overwrite an existing archive at the target path.

        Returns:
            The path and byte size of the written archive.

        Raises:
            ArchiveAlreadyExistsError: The target archive exists and `force` is False.
        """
        ...
