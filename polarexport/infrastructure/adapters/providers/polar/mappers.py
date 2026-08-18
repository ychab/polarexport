from collections.abc import Mapping
from datetime import date
from datetime import datetime
from typing import Any

from polarexport.application.ports.mappers.night import NightMapperPort
from polarexport.domain.entities.heart_rate import ContinuousHeartRate
from polarexport.domain.entities.recharge import NightlyRecharge
from polarexport.domain.entities.skin_temperature import SkinTemperature
from polarexport.domain.entities.sleep import Sleep
from polarexport.domain.entities.sleepwise import SleepWise
from polarexport.domain.enums import ContinuityClass
from polarexport.domain.enums import NightlyRechargeStatus
from polarexport.domain.value_objects.sleep_stages import SleepStages
from polarexport.infrastructure.adapters.providers.polar.schemas import AlertnessDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import CircadianBedtimeDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import ContinuousHeartRateDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import NightlyRechargeDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import SkinTemperatureDTO
from polarexport.infrastructure.adapters.providers.polar.schemas import SleepDTO


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
    )


def _skin_temperature_dto_to_entity(dto: SkinTemperatureDTO) -> SkinTemperature:
    return SkinTemperature(
        date=dto.sleep_date,
        deviation=dto.deviation_from_baseline_celsius,
    )


def _sleepwise_dto_to_entity(
    day: date,
    alertness: AlertnessDTO | None,
    circadian: CircadianBedtimeDTO | None,
) -> SleepWise:
    # The domain SleepWise entity predates a live SleepWise payload (this account has no supported
    # device) and models an hourly (hour, label) view rather than Polar's richer hourly_data objects.
    # Best-effort projection until the entity is revisited with real data.
    alertness_hourly = tuple(
        (hour.start_time.hour, hour.alertness_level)
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
    )


def _continuous_heart_rate_dto_to_entity(dto: ContinuousHeartRateDTO) -> ContinuousHeartRate:
    samples = tuple(
        (datetime.combine(dto.date, datetime.strptime(sample.sample_time, "%H:%M:%S").time()), sample.heart_rate)
        for sample in dto.heart_rate_samples
    )
    return ContinuousHeartRate(date=dto.date, samples=samples)
