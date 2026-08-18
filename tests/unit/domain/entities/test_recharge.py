from datetime import date

from polarexport.domain.entities.recharge import NightlyRecharge
from polarexport.domain.enums import NightlyRechargeStatus


class TestNightlyRecharge:
    def test__fields(self) -> None:
        recharge = NightlyRecharge(
            date=date(2026, 7, 20),
            nightly_recharge_status=NightlyRechargeStatus.GOOD,
            ans_charge=1.5,
            ans_charge_status=1,
            heart_rate_avg=50,
            heart_rate_variability_avg=60,
            beat_to_beat_avg=900,
            breathing_rate_avg=14.5,
        )
        assert recharge.nightly_recharge_status is NightlyRechargeStatus.GOOD
        assert recharge.ans_charge == 1.5

    def test__defaults_are_none(self) -> None:
        recharge = NightlyRecharge(date=date(2026, 7, 20))
        assert recharge.nightly_recharge_status is None
        assert recharge.ans_charge is None
