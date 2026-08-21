import asyncio
import json
import logging
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from polarexport.application.ports.archivers.night import ArchiveResult
from polarexport.application.ports.archivers.night import NightArchiverPort
from polarexport.domain.const import ARCHIVE_NAME_TEMPLATE
from polarexport.domain.entities.export import ExportManifest
from polarexport.domain.entities.night import Night
from polarexport.domain.enums import NightSource
from polarexport.infrastructure.adapters.archivers.atomic_zip import write_zip_atomic
from polarexport.infrastructure.adapters.archivers.serializers import _render_readme
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_manifest
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_nights_document

logger = logging.getLogger(__name__)


class ZipNightArchiver(NightArchiverPort):
    """`NightArchiverPort` implementation that writes a self-contained `.zip` archive.

    `zipfile` is synchronous; the whole write is offloaded to a worker thread via
    `asyncio.to_thread` rather than pretending it's non-blocking, since the port is `async` and this
    is a CLI writing a small file, not a server under load.
    """

    async def write(
        self,
        nights: Sequence[Night],
        manifest: ExportManifest,
        raw: Mapping[NightSource, Mapping[date, dict[str, Any]]],
        *,
        output_dir: Path,
        include_raw: bool,
        force: bool,
    ) -> ArchiveResult:
        return await asyncio.to_thread(self._write_sync, nights, manifest, raw, output_dir, include_raw, force)

    def _write_sync(
        self,
        nights: Sequence[Night],
        manifest: ExportManifest,
        raw: Mapping[NightSource, Mapping[date, dict[str, Any]]],
        output_dir: Path,
        include_raw: bool,
        force: bool,
    ) -> ArchiveResult:
        target = output_dir / ARCHIVE_NAME_TEMPLATE.format(
            date_min=manifest.date_range.date_min.isoformat(),
            date_max=manifest.date_range.date_max.isoformat(),
        )

        entries: dict[str, str] = {
            "manifest.json": json.dumps(_serialize_manifest(manifest), indent=2, ensure_ascii=False),
            "README.md": _render_readme(manifest),
            "nights.json": json.dumps(
                _serialize_nights_document(nights, manifest.date_range), indent=2, ensure_ascii=False
            ),
        }
        if include_raw:
            entries.update(self._raw_entries(raw))

        size_bytes = write_zip_atomic(target, entries, force=force)
        logger.info("Wrote night export archive", extra={"path": str(target), "night_count": len(nights)})
        return ArchiveResult(path=target, size_bytes=size_bytes)

    def _raw_entries(self, raw: Mapping[NightSource, Mapping[date, dict[str, Any]]]) -> dict[str, str]:
        entries: dict[str, str] = {}
        for source in NightSource:
            payloads = raw.get(source)
            if not payloads:
                continue
            for day in sorted(payloads):
                entries[f"raw/{source.value}/{day.isoformat()}.json"] = json.dumps(
                    payloads[day], indent=2, ensure_ascii=False
                )
        return entries
