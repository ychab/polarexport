from dataclasses import dataclass
from datetime import date

from polarexport.domain.enums import NightlyRechargeStatus


@dataclass(frozen=True, kw_only=True)
class NightlyRecharge:
    date: date
    nightly_recharge_status: NightlyRechargeStatus | None = None
    ans_charge: float | None = None
    ans_charge_status: int | None = None
    heart_rate_avg: int | None = None
    heart_rate_variability_avg: int | None = None
    beat_to_beat_avg: int | None = None
    breathing_rate_avg: float | None = None
