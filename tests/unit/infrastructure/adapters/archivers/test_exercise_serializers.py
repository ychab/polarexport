from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.exercise_export import SportSummary
from polarexport.domain.entities.profile import UserProfile
from polarexport.domain.enums import LoadInterpretation
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.domain.value_objects.heart_rate_stats import HeartRateStats
from polarexport.domain.value_objects.heart_rate_zone import HeartRateZone
from polarexport.domain.value_objects.training_load import TrainingLoad
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _iso
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _render_load_interpretation_table
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _render_profile_note
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _render_readme
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _render_samples_note
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _render_sports_table
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_exercise
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_exercises_document
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_heart_rate
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_heart_rate_zone
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_load_interpretation
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_manifest
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_profile
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_sport_summary
from polarexport.infrastructure.adapters.archivers.exercise_serializers import _serialize_training_load

from tests.unit.factories.entities.exercise_export import ExerciseManifestFactory


class TestIso:
    def test__none__returns_none(self) -> None:
        assert _iso(None) is None

    def test__value__returns_isoformat(self) -> None:
        value = datetime(2026, 8, 18, tzinfo=UTC)
        assert _iso(value) == value.isoformat()


class TestSerializeHeartRate:
    def test__none__returns_none(self) -> None:
        assert _serialize_heart_rate(None) is None

    def test__value__returns_dict(self) -> None:
        heart_rate = HeartRateStats(average=121, maximum=175, minimum=70)
        assert _serialize_heart_rate(heart_rate) == {"average": 121, "maximum": 175, "minimum": 70}


class TestSerializeHeartRateZone:
    def test__value__returns_dict(self) -> None:
        zone = HeartRateZone(index=0, lower_limit=98, upper_limit=118, seconds=941)
        assert _serialize_heart_rate_zone(zone) == {
            "index": 0,
            "lower_limit": 98,
            "upper_limit": 118,
            "seconds": 941,
        }


class TestSerializeLoadInterpretation:
    def test__none__returns_none(self) -> None:
        assert _serialize_load_interpretation(None) is None

    def test__value__returns_value(self) -> None:
        assert _serialize_load_interpretation(LoadInterpretation.HIGH) == "HIGH"


class TestSerializeTrainingLoad:
    def test__none__returns_none(self) -> None:
        assert _serialize_training_load(None) is None

    def test__value__returns_dict(self) -> None:
        training_load = TrainingLoad(
            cardio_load=81.1622,
            cardio_load_interpretation=LoadInterpretation.HIGH,
            muscle_load=None,
            muscle_load_interpretation=None,
            perceived_load=None,
            perceived_load_interpretation=None,
        )
        assert _serialize_training_load(training_load) == {
            "cardio_load": 81.1622,
            "cardio_load_interpretation": "HIGH",
            "muscle_load": None,
            "muscle_load_interpretation": None,
            "perceived_load": None,
            "perceived_load_interpretation": None,
        }


class TestSerializeExercise:
    def test__detailed_sport_info_present__used_as_sport(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            sport="OTHER",
            detailed_sport_info="KICKBOXING_MARTIAL_ARTS",
        )

        document = _serialize_exercise(exercise, include_samples=True)

        assert document["sport"] == "KICKBOXING_MARTIAL_ARTS"
        assert document["sport_label"] == "Kickboxing Martial Arts"

    def test__detailed_sport_info_absent__falls_back_to_sport(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            sport="RUNNING",
            detailed_sport_info=None,
        )

        document = _serialize_exercise(exercise, include_samples=True)

        assert document["sport"] == "RUNNING"

    def test__include_samples_true__heart_rate_per_minute_key_present(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            heart_rate_per_minute=(98, 112, None),
        )

        document = _serialize_exercise(exercise, include_samples=True)

        assert document["heart_rate_per_minute"] == [98, 112, None]

    def test__include_samples_false__heart_rate_per_minute_key_absent(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            heart_rate_per_minute=(98, 112),
        )

        document = _serialize_exercise(exercise, include_samples=False)

        assert "heart_rate_per_minute" not in document

    def test__heart_rate_zones_none__serializes_to_none(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            heart_rate_zones=None,
        )

        document = _serialize_exercise(exercise, include_samples=True)

        assert document["heart_rate_zones"] is None

    def test__heart_rate_zones_present__serializes_each_zone(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            heart_rate_zones=(HeartRateZone(index=0, lower_limit=98, upper_limit=118, seconds=941),),
        )

        document = _serialize_exercise(exercise, include_samples=True)

        assert document["heart_rate_zones"] == [{"index": 0, "lower_limit": 98, "upper_limit": 118, "seconds": 941}]


class TestSerializeExercisesDocument:
    def test__sorts_ascending_by_start_time(self) -> None:
        later = Exercise(id="later", start_time=datetime(2026, 8, 18, tzinfo=UTC), date=date(2026, 8, 18))
        earlier = Exercise(id="earlier", start_time=datetime(2026, 8, 17, tzinfo=UTC), date=date(2026, 8, 17))
        date_range = DateRange(date_min=date(2026, 8, 17), date_max=date(2026, 8, 18))

        document = _serialize_exercises_document([later, earlier], date_range, include_samples=True)

        assert [entry["id"] for entry in document["exercises"]] == ["earlier", "later"]
        assert document["exercise_count"] == 2


class TestSerializeSportSummary:
    def test__value__returns_dict(self) -> None:
        summary = SportSummary(
            sport="Kickboxing Martial Arts", session_count=1, total_duration_seconds=5221.5, total_calories=786
        )
        assert _serialize_sport_summary(summary) == {
            "sport": "Kickboxing Martial Arts",
            "session_count": 1,
            "total_duration_seconds": 5221.5,
            "total_calories": 786,
        }


class TestSerializeProfile:
    def test__none__returns_none(self) -> None:
        assert _serialize_profile(None) is None

    def test__value__returns_dict(self) -> None:
        profile = UserProfile(
            user_id="60233839", birthdate=date(1990, 3, 15), gender="MALE", height_cm=175.0, weight_kg=71.0
        )

        assert _serialize_profile(profile) == {
            "birthdate": "1990-03-15",
            "gender": "MALE",
            "height_cm": 175.0,
            "weight_kg": 71.0,
        }

    def test__birthdate_none__serializes_to_none(self) -> None:
        profile = UserProfile(user_id="60233839", birthdate=None)

        document = _serialize_profile(profile)

        assert document is not None
        assert document["birthdate"] is None


class TestSerializeManifest:
    def test__value__returns_expected_shape(self) -> None:
        manifest = ExerciseManifestFactory.build(
            date_range=DateRange(date_min=date(2026, 7, 22), date_max=date(2026, 8, 20)),
            availability=SourceAvailability.AVAILABLE,
            exercise_count=1,
            total_duration_seconds=5221.5,
            total_calories=786,
            sports=(
                SportSummary(sport="Aerobics", session_count=2, total_duration_seconds=7757.8, total_calories=1125),
            ),
            profile=None,
            history_window_warning=None,
        )

        document = _serialize_manifest(manifest)

        assert document["availability"] == "available"
        assert document["exercise_count"] == 1
        assert document["total_duration_seconds"] == 5221.5
        assert document["total_calories"] == 786
        assert document["sports"] == [
            {"sport": "Aerobics", "session_count": 2, "total_duration_seconds": 7757.8, "total_calories": 1125}
        ]
        assert document["profile"] is None
        assert document["history_window_warning"] is None


class TestRenderSportsTable:
    def test__empty__returns_placeholder(self) -> None:
        assert "None" in _render_sports_table(())

    def test__non_empty__renders_row(self) -> None:
        summary = SportSummary(sport="Aerobics", session_count=2, total_duration_seconds=7757.8, total_calories=1125)

        table = _render_sports_table((summary,))

        assert "Aerobics" in table
        assert "1125" in table


class TestRenderLoadInterpretationTable:
    def test__contains_every_member(self) -> None:
        table = _render_load_interpretation_table()

        for member in LoadInterpretation:
            assert member.value in table


class TestRenderProfileNote:
    def test__none__returns_unavailable_note(self) -> None:
        assert "No profile" in _render_profile_note(None)

    def test__full_profile__renders_all_fields(self) -> None:
        profile = UserProfile(
            user_id="60233839", birthdate=date(1990, 3, 15), gender="MALE", height_cm=175.0, weight_kg=71.0
        )

        note = _render_profile_note(profile)

        assert "1990-03-15" in note
        assert "MALE" in note
        assert "175.0 cm" in note
        assert "71.0 kg" in note

    def test__profile_with_unknown_fields__renders_unknown(self) -> None:
        profile = UserProfile(user_id="60233839", birthdate=None, gender=None, height_cm=None, weight_kg=None)

        note = _render_profile_note(profile)

        assert note.count("unknown") == 4


class TestRenderSamplesNote:
    def test__include_samples_true__mentions_includes(self) -> None:
        assert "includes" in _render_samples_note(include_samples=True)

    def test__include_samples_false__mentions_without(self) -> None:
        assert "without" in _render_samples_note(include_samples=False)


class TestRenderReadme:
    def test__no_history_window_warning__uses_default_note(self) -> None:
        manifest = ExerciseManifestFactory.build(history_window_warning=None, profile=None, sports=())

        readme = _render_readme(manifest, include_samples=True)

        assert "30-day exercise retention window" in readme

    def test__history_window_warning_set__is_rendered(self) -> None:
        manifest = ExerciseManifestFactory.build(
            history_window_warning="date_min is outside the 30-day window", profile=None, sports=()
        )

        readme = _render_readme(manifest, include_samples=True)

        assert "date_min is outside the 30-day window" in readme

    def test__renders_tool_name_and_version(self) -> None:
        manifest = ExerciseManifestFactory.build(
            tool_name="polarexport", tool_version="0.2.0", profile=None, sports=()
        )

        readme = _render_readme(manifest, include_samples=False)

        assert "polarexport" in readme
        assert "0.2.0" in readme
