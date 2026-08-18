from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.domain.entities.skin_temperature import SkinTemperature


class TestSkinTemperature:
    def test__fields(self) -> None:
        sample = (datetime(2026, 7, 21, 2, 0, tzinfo=UTC), 0.4)
        skin_temperature = SkinTemperature(
            date=date(2026, 7, 20),
            sleep_start=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            sleep_end=datetime(2026, 7, 21, 6, 0, tzinfo=UTC),
            samples=(sample,),
            deviation=0.4,
        )
        assert skin_temperature.samples == (sample,)
        assert skin_temperature.deviation == 0.4

    def test__defaults(self) -> None:
        skin_temperature = SkinTemperature(date=date(2026, 7, 20))
        assert skin_temperature.samples == ()
        assert skin_temperature.deviation is None
