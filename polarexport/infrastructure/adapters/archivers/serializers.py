from collections.abc import Mapping
from collections.abc import Sequence
from datetime import date
from datetime import datetime
from importlib import resources
from string import Template
from typing import Any

from polarexport.domain.entities.export import ExportManifest
from polarexport.domain.entities.heart_rate import ContinuousHeartRate
from polarexport.domain.entities.night import Night
from polarexport.domain.entities.recharge import NightlyRecharge
from polarexport.domain.entities.skin_temperature import SkinTemperature
from polarexport.domain.entities.sleep import Sleep
from polarexport.domain.entities.sleepwise import SleepWise
from polarexport.domain.enums import ContinuityClass
from polarexport.domain.enums import NightlyRechargeStatus
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SleepStage
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.date_range import DateRange
from polarexport.domain.value_objects.sleep_stages import SleepStages

_NIGHTS_SCHEMA_VERSION = 1

_README_TEMPLATE = (
    resources.files("polarexport.infrastructure.adapters.archivers.templates")
    .joinpath("README.md")
    .read_text(encoding="utf-8")
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _serialize_date_range(date_range: DateRange) -> dict[str, str]:
    return {
        "date_min": date_range.date_min.isoformat(),
        "date_max": date_range.date_max.isoformat(),
    }


def _serialize_manifest(manifest: ExportManifest) -> dict[str, Any]:
    return {
        "tool_name": manifest.tool_name,
        "tool_version": manifest.tool_version,
        "generated_at": manifest.generated_at.isoformat(),
        "date_range": _serialize_date_range(manifest.date_range),
        "night_count": manifest.night_count,
        "sources_requested": [source.value for source in manifest.sources_requested],
        "source_availability": {
            source.value: availability.value for source, availability in manifest.source_availability.items()
        },
        "gaps": [day.isoformat() for day in manifest.gaps],
        "history_window_warning": manifest.history_window_warning,
    }


def _serialize_sleep_stages(stages: SleepStages | None) -> dict[str, int] | None:
    if stages is None:
        return None
    return {
        "light_seconds": stages.light_seconds,
        "deep_seconds": stages.deep_seconds,
        "rem_seconds": stages.rem_seconds,
        "unrecognized_seconds": stages.unrecognized_seconds,
    }


def _serialize_sleep(sleep: Sleep | None) -> dict[str, Any] | None:
    if sleep is None:
        return None
    return {
        "sleep_start_time": _iso(sleep.sleep_start_time),
        "sleep_end_time": _iso(sleep.sleep_end_time),
        "stages": _serialize_sleep_stages(sleep.stages),
        "continuity": sleep.continuity,
        "continuity_class": sleep.continuity_class.value if sleep.continuity_class is not None else None,
        "short_interruption_duration": sleep.short_interruption_duration,
        "long_interruption_duration": sleep.long_interruption_duration,
        "total_interruption_duration": sleep.total_interruption_duration,
        "sleep_score": sleep.sleep_score,
        "sleep_charge": sleep.sleep_charge,
        "sleep_goal": sleep.sleep_goal,
        "sleep_rating": sleep.sleep_rating,
        "sleep_cycles": sleep.sleep_cycles,
        "group_duration_score": sleep.group_duration_score,
        "group_solidity_score": sleep.group_solidity_score,
        "group_regeneration_score": sleep.group_regeneration_score,
        "hypnogram": sleep.hypnogram,
        "device_id": sleep.device_id,
    }


def _serialize_recharge(recharge: NightlyRecharge | None) -> dict[str, Any] | None:
    if recharge is None:
        return None
    return {
        "nightly_recharge_status": (
            recharge.nightly_recharge_status.value if recharge.nightly_recharge_status is not None else None
        ),
        "ans_charge": recharge.ans_charge,
        "ans_charge_status": recharge.ans_charge_status,
        "heart_rate_avg": recharge.heart_rate_avg,
        "heart_rate_variability_avg": recharge.heart_rate_variability_avg,
        "beat_to_beat_avg": recharge.beat_to_beat_avg,
        "breathing_rate_avg": recharge.breathing_rate_avg,
    }


def _serialize_skin_temperature(skin_temperature: SkinTemperature | None) -> dict[str, Any] | None:
    if skin_temperature is None:
        return None
    return {
        "sleep_start": _iso(skin_temperature.sleep_start),
        "sleep_end": _iso(skin_temperature.sleep_end),
        "samples": [{"time": _iso(time), "deviation": deviation} for time, deviation in skin_temperature.samples],
        "deviation": skin_temperature.deviation,
    }


def _serialize_sleepwise(sleepwise: SleepWise | None) -> dict[str, Any] | None:
    if sleepwise is None:
        return None
    return {
        "alertness_hourly": [
            {"hour": hour, "alertness_level": alertness_level} for hour, alertness_level in sleepwise.alertness_hourly
        ],
        "sleep_time": _iso(sleepwise.sleep_time),
        "wake_time": _iso(sleepwise.wake_time),
        "bedtime_window_start": _iso(sleepwise.bedtime_window_start),
        "bedtime_window_end": _iso(sleepwise.bedtime_window_end),
    }


def _serialize_heart_rate(heart_rate: ContinuousHeartRate | None) -> dict[str, Any] | None:
    if heart_rate is None:
        return None
    return {
        "samples": [
            {"time": _iso(time), "heart_rate": heart_rate_value} for time, heart_rate_value in heart_rate.samples
        ],
    }


def _serialize_night(night: Night) -> dict[str, Any]:
    return {
        "date": night.date.isoformat(),
        "sleep": _serialize_sleep(night.sleep),
        "recharge": _serialize_recharge(night.recharge),
        "skin_temperature": _serialize_skin_temperature(night.skin_temperature),
        "sleepwise": _serialize_sleepwise(night.sleepwise),
        "heart_rate": _serialize_heart_rate(night.heart_rate),
    }


def _serialize_nights_document(nights: Sequence[Night], date_range: DateRange) -> dict[str, Any]:
    return {
        "schema_version": _NIGHTS_SCHEMA_VERSION,
        "date_range": _serialize_date_range(date_range),
        "night_count": len(nights),
        "nights": [_serialize_night(night) for night in sorted(nights, key=lambda night: night.date)],
    }


def _render_source_availability_table(source_availability: Mapping[NightSource, SourceAvailability]) -> str:
    rows = "\n".join(
        f"| `{source.value}` | `{source_availability[source].value}` |"
        for source in NightSource
        if source in source_availability
    )
    return f"| Source | Availability |\n|---|---|\n{rows}"


def _render_gaps_list(gaps: Sequence[date]) -> str:
    if not gaps:
        return "None — every requested date has at least one source of data."
    return "\n".join(f"- {day.isoformat()}" for day in sorted(gaps))


def _render_continuity_class_table() -> str:
    rows = "\n".join(f"| {member.value} | {member.label} |" for member in ContinuityClass)
    return f"| Value | Meaning |\n|---|---|\n{rows}"


def _render_nightly_recharge_status_table() -> str:
    rows = "\n".join(f"| {member.value} | {member.label} |" for member in NightlyRechargeStatus)
    return f"| Value | Meaning |\n|---|---|\n{rows}"


def _render_hypnogram_table() -> str:
    rows = "\n".join(f"| {stage.value} | {stage.name.replace('_', ' ').title()} |" for stage in SleepStage)
    return f"| Code | Stage |\n|---|---|\n{rows}"


def _render_readme(manifest: ExportManifest) -> str:
    history_window_note = (
        manifest.history_window_warning or "The full requested range is within Polar's 28-day retention window."
    )
    return Template(_README_TEMPLATE).substitute(
        TOOL_NAME=manifest.tool_name,
        TOOL_VERSION=manifest.tool_version,
        GENERATED_AT=manifest.generated_at.isoformat(),
        DATE_MIN=manifest.date_range.date_min.isoformat(),
        DATE_MAX=manifest.date_range.date_max.isoformat(),
        NIGHT_COUNT=str(manifest.night_count),
        SOURCE_AVAILABILITY_TABLE=_render_source_availability_table(manifest.source_availability),
        HISTORY_WINDOW_NOTE=history_window_note,
        GAPS_LIST=_render_gaps_list(manifest.gaps),
        CONTINUITY_CLASS_TABLE=_render_continuity_class_table(),
        NIGHTLY_RECHARGE_STATUS_TABLE=_render_nightly_recharge_status_table(),
        HYPNOGRAM_TABLE=_render_hypnogram_table(),
    )
