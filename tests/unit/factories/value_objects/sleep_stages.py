from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.value_objects.sleep_stages import SleepStages


class SleepStagesFactory(DataclassFactory[SleepStages]):
    __model__ = SleepStages
    __set_as_default_factory_for_type__ = True

    light_seconds = Use(DataclassFactory.__faker__.random_int, min=0, max=3600)
    deep_seconds = Use(DataclassFactory.__faker__.random_int, min=0, max=3600)
    rem_seconds = Use(DataclassFactory.__faker__.random_int, min=0, max=3600)
    unrecognized_seconds = Use(DataclassFactory.__faker__.random_int, min=0, max=3600)
