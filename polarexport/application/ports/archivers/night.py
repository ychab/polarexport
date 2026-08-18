from abc import ABC
from abc import abstractmethod
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from polarexport.domain.entities.export import ExportManifest
from polarexport.domain.entities.night import Night
from polarexport.domain.enums import NightSource


class NightArchiverPort(ABC):
    """A port for writing night export archives to local storage."""

    @abstractmethod
    async def write(
        self,
        nights: Sequence[Night],
        manifest: ExportManifest,
        raw: Mapping[NightSource, Mapping[date, dict[str, Any]]],
        *,
        output_dir: Path,
        include_raw: bool,
        force: bool,
    ) -> Path:
        """Write the export archive and return its path.

        Args:
            nights: The merged nights to include in the archive.
            manifest: The manifest describing the export.
            raw: The raw payloads to optionally bundle alongside the mapped nights.
            output_dir: The directory the archive is written to.
            include_raw: Whether to bundle `raw` inside the archive.
            force: Whether to overwrite an existing archive at the target path.

        Returns:
            The path of the written archive.

        Raises:
            ArchiveAlreadyExistsError: The target archive exists and `force` is False.
        """
        ...
