import asyncio
import json
import logging
import os
import tempfile
import zipfile
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
from polarexport.domain.exceptions import ArchiveAlreadyExistsError
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
        output_dir.mkdir(parents=True, exist_ok=True)

        target = output_dir / ARCHIVE_NAME_TEMPLATE.format(
            date_min=manifest.date_range.date_min.isoformat(),
            date_max=manifest.date_range.date_max.isoformat(),
        )
        if target.exists() and not force:
            raise ArchiveAlreadyExistsError(f"Archive already exists: {target}")

        fd, tmp_name = tempfile.mkstemp(dir=output_dir, prefix=f".{target.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with (
                os.fdopen(fd, "wb") as raw_file,
                zipfile.ZipFile(raw_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file,
            ):
                zip_file.writestr(
                    "manifest.json", json.dumps(_serialize_manifest(manifest), indent=2, ensure_ascii=False)
                )
                zip_file.writestr("README.md", _render_readme(manifest))
                zip_file.writestr(
                    "nights.json",
                    json.dumps(_serialize_nights_document(nights, manifest.date_range), indent=2, ensure_ascii=False),
                )
                if include_raw:
                    self._write_raw_entries(zip_file, raw)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        tmp_path.replace(target)
        size_bytes = target.stat().st_size
        logger.info("Wrote night export archive", extra={"path": str(target), "night_count": len(nights)})
        return ArchiveResult(path=target, size_bytes=size_bytes)

    def _write_raw_entries(
        self, zip_file: zipfile.ZipFile, raw: Mapping[NightSource, Mapping[date, dict[str, Any]]]
    ) -> None:
        for source in NightSource:
            payloads = raw.get(source)
            if not payloads:
                continue
            for day in sorted(payloads):
                zip_file.writestr(
                    f"raw/{source.value}/{day.isoformat()}.json",
                    json.dumps(payloads[day], indent=2, ensure_ascii=False),
                )
