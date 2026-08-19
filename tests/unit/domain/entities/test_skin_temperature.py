from datetime import date

from polarexport.domain.entities.skin_temperature import SkinTemperature


class TestSkinTemperature:
    def test__fields(self) -> None:
        skin_temperature = SkinTemperature(date=date(2026, 7, 20), celsius=33.8, deviation=0.4)
        assert skin_temperature.celsius == 33.8
        assert skin_temperature.deviation == 0.4

    def test__defaults(self) -> None:
        skin_temperature = SkinTemperature(date=date(2026, 7, 20))
        assert skin_temperature.celsius is None
        assert skin_temperature.deviation is None
