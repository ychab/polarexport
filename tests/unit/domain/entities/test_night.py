from datetime import date

from polarexport.domain.entities.night import Night

from tests.unit.factories.entities.heart_rate import ContinuousHeartRateFactory


class TestNight:
    def test__has_data__true(self) -> None:
        night = Night(date=date(2026, 7, 20), heart_rate=ContinuousHeartRateFactory.build())
        assert night.has_data is True

    def test__has_data__false(self) -> None:
        night = Night(date=date(2026, 7, 20))
        assert night.has_data is False
