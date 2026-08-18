from dataclasses import dataclass
from datetime import date

from polarexport.domain.entities.heart_rate import ContinuousHeartRate
from polarexport.domain.entities.recharge import NightlyRecharge
from polarexport.domain.entities.skin_temperature import SkinTemperature
from polarexport.domain.entities.sleep import Sleep
from polarexport.domain.entities.sleepwise import SleepWise


@dataclass(frozen=True, kw_only=True)
class Night:
    date: date
    sleep: Sleep | None = None
    recharge: NightlyRecharge | None = None
    skin_temperature: SkinTemperature | None = None
    sleepwise: SleepWise | None = None
    heart_rate: ContinuousHeartRate | None = None

    @property
    def has_data(self) -> bool:
        return any((self.sleep, self.recharge, self.skin_temperature, self.sleepwise, self.heart_rate))
