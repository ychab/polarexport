from collections.abc import Sequence
from datetime import datetime
from importlib import resources
from string import Template
from typing import Any

from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.exercise_export import ExerciseManifest
from polarexport.domain.entities.exercise_export import SportSummary
from polarexport.domain.entities.profile import UserProfile
from polarexport.domain.enums import LoadInterpretation
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.domain.value_objects.heart_rate_stats import HeartRateStats
from polarexport.domain.value_objects.heart_rate_zone import HeartRateZone
from polarexport.domain.value_objects.speed_stats import SpeedStats
from polarexport.domain.value_objects.training_load import TrainingLoad

_EXERCISES_SCHEMA_VERSION = 1

_README_TEMPLATE = (
    resources.files("polarexport.infrastructure.adapters.archivers.templates")
    .joinpath("exercise-README.md")
    .read_text(encoding="utf-8")
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _serialize_date_range(date_range: DateRange) -> dict[str, str]:
    return {
        "date_min": date_range.date_min.isoformat(),
        "date_max": date_range.date_max.isoformat(),
    }


def _serialize_heart_rate(heart_rate: HeartRateStats | None) -> dict[str, int | None] | None:
    if heart_rate is None:
        return None
    return {
        "average": heart_rate.average,
        "maximum": heart_rate.maximum,
        "minimum": heart_rate.minimum,
    }


def _serialize_speed_stats(speed: SpeedStats | None) -> dict[str, float | None] | None:
    if speed is None:
        return None
    return {
        "average_kmh": speed.average_kmh,
        "maximum_kmh": speed.maximum_kmh,
        "minimum_kmh": speed.minimum_kmh,
    }


def _serialize_heart_rate_zone(zone: HeartRateZone) -> dict[str, int | None]:
    return {
        "index": zone.index,
        "lower_limit": zone.lower_limit,
        "upper_limit": zone.upper_limit,
        "seconds": zone.seconds,
    }


def _serialize_load_interpretation(value: LoadInterpretation | None) -> str | None:
    return value.value if value is not None else None


def _serialize_training_load(training_load: TrainingLoad | None) -> dict[str, Any] | None:
    if training_load is None:
        return None
    return {
        "cardio_load": training_load.cardio_load,
        "cardio_load_interpretation": _serialize_load_interpretation(training_load.cardio_load_interpretation),
        "muscle_load": training_load.muscle_load,
        "muscle_load_interpretation": _serialize_load_interpretation(training_load.muscle_load_interpretation),
        "perceived_load": training_load.perceived_load,
        "perceived_load_interpretation": _serialize_load_interpretation(training_load.perceived_load_interpretation),
    }


def _serialize_exercise(exercise: Exercise, *, include_samples: bool) -> dict[str, Any]:
    document: dict[str, Any] = {
        "id": exercise.id,
        "start_time": exercise.start_time.isoformat(),
        "date": exercise.date.isoformat(),
        # `detailed_sport_info` is what gets exported as `sport` — Polar's own top-level `sport`
        # field is frequently the useless "OTHER"; see the archive README's "sport vs sport_label".
        "sport": exercise.detailed_sport_info or exercise.sport,
        "sport_label": exercise.sport_label,
        "duration_seconds": exercise.duration_seconds,
        "calories": exercise.calories,
        "calories_per_hour": exercise.calories_per_hour,
        "distance_km": exercise.distance_km,
        "average_speed_kmh": exercise.average_speed_kmh,
        "speed": _serialize_speed_stats(exercise.speed),
        "heart_rate": _serialize_heart_rate(exercise.heart_rate),
        "heart_rate_zones": (
            [_serialize_heart_rate_zone(zone) for zone in exercise.heart_rate_zones]
            if exercise.heart_rate_zones is not None
            else None
        ),
    }
    if include_samples:
        document["heart_rate_per_minute"] = (
            list(exercise.heart_rate_per_minute) if exercise.heart_rate_per_minute is not None else None
        )
    document["training_load"] = _serialize_training_load(exercise.training_load)
    document["device"] = exercise.device
    document["running_index"] = exercise.running_index
    document["fat_percentage"] = exercise.fat_percentage
    return document


def _serialize_exercises_document(
    exercises: Sequence[Exercise], date_range: DateRange, *, include_samples: bool
) -> dict[str, Any]:
    return {
        "schema_version": _EXERCISES_SCHEMA_VERSION,
        "date_range": _serialize_date_range(date_range),
        "exercise_count": len(exercises),
        "exercises": [
            _serialize_exercise(exercise, include_samples=include_samples)
            for exercise in sorted(exercises, key=lambda exercise: exercise.start_time)
        ],
    }


def _serialize_sport_summary(summary: SportSummary) -> dict[str, Any]:
    return {
        "sport": summary.sport,
        "session_count": summary.session_count,
        "total_duration_seconds": summary.total_duration_seconds,
        "total_calories": summary.total_calories,
    }


def _serialize_profile(profile: UserProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "birthdate": profile.birthdate.isoformat() if profile.birthdate is not None else None,
        "gender": profile.gender,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
    }


def _serialize_manifest(manifest: ExerciseManifest) -> dict[str, Any]:
    return {
        "tool_name": manifest.tool_name,
        "tool_version": manifest.tool_version,
        "generated_at": manifest.generated_at.isoformat(),
        "date_range": _serialize_date_range(manifest.date_range),
        "availability": manifest.availability.value,
        "exercise_count": manifest.exercise_count,
        "total_duration_seconds": manifest.total_duration_seconds,
        "total_calories": manifest.total_calories,
        "sports": [_serialize_sport_summary(summary) for summary in manifest.sports],
        "profile": _serialize_profile(manifest.profile),
        "history_window_warning": manifest.history_window_warning,
    }


def _render_sports_table(sports: Sequence[SportSummary]) -> str:
    if not sports:
        return "None — no session in this export matched a known sport."
    rows = "\n".join(
        f"| {summary.sport} | {summary.session_count} | {summary.total_duration_seconds:.1f} | "
        f"{summary.total_calories} |"
        for summary in sports
    )
    return f"| Sport | Sessions | Total duration (s) | Total calories |\n|---|---|---|---|\n{rows}"


def _render_load_interpretation_table() -> str:
    rows = "\n".join(
        f"| `{member.value}` | {member.name.replace('_', ' ').title()} |" for member in LoadInterpretation
    )
    return f"| Value | Meaning |\n|---|---|\n{rows}"


def _render_profile_note(profile: UserProfile | None) -> str:
    if profile is None:
        return (
            "No profile is in the local store yet — it is fetched and cached alongside the exercise "
            "data on sync, so this block stays unavailable until a sync has completed at least once."
        )
    birthdate = profile.birthdate.isoformat() if profile.birthdate is not None else "unknown"
    height = f"{profile.height_cm} cm" if profile.height_cm is not None else "unknown"
    weight = f"{profile.weight_kg} kg" if profile.weight_kg is not None else "unknown"
    return f"- Birthdate: {birthdate}\n- Gender: {profile.gender or 'unknown'}\n- Height: {height}\n- Weight: {weight}"


def _render_samples_note(*, include_samples: bool) -> str:
    if include_samples:
        return (
            "This archive **includes** `heart_rate_per_minute` on every session: one averaged bpm "
            "value per minute, starting at `start_time`."
        )
    return (
        "This archive was built **without** per-minute heart-rate samples: `heart_rate_per_minute` "
        "is absent from every session entirely, not `null`."
    )


def _render_readme(manifest: ExerciseManifest, *, include_samples: bool) -> str:
    history_window_note = (
        manifest.history_window_warning
        or "The full requested range is within Polar's 30-day exercise retention window."
    )
    return Template(_README_TEMPLATE).substitute(
        TOOL_NAME=manifest.tool_name,
        TOOL_VERSION=manifest.tool_version,
        GENERATED_AT=manifest.generated_at.isoformat(),
        DATE_MIN=manifest.date_range.date_min.isoformat(),
        DATE_MAX=manifest.date_range.date_max.isoformat(),
        EXERCISE_COUNT=str(manifest.exercise_count),
        TOTAL_DURATION_SECONDS=f"{manifest.total_duration_seconds:.1f}",
        TOTAL_CALORIES=str(manifest.total_calories),
        AVAILABILITY=manifest.availability.value,
        HISTORY_WINDOW_NOTE=history_window_note,
        SPORTS_TABLE=_render_sports_table(manifest.sports),
        LOAD_INTERPRETATION_TABLE=_render_load_interpretation_table(),
        PROFILE_NOTE=_render_profile_note(manifest.profile),
        SAMPLES_NOTE=_render_samples_note(include_samples=include_samples),
    )
