import json
import zipfile
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

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

from tests import ASSETS_DIR

POLAR_ASSETS_DIR = ASSETS_DIR / "polar"


def _load(name: str) -> dict[str, Any]:
    return json.loads((POLAR_ASSETS_DIR / f"{name}.json").read_text())  # type: ignore[no-any-return]


def _load_list(name: str) -> list[dict[str, Any]]:
    return json.loads((POLAR_ASSETS_DIR / f"{name}.json").read_text())  # type: ignore[no-any-return]


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


@pytest.fixture
async def full_fidelity_payloads_stored(night_store: FilesystemNightStore, day: date) -> None:
    for source, payload in (
        (NightSource.SLEEP, _load("sleep")),
        (NightSource.RECHARGE, _load("nightly-recharge")),
        (NightSource.SKIN_TEMPERATURE, _load_list("skin-temperature")[0]),
        (NightSource.SLEEPWISE, _load("sleepwise")),
    ):
        await night_store.write(
            StoredPayload(
                source=source,
                date=day,
                fetched_at=datetime(2026, 8, 15, 6, 0, tzinfo=UTC),
                api=API_NAME,
                payload=payload,
            )
        )


class TestNightExportUseCaseDataFidelity:
    async def test__nights_json_carries_fields_dropped_before_phase_16(
        self,
        night_store: FilesystemNightStore,
        full_fidelity_payloads_stored: None,
        day: date,
        tmp_path: Path,
    ) -> None:
        use_case = NightExportUseCase(
            night_store=night_store,
            night_mapper=PolarNightMapper(),
            night_archiver=ZipNightArchiver(),
        )
        export_in = NightExportInput(
            date_range=DateRange(date_min=day, date_max=day),
            sources=frozenset(
                {NightSource.SLEEP, NightSource.RECHARGE, NightSource.SKIN_TEMPERATURE, NightSource.SLEEPWISE}
            ),
            output_dir=tmp_path / "export",
        )

        report = await use_case.export(export_in, today=day, generated_at=datetime(2026, 8, 15, tzinfo=UTC))

        with zipfile.ZipFile(report.archive_path) as zip_file:
            nights_document = json.loads(zip_file.read("nights.json"))

        night = next(entry for entry in nights_document["nights"] if entry["date"] == day.isoformat())

        assert night["sleep"]["heart_rate_samples"]
        assert night["recharge"]["hrv_samples"]
        assert night["recharge"]["breathing_samples"]
        assert isinstance(night["skin_temperature"]["celsius"], float)
        assert set(night["skin_temperature"].keys()) == {"celsius", "deviation"}
        assert isinstance(night["sleepwise"]["grade"], float)
