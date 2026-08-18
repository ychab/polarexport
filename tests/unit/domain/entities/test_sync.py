from tests.unit.factories.entities.sync import SourceSyncStatFactory
from tests.unit.factories.entities.sync import SyncReportFactory


class TestSourceSyncStat:
    def test__fields(self) -> None:
        stat = SourceSyncStatFactory.build(fetched=3)
        assert stat.fetched == 3


class TestSyncReport:
    def test__fields(self) -> None:
        report = SyncReportFactory.build()
        assert report.stats
