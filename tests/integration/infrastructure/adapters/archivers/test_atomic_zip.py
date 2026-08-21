import zipfile
from pathlib import Path

from polarexport.infrastructure.adapters.archivers.atomic_zip import write_zip_atomic


class TestWriteZipAtomic:
    async def test__write__creates_zip_with_expected_entries(self, tmp_path: Path) -> None:
        target = tmp_path / "archive.zip"

        size_bytes = write_zip_atomic(target, {"a.json": "{}", "README.md": "# hi"}, force=False)

        assert target.is_file()
        assert size_bytes == target.stat().st_size
        with zipfile.ZipFile(target) as zip_file:
            assert set(zip_file.namelist()) == {"a.json", "README.md"}
            assert zip_file.read("a.json").decode("utf-8") == "{}"
            assert zip_file.read("README.md").decode("utf-8") == "# hi"

    async def test__write__result_mode_is_0600(self, tmp_path: Path) -> None:
        target = tmp_path / "archive.zip"

        write_zip_atomic(target, {"a.json": "{}"}, force=False)

        assert (target.stat().st_mode & 0o777) == 0o600

    async def test__output_dir_missing__is_created(self, tmp_path: Path) -> None:
        target = tmp_path / "fresh" / "export" / "archive.zip"

        write_zip_atomic(target, {"a.json": "{}"}, force=False)

        assert target.is_file()

    async def test__target_exists_with_force__is_overwritten(self, tmp_path: Path) -> None:
        target = tmp_path / "archive.zip"
        target.write_bytes(b"not a real zip")

        write_zip_atomic(target, {"a.json": "{}"}, force=True)

        assert target.read_bytes() != b"not a real zip"
        with zipfile.ZipFile(target) as zip_file:
            assert zip_file.namelist() == ["a.json"]

    async def test__write_is_atomic__no_leftover_temp_files(self, tmp_path: Path) -> None:
        target = tmp_path / "archive.zip"

        write_zip_atomic(target, {"a.json": "{}"}, force=False)

        assert list(tmp_path.iterdir()) == [target]
