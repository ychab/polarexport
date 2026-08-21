from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.value_objects.training_load import TrainingLoad


class TrainingLoadFactory(DataclassFactory[TrainingLoad]):
    __model__ = TrainingLoad
    __set_as_default_factory_for_type__ = True
