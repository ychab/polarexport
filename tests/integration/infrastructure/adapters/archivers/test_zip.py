import json
import os
import zipfile
from datetime import date
from pathlib import Path

from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.archivers.zip import ZipNightArchiver

from tests.unit.factories.entities.export import ExportManifestFactory
from tests.unit.factories.entities.night import NightFactory
from tests.unit.factories.entities.sleep import SleepFactory


class TestZipNightArchiverWrite:
    async def test__write__with_include_raw__creates_expected_entries(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 21))
        night = NightFactory.build(
            date=date(2026, 7, 20),
            sleep=SleepFactory.build(date=date(2026, 7, 20)),
            recharge=None,
            skin_temperature=None,
            sleepwise=None,
            heart_rate=None,
        )
        manifest = ExportManifestFactory.build(date_range=date_range, night_count=1, gaps=(date(2026, 7, 21),))
        raw = {NightSource.SLEEP: {date(2026, 7, 20): {"date": "2026-07-20", "sleep_score": 80}}}
        archiver = ZipNightArchiver()

        path = await archiver.write([night], manifest, raw, output_dir=tmp_path, include_raw=True, force=False)

        with zipfile.ZipFile(path) as zip_file:
            assert set(zip_file.namelist()) == {
                "manifest.json",
                "README.md",
                "nights.json",
                "raw/sleep/2026-07-20.json",
            }

    async def test__write__without_include_raw__excludes_raw_directory(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 20))
        night = NightFactory.build(date=date(2026, 7, 20))
        manifest = ExportManifestFactory.build(date_range=date_range, night_count=1, gaps=())
        raw = {NightSource.SLEEP: {date(2026, 7, 20): {"date": "2026-07-20"}}}
        archiver = ZipNightArchiver()

        path = await archiver.write([night], manifest, raw, output_dir=tmp_path, include_raw=False, force=False)

        with zipfile.ZipFile(path) as zip_file:
            names = set(zip_file.namelist())
            assert names == {"manifest.json", "README.md", "nights.json"}

    async def test__nights_json__round_trips_with_null_for_absent_sources(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 20))
        night = NightFactory.build(
            date=date(2026, 7, 20),
            sleep=SleepFactory.build(date=date(2026, 7, 20), sleep_score=80),
            recharge=None,
            skin_temperature=None,
            sleepwise=None,
            heart_rate=None,
        )
        manifest = ExportManifestFactory.build(date_range=date_range, night_count=1, gaps=())
        archiver = ZipNightArchiver()

        path = await archiver.write([night], manifest, {}, output_dir=tmp_path, include_raw=False, force=False)

        with zipfile.ZipFile(path) as zip_file:
            document = json.loads(zip_file.read("nights.json"))

        assert document["night_count"] == 1
        night_entry = document["nights"][0]
        assert night_entry["date"] == "2026-07-20"
        assert night_entry["sleep"]["sleep_score"] == 80
        assert night_entry["recharge"] is None
        assert night_entry["skin_temperature"] is None
        assert night_entry["sleepwise"] is None
        assert night_entry["heart_rate"] is None

    async def test__manifest_json__matches_export_manifest(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 21))
        night = NightFactory.build(date=date(2026, 7, 20))
        manifest = ExportManifestFactory.build(
            date_range=date_range,
            night_count=1,
            gaps=(date(2026, 7, 21),),
            source_availability={NightSource.SLEEP: SourceAvailability.AVAILABLE},
            sources_requested=(NightSource.SLEEP,),
            history_window_warning="date_min is outside the retention window",
        )
        archiver = ZipNightArchiver()

        path = await archiver.write([night], manifest, {}, output_dir=tmp_path, include_raw=False, force=False)

        with zipfile.ZipFile(path) as zip_file:
            manifest_json = json.loads(zip_file.read("manifest.json"))

        assert manifest_json["tool_name"] == manifest.tool_name
        assert manifest_json["tool_version"] == manifest.tool_version
        assert manifest_json["night_count"] == 1
        assert manifest_json["date_range"] == {"date_min": "2026-07-20", "date_max": "2026-07-21"}
        assert manifest_json["sources_requested"] == ["sleep"]
        assert manifest_json["source_availability"] == {"sleep": "available"}
        assert manifest_json["gaps"] == ["2026-07-21"]
        assert manifest_json["history_window_warning"] == "date_min is outside the retention window"

    async def test__readme__mentions_28_day_caveat_and_every_requested_source(self, tmp_path: Path) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 20))
        night = NightFactory.build(date=date(2026, 7, 20))
        manifest = ExportManifestFactory.build(
            date_range=date_range,
            night_count=1,
            gaps=(),
            source_availability={source: SourceAvailability.AVAILABLE for source in NightSource},
            sources_requested=tuple(NightSource),
        )
        archiver = ZipNightArchiver()

        path = await archiver.write([night], manifest, {}, output_dir=tmp_path, include_raw=False, force=False)

        with zipfile.ZipFile(path) as zip_file:
            readme = zip_file.read("README.md").decode("utf-8")

        assert readme.strip()
        assert "28-day" in readme
        for source in NightSource:
            assert source.value in readme

    async def test__access_token_never_appears_in_archive(self, tmp_path: Path) -> None:
        access_token = os.environ["POLAR_ACCESS_TOKEN"]
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 20))
        night = NightFactory.build(date=date(2026, 7, 20))
        manifest = ExportManifestFactory.build(date_range=date_range, night_count=1, gaps=())
        raw = {NightSource.SLEEP: {date(2026, 7, 20): {"date": "2026-07-20", "sleep_score": 80}}}
        archiver = ZipNightArchiver()

        path = await archiver.write([night], manifest, raw, output_dir=tmp_path, include_raw=True, force=False)

        with zipfile.ZipFile(path) as zip_file:
            for name in zip_file.namelist():
                assert access_token not in zip_file.read(name).decode("utf-8")
