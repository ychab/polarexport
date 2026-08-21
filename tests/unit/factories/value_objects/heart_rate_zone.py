from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.value_objects.heart_rate_zone import HeartRateZone


class HeartRateZoneFactory(DataclassFactory[HeartRateZone]):
    __model__ = HeartRateZone
    __set_as_default_factory_for_type__ = True
