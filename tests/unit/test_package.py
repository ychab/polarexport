from pathlib import Path

import polarexport


class TestPackageMetadata:
    def test__project_name(self) -> None:
        assert polarexport.__project_name__ == "polarexport"

    def test__version(self) -> None:
        assert polarexport.__version__

    def test__project_dir_is_the_package_directory(self) -> None:
        assert polarexport.PROJECT_DIR == Path(polarexport.__file__).parent

    def test__base_dir_is_the_repository_root(self) -> None:
        assert (polarexport.BASE_DIR / "pyproject.toml").is_file()
