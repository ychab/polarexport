import os
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path

from polarexport.domain.exceptions import ArchiveAlreadyExistsError


def write_zip_atomic(target: Path, entries: Mapping[str, str], *, force: bool) -> int:
    """Write `entries` as a zip at `target`, atomically, mode 0600. Returns the size in bytes.

    Args:
        target: The archive path to write.
        entries: Archive path to text content, written as one `writestr` per entry.
        force: Whether to overwrite an existing file at `target`.

    Raises:
        ArchiveAlreadyExistsError: `target` already exists and `force` is False.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        raise ArchiveAlreadyExistsError(f"Archive already exists: {target}")

    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    # 0600, chosen deliberately: these archives carry nightly biometrics and exercise/profile data,
    # the same sensitivity class as the bearer token in credentials.json. mkstemp already creates at
    # 0600; this makes it a decision rather than leaving it as an accident of the atomic-write
    # mechanism.
    os.fchmod(fd, 0o600)
    try:
        with (
            os.fdopen(fd, "wb") as raw_file,
            zipfile.ZipFile(raw_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file,
        ):
            for name, content in entries.items():
                zip_file.writestr(name, content)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    tmp_path.replace(target)
    return target.stat().st_size
