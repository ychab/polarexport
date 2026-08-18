from datetime import date
from pathlib import Path

import pytest

from polarexport.domain.const import ARCHIVE_NAME_TEMPLATE
from polarexport.domain.exceptions import ArchiveAlreadyExistsError
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.infrastructure.adapters.archivers.zip import ZipNightArchiver

from tests.unit.factories.entities.export import ExportManifestFactory
from tests.unit.factories.entities.night import NightFactory


class TestZipNightArchiverWrite:
    @pytest.fixture
    def date_range(self) -> DateRange:
        return DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 20))

    @pytest.fixture
    def archive_name(self, date_range: DateRange) -> str:
        return ARCHIVE_NAME_TEMPLATE.format(
            date_min=date_range.date_min.isoformat(), date_max=date_range.date_max.isoformat()
        )

    async def test__target_exists_without_force__raises_archive_already_exists_error(
        self, tmp_path: Path, date_range: DateRange, archive_name: str
    ) -> None:
        (tmp_path / archive_name).write_bytes(b"not a real zip")
        night = NightFactory.build(date=date(2026, 7, 20))
        manifest = ExportManifestFactory.build(date_range=date_range, night_count=1, gaps=())
        archiver = ZipNightArchiver()

        with pytest.raises(ArchiveAlreadyExistsError):
            await archiver.write([night], manifest, {}, output_dir=tmp_path, include_raw=False, force=False)

    async def test__target_exists_with_force__is_overwritten(
        self, tmp_path: Path, date_range: DateRange, archive_name: str
    ) -> None:
        target = tmp_path / archive_name
        target.write_bytes(b"not a real zip")
        night = NightFactory.build(date=date(2026, 7, 20))
        manifest = ExportManifestFactory.build(date_range=date_range, night_count=1, gaps=())
        archiver = ZipNightArchiver()

        path = await archiver.write([night], manifest, {}, output_dir=tmp_path, include_raw=False, force=True)

        assert path == target
        assert path.read_bytes() != b"not a real zip"

    async def test__output_dir_missing__is_created(self, tmp_path: Path, date_range: DateRange) -> None:
        output_dir = tmp_path / "fresh" / "export"
        night = NightFactory.build(date=date(2026, 7, 20))
        manifest = ExportManifestFactory.build(date_range=date_range, night_count=1, gaps=())
        archiver = ZipNightArchiver()

        path = await archiver.write([night], manifest, {}, output_dir=output_dir, include_raw=False, force=False)

        assert path.is_file()


class TestZipNightArchiverWriteSerializationFailure:
    @pytest.fixture
    def failing_readme_render(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(*args: object, **kwargs: object) -> str:
            raise ValueError("boom")

        monkeypatch.setattr("polarexport.infrastructure.adapters.archivers.zip._render_readme", _raise)

    async def test__serialisation_fails__temp_file_is_cleaned_up_and_no_archive_left_behind(
        self, tmp_path: Path, failing_readme_render: None
    ) -> None:
        date_range = DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 20))
        night = NightFactory.build(date=date(2026, 7, 20))
        manifest = ExportManifestFactory.build(date_range=date_range, night_count=1, gaps=())
        archiver = ZipNightArchiver()

        with pytest.raises(ValueError, match="boom"):
            await archiver.write([night], manifest, {}, output_dir=tmp_path, include_raw=False, force=False)

        assert list(tmp_path.iterdir()) == []
