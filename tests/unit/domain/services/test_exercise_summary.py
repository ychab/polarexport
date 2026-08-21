from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.domain.services.exercise_summary import summarize_by_sport

from tests.unit.factories.entities.exercise import ExerciseFactory


class TestSummarizeBySport:
    def test__aggregates_by_sport_label_sorted_by_duration_descending(self) -> None:
        kickboxing = ExerciseFactory.build(
            id="54klrKbL",
            start_time=datetime(2026, 8, 18, tzinfo=UTC),
            date=date(2026, 8, 18),
            sport="OTHER",
            detailed_sport_info="KICKBOXING_MARTIAL_ARTS",
            duration_seconds=5221.533,
            calories=786,
        )
        running_one = ExerciseFactory.build(
            id="ymmr1Q46",
            start_time=datetime(2026, 8, 19, tzinfo=UTC),
            date=date(2026, 8, 19),
            sport="RUNNING",
            detailed_sport_info=None,
            duration_seconds=1800.0,
            calories=None,
        )
        running_two = ExerciseFactory.build(
            id="09Bzklzo",
            start_time=datetime(2026, 8, 20, tzinfo=UTC),
            date=date(2026, 8, 20),
            sport="RUNNING",
            detailed_sport_info=None,
            duration_seconds=1800.0,
            calories=200,
        )

        summaries = summarize_by_sport((kickboxing, running_one, running_two))

        assert len(summaries) == 2
        assert summaries[0].sport == "Kickboxing Martial Arts"
        assert summaries[0].session_count == 1
        assert summaries[0].total_duration_seconds == 5221.533
        assert summaries[0].total_calories == 786
        assert summaries[1].sport == "Running"
        assert summaries[1].session_count == 2
        assert summaries[1].total_duration_seconds == 3600.0
        assert summaries[1].total_calories == 200

    def test__no_exercises__empty(self) -> None:
        assert summarize_by_sport(()) == ()

    def test__no_sport_label__falls_back_to_unknown(self) -> None:
        exercise = ExerciseFactory.build(sport=None, detailed_sport_info=None)

        summaries = summarize_by_sport((exercise,))

        assert summaries[0].sport == "Unknown"
