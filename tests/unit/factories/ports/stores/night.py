from datetime import UTC
from datetime import date
from datetime import datetime

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.application.ports.stores.night import StoredPayload


class StoredPayloadFactory(DataclassFactory[StoredPayload]):
    __model__ = StoredPayload

    date = Use(lambda: date(2026, 7, 20))
    fetched_at = Use(lambda: datetime(2026, 7, 20, 6, 0, tzinfo=UTC))
    api = "polar-accesslink-v3"
