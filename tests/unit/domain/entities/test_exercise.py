from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from polarexport.domain.entities.exercise import Exercise


class TestExercise:
    def test__negative_duration__raises(self) -> None:
        with pytest.raises(ValueError, match="duration_seconds must be >= 0"):
            Exercise(
                id="54klrKbL",
                start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
                date=date(2026, 8, 18),
                duration_seconds=-1,
            )

    def test__zero_duration__valid(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            duration_seconds=0,
        )
        assert exercise.duration_seconds == 0

    def test__no_duration__valid(self) -> None:
        exercise = Exercise(
            id="54klrKbL", start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC), date=date(2026, 8, 18)
        )
        assert exercise.duration_seconds is None


class TestExerciseSportLabel:
    def test__prefers_detailed_sport_info(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            sport="OTHER",
            detailed_sport_info="KICKBOXING_MARTIAL_ARTS",
        )
        assert exercise.sport_label == "Kickboxing Martial Arts"

    def test__falls_back_to_sport(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            sport="RUNNING",
            detailed_sport_info=None,
        )
        assert exercise.sport_label == "Running"

    def test__no_sport_at_all__returns_none(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            sport=None,
            detailed_sport_info=None,
        )
        assert exercise.sport_label is None


class TestExerciseDistanceKm:
    def test__converts_meters_to_km(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            distance_meters=10_000,
        )
        assert exercise.distance_km == 10.0

    def test__no_distance__returns_none(self) -> None:
        exercise = Exercise(
            id="54klrKbL", start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC), date=date(2026, 8, 18)
        )
        assert exercise.distance_km is None


class TestExerciseAverageSpeedKmh:
    def test__derived_from_distance_and_duration(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            distance_meters=10_000,
            duration_seconds=3600,
        )
        assert exercise.average_speed_kmh == 10.0

    def test__no_distance__returns_none(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            distance_meters=None,
            duration_seconds=3600,
        )
        assert exercise.average_speed_kmh is None

    def test__no_duration__returns_none(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            distance_meters=10_000,
            duration_seconds=None,
        )
        assert exercise.average_speed_kmh is None

    def test__zero_duration__returns_none(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            distance_meters=10_000,
            duration_seconds=0,
        )
        assert exercise.average_speed_kmh is None


class TestExerciseCaloriesPerHour:
    def test__derived_from_calories_and_duration(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            calories=786,
            duration_seconds=5221.533,
        )
        assert exercise.calories_per_hour is not None
        assert round(exercise.calories_per_hour) == 542

    def test__zero_duration__returns_none(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            calories=786,
            duration_seconds=0,
        )
        assert exercise.calories_per_hour is None

    def test__no_calories__returns_none(self) -> None:
        exercise = Exercise(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, 11, 32, 8, tzinfo=UTC),
            date=date(2026, 8, 18),
            calories=None,
            duration_seconds=5221.533,
        )
        assert exercise.calories_per_hour is None
