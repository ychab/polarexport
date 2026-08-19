from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.entities.credentials import StoredCredentials


class StoredCredentialsFactory(DataclassFactory[StoredCredentials]):
    __model__ = StoredCredentials
