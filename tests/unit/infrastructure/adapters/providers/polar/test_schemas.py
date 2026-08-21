from polarexport.infrastructure.adapters.providers.polar.schemas import AlertnessDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import CircadianBedtimeDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import ContinuousHeartRateDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import ExerciseDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import NightlyRechargeDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import SkinTemperatureDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import SleepDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import TrainingLoadProDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import UserProfileDTO


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


class TestExerciseDTO:
    def test__unknown_field__does_not_raise(self) -> None:
        dto = ExerciseDTO.model_validate({"id": "abc123", "start_time": "2026-08-18T11:32:08", "a_future_field": 123})
        assert dto.id == "abc123"

    def test__hyphenated_running_index__parsed_by_alias(self) -> None:
        dto = ExerciseDTO.model_validate({"id": "abc123", "start_time": "2026-08-18T11:32:08", "running-index": 55})
        assert dto.running_index == 55


class TestTrainingLoadProDTO:
    def test__hyphenated_fields__parsed_by_alias(self) -> None:
        dto = TrainingLoadProDTO.model_validate(
            {
                "cardio-load": 81.1622,
                "cardio-load-interpretation": "HIGH",
                "muscle-load": -1.0,
                "muscle-load-interpretation": "NOT_AVAILABLE",
                "perceived-load": 0.0,
                "perceived-load-interpretation": "NOT_AVAILABLE",
                "user-rpe": "UNKNOWN",
                "a_future_field": 123,
            }
        )
        assert dto.cardio_load == 81.1622
        assert dto.cardio_load_interpretation == "HIGH"
        assert dto.user_rpe == "UNKNOWN"


class TestUserProfileDTO:
    def test__hyphenated_fields__parsed_by_alias(self) -> None:
        dto = UserProfileDTO.model_validate(
            {
                "polar-user-id": 60233839,
                "member-id": "redacted-member",
                "first-name": "Test",
                "last-name": "User",
                "birthdate": "1990-03-15",
                "a_future_field": 123,
            }
        )
        assert dto.polar_user_id == 60233839
        assert dto.first_name == "Test"
        assert dto.birthdate is not None
        assert dto.birthdate.isoformat() == "1990-03-15"
