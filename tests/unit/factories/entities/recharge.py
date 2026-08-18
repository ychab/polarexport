from datetime import date

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.entities.recharge import NightlyRecharge


class NightlyRechargeFactory(DataclassFactory[NightlyRecharge]):
    __model__ = NightlyRecharge
    __set_as_default_factory_for_type__ = True

    date = Use(lambda: date(2026, 7, 20))
