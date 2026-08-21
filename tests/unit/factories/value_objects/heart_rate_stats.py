from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.value_objects.heart_rate_stats import HeartRateStats


class HeartRateStatsFactory(DataclassFactory[HeartRateStats]):
    __model__ = HeartRateStats
    __set_as_default_factory_for_type__ = True
