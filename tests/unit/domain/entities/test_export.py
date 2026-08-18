from tests.unit.factories.entities.export import ExportManifestFactory
from tests.unit.factories.entities.export import ExportReportFactory


class TestExportManifest:
    def test__fields(self) -> None:
        manifest = ExportManifestFactory.build(night_count=5)
        assert manifest.night_count == 5


class TestExportReport:
    def test__fields(self) -> None:
        report = ExportReportFactory.build()
        assert report.manifest is not None
