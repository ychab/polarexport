import logging
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from pydantic import ValidationError

from polarexport.application.ports.mappers.exercise import ExerciseMapperPort
from polarexport.application.ports.mappers.night import NightMapperPort
from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.heart_rate import ContinuousHeartRate
from polarexport.domain.entities.profile import UserProfile
from polarexport.domain.entities.recharge import NightlyRecharge
from polarexport.domain.entities.skin_temperature import SkinTemperature
from polarexport.domain.entities.sleep import Sleep
from polarexport.domain.entities.sleepwise import SleepWise
from polarexport.domain.enums import ContinuityClass
from polarexport.domain.enums import LoadInterpretation
from polarexport.domain.enums import NightlyRechargeStatus
from polarexport.domain.enums import SampleType
from polarexport.domain.services.exercise_metrics import downsample_per_minute
from polarexport.domain.services.exercise_metrics import heart_rate_stats
from polarexport.domain.services.exercise_metrics import parse_sample_series
from polarexport.domain.utils.durations import parse_iso_duration
from polarexport.domain.value_objects.alertness_hour import AlertnessHour
from polarexport.domain.value_objects.heart_rate_stats import HeartRateStats
from polarexport.domain.value_objects.heart_rate_zone import HeartRateZone
from polarexport.domain.value_objects.sleep_stages import SleepStages
from polarexport.domain.value_objects.speed_stats import SpeedStats
from polarexport.domain.value_objects.training_load import TrainingLoad
from polarexport.infrastructure.adapters.providers.polar.schemas import AlertnessDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import CircadianBedtimeDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import ContinuousHeartRateDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import ExerciseDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import ExerciseSampleDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import HeartRateZoneDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import NightlyRechargeDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import SkinTemperatureDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import SleepDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import TrainingLoadProDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import UserProfileDTO

logger = logging.getLogger(__name__)


class PolarNightMapper(NightMapperPort):
    """Maps raw Polar AccessLink v3 payloads to domain entities.

    Stateless — no I/O, no settings. Instantiate anywhere.
    """

    def to_sleep(self, payload: Mapping[str, Any]) -> Sleep:
        return _sleep_dto_to_entity(SleepDTO.model_validate(payload))

    def to_nightly_recharge(self, payload: Mapping[str, Any]) -> NightlyRecharge:
        return _nightly_recharge_dto_to_entity(NightlyRechargeDTO.model_validate(payload))

    def to_skin_temperature(self, payload: Mapping[str, Any]) -> SkinTemperature:
        return _skin_temperature_dto_to_entity(SkinTemperatureDTO.model_validate(payload))

    def to_sleepwise(self, payload: Mapping[str, Any]) -> SleepWise:
        alertness_raw = payload.get("alertness")
        circadian_raw = payload.get("circadian_bedtime")
        return _sleepwise_dto_to_entity(
            day=date.fromisoformat(payload["date"]),
            alertness=AlertnessDTO.model_validate(alertness_raw) if alertness_raw else None,
            circadian=CircadianBedtimeDTO.model_validate(circadian_raw) if circadian_raw else None,
        )

    def to_continuous_heart_rate(self, payload: Mapping[str, Any]) -> ContinuousHeartRate:
        return _continuous_heart_rate_dto_to_entity(ContinuousHeartRateDTO.model_validate(payload))


def _sleep_dto_to_entity(dto: SleepDTO) -> Sleep:
    stages: SleepStages | None = None
    if None not in (dto.light_sleep, dto.deep_sleep, dto.rem_sleep, dto.unrecognized_sleep_stage):
        stages = SleepStages(
            light_seconds=dto.light_sleep,  # type: ignore[arg-type]
            deep_seconds=dto.deep_sleep,  # type: ignore[arg-type]
            rem_seconds=dto.rem_sleep,  # type: ignore[arg-type]
            unrecognized_seconds=dto.unrecognized_sleep_stage,  # type: ignore[arg-type]
        )

    return Sleep(
        date=dto.date,
        sleep_start_time=dto.sleep_start_time,
        sleep_end_time=dto.sleep_end_time,
        stages=stages,
        continuity=dto.continuity,
        continuity_class=ContinuityClass(dto.continuity_class) if dto.continuity_class is not None else None,
        short_interruption_duration=dto.short_interruption_duration,
        long_interruption_duration=dto.long_interruption_duration,
        total_interruption_duration=dto.total_interruption_duration,
        sleep_score=dto.sleep_score,
        sleep_charge=dto.sleep_charge,
        sleep_goal=dto.sleep_goal,
        sleep_rating=dto.sleep_rating,
        sleep_cycles=dto.sleep_cycles,
        group_duration_score=dto.group_duration_score,
        group_solidity_score=dto.group_solidity_score,
        group_regeneration_score=dto.group_regeneration_score,
        hypnogram=dto.hypnogram,
        heart_rate_samples=dto.heart_rate_samples,
        device_id=dto.device_id,
    )


def _nightly_recharge_dto_to_entity(dto: NightlyRechargeDTO) -> NightlyRecharge:
    return NightlyRecharge(
        date=dto.date,
        nightly_recharge_status=(
            NightlyRechargeStatus(dto.nightly_recharge_status) if dto.nightly_recharge_status is not None else None
        ),
        ans_charge=dto.ans_charge,
        ans_charge_status=dto.ans_charge_status,
        heart_rate_avg=dto.heart_rate_avg,
        heart_rate_variability_avg=dto.heart_rate_variability_avg,
        beat_to_beat_avg=dto.beat_to_beat_avg,
        breathing_rate_avg=dto.breathing_rate_avg,
        hrv_samples=dto.hrv_samples,
        breathing_samples=dto.breathing_samples,
    )


def _skin_temperature_dto_to_entity(dto: SkinTemperatureDTO) -> SkinTemperature:
    return SkinTemperature(
        date=dto.sleep_date,
        celsius=dto.sleep_time_skin_temperature_celsius,
        deviation=dto.deviation_from_baseline_celsius,
    )


def _sleepwise_dto_to_entity(
    day: date,
    alertness: AlertnessDTO | None,
    circadian: CircadianBedtimeDTO | None,
) -> SleepWise:
    alertness_hourly = tuple(
        AlertnessHour(
            start_time=hour.start_time,
            end_time=hour.end_time,
            alertness_level=hour.alertness_level,
            validity=hour.validity,
        )
        for hour in (alertness.hourly_data if alertness else [])
        if hour.alertness_level is not None
    )

    return SleepWise(
        date=day,
        alertness_hourly=alertness_hourly,
        sleep_time=alertness.sleep_period_start_time if alertness else None,
        wake_time=alertness.sleep_period_end_time if alertness else None,
        bedtime_window_start=circadian.sleep_gate_start_time if circadian else None,
        bedtime_window_end=circadian.sleep_gate_end_time if circadian else None,
        grade=alertness.grade if alertness else None,
        grade_type=alertness.grade_type if alertness else None,
        grade_classification=alertness.grade_classification if alertness else None,
        grade_validity_seconds=alertness.grade_validity_seconds if alertness else None,
        validity=alertness.validity if alertness else None,
        sleep_inertia=alertness.sleep_inertia if alertness else None,
        sleep_type=alertness.sleep_type if alertness else None,
        result_type=alertness.result_type if alertness else None,
        period_start_time=alertness.period_start_time if alertness else None,
        period_end_time=alertness.period_end_time if alertness else None,
        sleep_timezone_offset_minutes=alertness.sleep_timezone_offset_minutes if alertness else None,
        circadian_validity=circadian.validity if circadian else None,
        circadian_quality=circadian.quality if circadian else None,
        preferred_sleep_period_start_time=circadian.preferred_sleep_period_start_time if circadian else None,
        preferred_sleep_period_end_time=circadian.preferred_sleep_period_end_time if circadian else None,
    )


def _continuous_heart_rate_dto_to_entity(dto: ContinuousHeartRateDTO) -> ContinuousHeartRate:
    samples = tuple(
        (datetime.combine(dto.date, datetime.strptime(sample.sample_time, "%H:%M:%S").time()), sample.heart_rate)
        for sample in dto.heart_rate_samples
    )
    return ContinuousHeartRate(date=dto.date, samples=samples)


class PolarExerciseMapper(ExerciseMapperPort):
    """Maps raw Polar AccessLink v3 exercise/profile payloads to domain entities.

    Stateless — no I/O, no settings. Instantiate anywhere.
    """

    def to_exercises(self, payloads: Mapping[str, Mapping[str, Any]]) -> tuple[Exercise, ...]:
        exercises: list[Exercise] = []
        for exercise_id, payload in payloads.items():
            try:
                dto = ExerciseDTO.model_validate(payload)
                exercises.append(_exercise_dto_to_entity(dto))
            except (ValidationError, ValueError):
                logger.warning("Failed to map Polar exercise", extra={"exercise_id": exercise_id})
                continue
        return tuple(exercises)

    def to_profile(self, payload: Mapping[str, Any]) -> UserProfile | None:
        try:
            dto = UserProfileDTO.model_validate(payload)
        except ValidationError:
            logger.warning("Failed to map Polar user profile")
            return None
        return UserProfile(
            user_id=str(dto.polar_user_id),
            birthdate=dto.birthdate,
            gender=dto.gender,
            height_cm=dto.height,
            weight_kg=dto.weight,
        )


def _exercise_dto_to_entity(dto: ExerciseDTO) -> Exercise:
    start_time, local_date = _local_start_time(dto)
    samples_by_type = _samples_by_type(dto.samples)

    heart_rate_sample = samples_by_type.get(SampleType.HEART_RATE)
    heart_rate: HeartRateStats | None = None
    heart_rate_per_minute: tuple[int | None, ...] | None = None
    if heart_rate_sample is not None:
        series = parse_sample_series(heart_rate_sample.data)
        heart_rate = heart_rate_stats(
            series,
            api_average=dto.heart_rate.average if dto.heart_rate else None,
            api_maximum=dto.heart_rate.maximum if dto.heart_rate else None,
        )
        heart_rate_per_minute = downsample_per_minute(series, recording_rate_seconds=heart_rate_sample.recording_rate)
    elif dto.heart_rate is not None:
        heart_rate = HeartRateStats(average=dto.heart_rate.average, maximum=dto.heart_rate.maximum, minimum=None)

    speed_sample = samples_by_type.get(SampleType.SPEED)
    speed = _speed_stats_from_samples(parse_sample_series(speed_sample.data)) if speed_sample is not None else None

    return Exercise(
        id=dto.id,
        start_time=start_time,
        date=local_date,
        upload_time=dto.upload_time,
        duration_seconds=parse_iso_duration(dto.duration) if dto.duration is not None else None,
        sport=dto.sport,
        detailed_sport_info=dto.detailed_sport_info,
        device=dto.device,
        device_id=dto.device_id,
        calories=dto.calories,
        distance_meters=dto.distance,
        heart_rate=heart_rate,
        heart_rate_zones=_heart_rate_zones(dto.heart_rate_zones),
        heart_rate_per_minute=heart_rate_per_minute,
        speed=speed,
        training_load=_training_load(dto.training_load_pro),
        running_index=dto.running_index,
        fat_percentage=dto.fat_percentage,
        carbohydrate_percentage=dto.carbohydrate_percentage,
        protein_percentage=dto.protein_percentage,
        has_route=dto.has_route,
    )


def _local_start_time(dto: ExerciseDTO) -> tuple[datetime, date]:
    # A missing offset is treated as UTC rather than dropping the session: the wall-clock time is
    # still meaningful even if its local reading isn't, and one missing field must not lose a workout.
    if dto.start_time_utc_offset is None:
        logger.warning(
            "Exercise missing start_time_utc_offset; treating start_time as UTC", extra={"exercise_id": dto.id}
        )
        aware_start_time = dto.start_time.replace(tzinfo=UTC)
    else:
        aware_start_time = dto.start_time.replace(tzinfo=timezone(timedelta(minutes=dto.start_time_utc_offset)))
    return aware_start_time, aware_start_time.date()


def _samples_by_type(samples: list[ExerciseSampleDTO] | None) -> dict[int, ExerciseSampleDTO]:
    if not samples:
        return {}
    return {sample.sample_type: sample for sample in samples}


def _speed_stats_from_samples(samples: Sequence[float | None]) -> SpeedStats | None:
    """Build `SpeedStats` from the type-1 sample series.

    Units were confirmed against the phase-23 live capture's one outdoor session: the sample series
    average (~4.36) matches `distance / duration` (~4.23 km/h) directly, whereas multiplying by 3.6 for
    an assumed m/s series would give ~15.7 km/h — an impossible pace for that walk. Every indoor session
    in the same capture carries an all-zero type-1 series (Polar still returns the field, just empty),
    so a series with no positive value is treated as absent rather than a real "0 km/h" measurement.

    The minimum is taken over positive samples only, matching `heart_rate_stats`: a 0 km/h sample is a
    pause, a traffic light or a GPS dropout, not a genuine minimum speed, and shipping it as
    `minimum_kmh` would be actively misleading. The average stays over every present sample, including
    zeros, so it remains comparable to `average_speed_kmh`.
    """
    present = [sample for sample in samples if sample is not None]
    positive = [sample for sample in present if sample > 0]
    if not positive:
        return None
    return SpeedStats(
        average_kmh=round(sum(present) / len(present), 4),
        maximum_kmh=round(max(positive), 4),
        minimum_kmh=round(min(positive), 4),
    )


def _heart_rate_zones(dtos: list[HeartRateZoneDTO] | None) -> tuple[HeartRateZone, ...] | None:
    if dtos is None:
        return None
    zones = []
    for zone_dto in dtos:
        seconds = parse_iso_duration(zone_dto.in_zone) if zone_dto.in_zone is not None else None
        zones.append(
            HeartRateZone(
                index=zone_dto.index,
                lower_limit=zone_dto.lower_limit,
                upper_limit=zone_dto.upper_limit,
                seconds=round(seconds) if seconds is not None else None,
            )
        )
    return tuple(zones)


def _training_load(dto: TrainingLoadProDTO | None) -> TrainingLoad | None:
    if dto is None:
        return None
    cardio_value, cardio_interpretation = _load_value(dto.cardio_load, dto.cardio_load_interpretation)
    muscle_value, muscle_interpretation = _load_value(dto.muscle_load, dto.muscle_load_interpretation)
    perceived_value, perceived_interpretation = _load_value(dto.perceived_load, dto.perceived_load_interpretation)
    return TrainingLoad(
        cardio_load=cardio_value,
        cardio_load_interpretation=cardio_interpretation,
        muscle_load=muscle_value,
        muscle_load_interpretation=muscle_interpretation,
        perceived_load=perceived_value,
        perceived_load_interpretation=perceived_interpretation,
        user_rpe=dto.user_rpe,
    )


def _load_value(value: float | None, interpretation: str | None) -> tuple[float | None, LoadInterpretation | None]:
    if interpretation is None:
        return value, None
    try:
        parsed_interpretation = LoadInterpretation(interpretation)
    except ValueError:
        logger.warning("Unknown Polar load interpretation", extra={"interpretation": interpretation})
        return None, None
    if parsed_interpretation is LoadInterpretation.NOT_AVAILABLE:
        # -1.0 (muscle) and 0.0 (perceived) are sentinels, not real values — the interpretation is the
        # only reliable signal that this figure was never measured.
        return None, None
    return value, parsed_interpretation
