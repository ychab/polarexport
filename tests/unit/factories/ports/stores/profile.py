from datetime import UTC
from datetime import datetime

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.application.ports.stores.profile import StoredProfile


class StoredProfileFactory(DataclassFactory[StoredProfile]):
    __model__ = StoredProfile

    fetched_at = Use(lambda: datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
    api = "polar-accesslink-v3"
    payload = Use(lambda: {"user-id": "60233839"})
