import asyncio
import json
import logging
from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from polarexport.application.ports.archivers.exercise import ArchiveResult
from polarexport.application.ports.archivers.exercise import ExerciseArchiverPort
from polarexport.domain.const import EXERCISE_ARCHIVE_NAME_TEMPLATE
from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.exercise_export import ExerciseManifest
from polarexport.infrastructure.adapters.archivers.atomic_zip import write_zip_atomic
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _render_readme
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_exercises_document
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_manifest

logger = logging.getLogger(__name__)


class ZipExerciseArchiver(ExerciseArchiverPort):
    """`ExerciseArchiverPort` implementation that writes a self-contained `.zip` archive.

    Shares its atomic-write mechanism with `ZipNightArchiver` via `write_zip_atomic` — the two
    archivers only differ in what goes into the zip.
    """

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
        return await asyncio.to_thread(
            self._write_sync, exercises, manifest, raw, output_dir, include_raw, include_samples, force
        )

    def _write_sync(
        self,
        exercises: Sequence[Exercise],
        manifest: ExerciseManifest,
        raw: Mapping[str, dict[str, Any]],
        output_dir: Path,
        include_raw: bool,
        include_samples: bool,
        force: bool,
    ) -> ArchiveResult:
        target = output_dir / EXERCISE_ARCHIVE_NAME_TEMPLATE.format(
            date_min=manifest.date_range.date_min.isoformat(),
            date_max=manifest.date_range.date_max.isoformat(),
        )

        entries: dict[str, str] = {
            "manifest.json": json.dumps(_serialize_manifest(manifest), indent=2, ensure_ascii=False),
            "README.md": _render_readme(manifest, include_samples=include_samples),
            "exercises.json": json.dumps(
                _serialize_exercises_document(exercises, manifest.date_range, include_samples=include_samples),
                indent=2,
                ensure_ascii=False,
            ),
        }
        if include_raw:
            entries.update(self._raw_entries(exercises, raw))

        size_bytes = write_zip_atomic(target, entries, force=force)
        logger.info("Wrote exercise export archive", extra={"path": str(target), "exercise_count": len(exercises)})
        return ArchiveResult(path=target, size_bytes=size_bytes)

    def _raw_entries(self, exercises: Sequence[Exercise], raw: Mapping[str, dict[str, Any]]) -> dict[str, str]:
        entries: dict[str, str] = {}
        for exercise in exercises:
            payload = raw.get(exercise.id)
            if payload is None:
                continue
            entries[f"raw/exercise/{exercise.date.isoformat()}-{exercise.id}.json"] = json.dumps(
                payload, indent=2, ensure_ascii=False
            )
        return entries
