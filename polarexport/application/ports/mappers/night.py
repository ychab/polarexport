from abc import ABC
from abc import abstractmethod
from collections.abc import Mapping
from typing import Any

from polarexport.domain.entities.heart_rate import ContinuousHeartRate
from polarexport.domain.entities.recharge import NightlyRecharge
from polarexport.domain.entities.skin_temperature import SkinTemperature
from polarexport.domain.entities.sleep import Sleep
from polarexport.domain.entities.sleepwise import SleepWise


class NightMapperPort(ABC):
    """A port for mapping raw Polar payloads to domain entities.

    This port exists because the export use case reads raw payloads from the store and must
    turn them into entities without the application layer importing the Polar adapter directly.
    `StoredPayload.api` records which mapper produced-shape a payload has, so a future v4 adapter
    ships its own mapper for its own stored files.
    """

    @abstractmethod
    def to_sleep(self, payload: Mapping[str, Any]) -> Sleep:
        """Map a raw sleep payload to a `Sleep` entity."""
        ...

    @abstractmethod
    def to_nightly_recharge(self, payload: Mapping[str, Any]) -> NightlyRecharge:
        """Map a raw nightly-recharge payload to a `NightlyRecharge` entity."""
        ...

    @abstractmethod
    def to_skin_temperature(self, payload: Mapping[str, Any]) -> SkinTemperature:
        """Map a raw skin-temperature payload to a `SkinTemperature` entity."""
        ...

    @abstractmethod
    def to_sleepwise(self, payload: Mapping[str, Any]) -> SleepWise:
        """Map a raw SleepWise payload to a `SleepWise` entity."""
        ...

    @abstractmethod
    def to_continuous_heart_rate(self, payload: Mapping[str, Any]) -> ContinuousHeartRate:
        """Map a raw continuous heart-rate payload to a `ContinuousHeartRate` entity."""
        ...
