from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.value_objects.speed_stats import SpeedStats


class SpeedStatsFactory(DataclassFactory[SpeedStats]):
    __model__ = SpeedStats
    __set_as_default_factory_for_type__ = True
