import zipfile
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path

import pytest

from polarexport.application.inputs.night import NightExportInput
from polarexport.application.ports.stores.night import StoredPayload
from polarexport.application.use_cases.night_export import NightExportUseCase
from polarexport.domain.const import API_NAME
from polarexport.domain.enums import NightSource
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.archivers.zip import ZipNightArchiver
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarNightMapper
from polarexport.infrastructure.adapters.stores.filesystem import FilesystemNightStore


@pytest.fixture
def day() -> date:
    return date(2026, 8, 15)


@pytest.fixture
def date_range(day: date) -> DateRange:
    return DateRange(date_min=day, date_max=day)


@pytest.fixture
def night_store(tmp_path: Path) -> FilesystemNightStore:
    return FilesystemNightStore(data_dir=tmp_path / "data")


@pytest.fixture
async def sleep_payload_stored(night_store: FilesystemNightStore, day: date) -> None:
    await night_store.write(
        StoredPayload(
            source=NightSource.SLEEP,
            date=day,
            fetched_at=datetime(2026, 8, 15, 6, 0, tzinfo=UTC),
            api=API_NAME,
            payload={
                "polar_user": "https://www.polaraccesslink.com/v3/users/12345",
                "date": day.isoformat(),
                "sleep_score": 82,
            },
        )
    )


class TestNightExportUseCase:
    async def test__happy_path__archive_written_from_store(
        self,
        night_store: FilesystemNightStore,
        sleep_payload_stored: None,
        date_range: DateRange,
        day: date,
        tmp_path: Path,
    ) -> None:
        use_case = NightExportUseCase(
            night_store=night_store,
            night_mapper=PolarNightMapper(),
            night_archiver=ZipNightArchiver(),
        )
        export_in = NightExportInput(
            date_range=date_range, sources=frozenset({NightSource.SLEEP}), output_dir=tmp_path / "export"
        )

        report = await use_case.export(export_in, today=day, generated_at=datetime(2026, 8, 15, tzinfo=UTC))

        assert report.manifest.night_count == 1
        assert report.nights[0].sleep is not None
        assert report.nights[0].sleep.sleep_score == 82
        assert report.archive_path.is_file()
        assert report.archive_size_bytes == report.archive_path.stat().st_size
        with zipfile.ZipFile(report.archive_path) as zip_file:
            assert "manifest.json" in zip_file.namelist()
            assert any(name.startswith("raw/sleep/") for name in zip_file.namelist())
