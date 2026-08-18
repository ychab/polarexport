from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.entities.sync import SourceSyncStat
from polarexport.domain.entities.sync import SyncReport
from polarexport.domain.enums import NightSource

from tests.unit.factories.value_objects.date_range import DateRangeFactory


class SourceSyncStatFactory(DataclassFactory[SourceSyncStat]):
    __model__ = SourceSyncStat


class SyncReportFactory(DataclassFactory[SyncReport]):
    __model__ = SyncReport

    date_range = Use(DateRangeFactory.build)
    stats = Use(lambda: {NightSource.SLEEP: SourceSyncStatFactory.build()})
