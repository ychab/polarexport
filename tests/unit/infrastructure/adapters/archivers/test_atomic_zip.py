from pathlib import Path

import pytest

from polarexport.domain.exceptions import ArchiveAlreadyExistsError
from polarexport.infrastructure.adapters.archivers.atomic_zip import write_zip_atomic


class TestWriteZipAtomic:
    async def test__target_exists_without_force__raises_archive_already_exists_error(self, tmp_path: Path) -> None:
        target = tmp_path / "archive.zip"
        target.write_bytes(b"not a real zip")

        with pytest.raises(ArchiveAlreadyExistsError):
            write_zip_atomic(target, {"a.json": "{}"}, force=False)

        assert target.read_bytes() == b"not a real zip"


class TestWriteZipAtomicEntryFailure:
    @pytest.fixture
    def failing_writestr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(*args: object, **kwargs: object) -> None:
            raise ValueError("boom")

        monkeypatch.setattr("zipfile.ZipFile.writestr", _raise)

    async def test__entry_writing_fails__no_target_or_temp_file_left_behind(
        self, tmp_path: Path, failing_writestr: None
    ) -> None:
        target = tmp_path / "archive.zip"

        with pytest.raises(ValueError, match="boom"):
            write_zip_atomic(target, {"a.json": "{}"}, force=False)

        assert list(tmp_path.iterdir()) == []
