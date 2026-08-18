from polarexport.infrastructure.adapters.providers.polar.schemas import AlertnessDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import CircadianBedtimeDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import ContinuousHeartRateDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import NightlyRechargeDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import SkinTemperatureDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import SleepDTO


class TestSleepDTO:
    def test__unknown_field__does_not_raise(self) -> None:
        dto = SleepDTO.model_validate(
            {"polar_user": "https://polaraccesslink.com/v3/users/1", "date": "2026-08-15", "a_future_field": 123}
        )
        assert dto.date.isoformat() == "2026-08-15"


class TestNightlyRechargeDTO:
    def test__unknown_field__does_not_raise(self) -> None:
        dto = NightlyRechargeDTO.model_validate(
            {"polar_user": "https://polaraccesslink.com/v3/users/1", "date": "2026-08-15", "a_future_field": 123}
        )
        assert dto.date.isoformat() == "2026-08-15"


class TestContinuousHeartRateDTO:
    def test__unknown_field__does_not_raise(self) -> None:
        dto = ContinuousHeartRateDTO.model_validate(
            {
                "polar_user": "https://polaraccesslink.com/v3/users/1",
                "date": "2026-08-15",
                "heart_rate_samples": [{"heart_rate": 60, "sample_time": "00:00:00", "a_future_field": 1}],
            }
        )
        assert dto.heart_rate_samples[0].heart_rate == 60


class TestSkinTemperatureDTO:
    def test__unknown_field__does_not_raise(self) -> None:
        dto = SkinTemperatureDTO.model_validate({"sleep_date": "2026-08-15", "a_future_field": 123})
        assert dto.sleep_date.isoformat() == "2026-08-15"


class TestAlertnessDTO:
    def test__unknown_field__does_not_raise(self) -> None:
        dto = AlertnessDTO.model_validate({"grade": 9.0, "a_future_field": 123})
        assert dto.grade == 9.0


class TestCircadianBedtimeDTO:
    def test__unknown_field__does_not_raise(self) -> None:
        dto = CircadianBedtimeDTO.model_validate({"quality": "OK", "a_future_field": 123})
        assert dto.quality == "OK"
