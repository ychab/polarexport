from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.entities.profile import UserProfile


class UserProfileFactory(DataclassFactory[UserProfile]):
    __model__ = UserProfile
    __set_as_default_factory_for_type__ = True

    user_id = Use(lambda: "60233839")
