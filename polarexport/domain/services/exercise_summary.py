from collections.abc import Sequence

from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.exercise_export import SportSummary


def summarize_by_sport(exercises: Sequence[Exercise]) -> tuple[SportSummary, ...]:
    totals_by_sport: dict[str, dict[str, float]] = {}
    for exercise in exercises:
        sport = exercise.sport_label or "Unknown"
        bucket = totals_by_sport.setdefault(sport, {"session_count": 0, "duration_seconds": 0.0, "calories": 0})
        bucket["session_count"] += 1
        bucket["duration_seconds"] += exercise.duration_seconds or 0
        bucket["calories"] += exercise.calories or 0

    summaries = [
        SportSummary(
            sport=sport,
            session_count=int(totals["session_count"]),
            total_duration_seconds=totals["duration_seconds"],
            total_calories=int(totals["calories"]),
        )
        for sport, totals in totals_by_sport.items()
    ]
    return tuple(sorted(summaries, key=lambda summary: summary.total_duration_seconds, reverse=True))
