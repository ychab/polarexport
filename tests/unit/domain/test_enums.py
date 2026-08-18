from polarexport.domain.enums import ContinuityClass
from polarexport.domain.enums import NightlyRechargeStatus


class TestContinuityClass:
    def test__label(self) -> None:
        assert ContinuityClass.FAIRLY_FRAGMENTED.label == "Fairly Fragmented"

    def test__label__single_word(self) -> None:
        assert ContinuityClass.FRAGMENTED.label == "Fragmented"


class TestNightlyRechargeStatus:
    def test__label(self) -> None:
        assert NightlyRechargeStatus.VERY_POOR.label == "Very Poor"

    def test__label__single_word(self) -> None:
        assert NightlyRechargeStatus.OK.label == "Ok"
