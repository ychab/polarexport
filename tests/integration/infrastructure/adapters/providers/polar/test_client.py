from datetime import date
from datetime import timedelta

import pytest

from polarexport.domain.enums import LoadInterpretation
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.infrastructure.adapters.providers.polar.client import PolarAccessLinkClient
from polarexport.infrastructure.adapters.providers.polar.mappers import PolarExerciseMapper

from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock
class TestPolarAccessLinkClient:
    async def test__fetch__sleep__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 8, 15)

        result = await polar_client.fetch(NightSource.SLEEP, [day])

        assert result.availability == SourceAvailability.AVAILABLE
        assert result.request_count == 1
        payload = result.payloads[day]
        assert payload is not None
        assert payload["date"] == day.isoformat()
        assert payload["hypnogram"]

    async def test__fetch__nightly_recharge__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 8, 15)

        result = await polar_client.fetch(NightSource.RECHARGE, [day])

        payload = result.payloads[day]
        assert payload is not None
        assert payload["nightly_recharge_status"] == 2

    async def test__fetch__continuous_heart_rate__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 8, 15)

        result = await polar_client.fetch(NightSource.HEART_RATE, [day])

        payload = result.payloads[day]
        assert payload is not None
        assert len(payload["heart_rate_samples"]) == 3

    async def test__fetch__skin_temperature__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2023, 10, 20)

        result = await polar_client.fetch(NightSource.SKIN_TEMPERATURE, [day])

        payload = result.payloads[day]
        assert payload is not None
        assert payload["sleep_date"] == day.isoformat()

    async def test__fetch__sleepwise__happy_path(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2022, 11, 20)

        result = await polar_client.fetch(NightSource.SLEEPWISE, [day])

        payload = result.payloads[day]
        assert payload is not None
        assert payload["alertness"] is not None
        assert payload["circadian_bedtime"] is not None

    async def test__fetch__404__recorded_as_gap(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 1, 1)

        result = await polar_client.fetch(NightSource.SLEEP, [day])

        assert result.payloads == {day: None}
        assert result.availability == SourceAvailability.AVAILABLE

    async def test__fetch__403__source_unavailable(self, polar_client: PolarAccessLinkClient) -> None:
        day = date(2026, 1, 2)

        result = await polar_client.fetch(NightSource.RECHARGE, [day])

        assert result.availability == SourceAvailability.UNAVAILABLE
        assert result.payloads == {}

    async def test__fetch__semaphore_bounds_concurrency__still_issues_all_requests(
        self, polar_client: PolarAccessLinkClient
    ) -> None:
        dates = [date(2026, 8, 1) + timedelta(days=i) for i in range(10)]

        result = await polar_client.fetch(NightSource.HEART_RATE, dates)

        assert result.request_count == 10
        assert len(result.payloads) == 10
        assert set(result.payloads) == set(dates)

    async def test__fetch__sleep__custom_stub_round_trips_verbatim(
        self,
        polar_client: PolarAccessLinkClient,
        polar_wiremock: WireMockContext,
    ) -> None:
        day = date(2026, 3, 1)
        custom_payload = {
            "date": day.isoformat(),
            "polar_user": "https://polaraccesslink.com/v3/users/1",
            "sleep_score": 42,
        }
        polar_wiremock.create_mapping(
            method="GET",
            url_path=f"/v3/users/sleep/{day.isoformat()}",
            status=200,
            json_body=custom_payload,
        )

        result = await polar_client.fetch(NightSource.SLEEP, [day])

        assert result.payloads[day] == custom_payload

    async def test__fetch__heart_rate__custom_stub_status_only__gap(
        self,
        polar_client: PolarAccessLinkClient,
        polar_wiremock: WireMockContext,
    ) -> None:
        day = date(2026, 5, 1)
        polar_wiremock.create_mapping(
            method="GET",
            url_path=f"/v3/users/continuous-heart-rate/{day.isoformat()}",
            status=404,
        )

        result = await polar_client.fetch(NightSource.HEART_RATE, [day])

        assert result.payloads == {day: None}

    async def test__fetch__skin_temperature__query_params_sent_correctly(
        self,
        polar_client: PolarAccessLinkClient,
        polar_wiremock: WireMockContext,
    ) -> None:
        date_min, date_max = date(2026, 4, 1), date(2026, 4, 2)
        polar_wiremock.create_mapping(
            method="GET",
            url_path="/v3/users/biosensing/skintemperature",
            status=200,
            query_params={"from": date_min.isoformat(), "to": date_max.isoformat()},
            json_body=[{"sleep_date": date_min.isoformat(), "deviation_from_baseline_celsius": 1.0}],
        )

        result = await polar_client.fetch(NightSource.SKIN_TEMPERATURE, [date_min, date_max])

        assert result.payloads[date_min] == {
            "sleep_date": date_min.isoformat(),
            "deviation_from_baseline_celsius": 1.0,
        }
        assert result.payloads[date_max] is None

    # -------------------------------------------------------------------------
    # fetch_exercises
    # -------------------------------------------------------------------------

    async def test__fetch_exercises__happy_path__maps_end_to_end(self, polar_client: PolarAccessLinkClient) -> None:
        result = await polar_client.fetch_exercises(with_samples=True, with_zones=True)

        assert result.availability == SourceAvailability.AVAILABLE
        assert result.request_count == 1
        assert len(result.payloads) == 3

        exercises = {exercise.id: exercise for exercise in PolarExerciseMapper().to_exercises(result.payloads)}
        kickboxing = exercises["54klrKbL"]
        assert kickboxing.calories == 786
        assert kickboxing.sport_label == "Kickboxing Martial Arts"
        assert kickboxing.heart_rate is not None
        assert kickboxing.heart_rate.average == 121
        assert kickboxing.heart_rate.maximum == 175
        trimmed_hr_samples = [
            int(value)
            for value in result.payloads["54klrKbL"]["samples"][0]["data"].split(",")
            if value not in ("", "0")
        ]
        assert kickboxing.heart_rate.minimum == min(trimmed_hr_samples)
        assert kickboxing.heart_rate_zones is not None
        assert len(kickboxing.heart_rate_zones) == 5

    async def test__fetch_exercises__outdoor_session__speed_derived_from_samples(
        self, polar_client: PolarAccessLinkClient
    ) -> None:
        result = await polar_client.fetch_exercises(with_samples=True, with_zones=True)

        exercises = {exercise.id: exercise for exercise in PolarExerciseMapper().to_exercises(result.payloads)}
        walk = exercises["PvkgKa3J"]
        assert walk.has_route is True
        assert walk.speed is not None
        assert walk.speed.average_kmh is not None
        assert walk.speed.average_kmh > 0

    async def test__fetch_exercises__indoor_session__speed_none(self, polar_client: PolarAccessLinkClient) -> None:
        result = await polar_client.fetch_exercises(with_samples=True, with_zones=True)

        exercises = {exercise.id: exercise for exercise in PolarExerciseMapper().to_exercises(result.payloads)}
        aerobics = exercises["ymmr1Q46"]
        assert aerobics.has_route is False
        assert aerobics.speed is None

    async def test__fetch_exercises__load_sentinels__mapped_to_none(self, polar_client: PolarAccessLinkClient) -> None:
        result = await polar_client.fetch_exercises(with_samples=True, with_zones=True)

        exercises = {exercise.id: exercise for exercise in PolarExerciseMapper().to_exercises(result.payloads)}
        kickboxing = exercises["54klrKbL"]
        assert kickboxing.training_load is not None
        assert kickboxing.training_load.cardio_load_interpretation is LoadInterpretation.HIGH
        assert kickboxing.training_load.muscle_load is None
        assert kickboxing.training_load.muscle_load_interpretation is None
        assert kickboxing.training_load.perceived_load is None
        assert kickboxing.training_load.perceived_load_interpretation is None

    async def test__fetch_exercises__403__unavailable(self, polar_client: PolarAccessLinkClient) -> None:
        result = await polar_client.fetch_exercises(with_samples=False, with_zones=False)

        assert result.availability == SourceAvailability.UNAVAILABLE
        assert result.payloads == {}

    async def test__fetch_exercises__empty_window__available_no_payloads(
        self,
        polar_client: PolarAccessLinkClient,
        polar_wiremock: WireMockContext,
    ) -> None:
        polar_wiremock.create_mapping(
            method="GET",
            url_path="/v3/exercises",
            status=200,
            json_body=[],
            priority=1,
        )

        result = await polar_client.fetch_exercises(with_samples=True, with_zones=True)

        assert result.availability == SourceAvailability.AVAILABLE
        assert result.payloads == {}

    # -------------------------------------------------------------------------
    # fetch_profile
    # -------------------------------------------------------------------------

    async def test__fetch_profile__happy_path__maps_end_to_end(self, polar_client: PolarAccessLinkClient) -> None:
        payload = await polar_client.fetch_profile()

        assert payload is not None
        profile = PolarExerciseMapper().to_profile(payload)
        assert profile is not None
        assert profile.birthdate is not None
        assert profile.birthdate.isoformat() == "1990-03-15"
        assert profile.age(on=date(2026, 8, 20)) == 36

    async def test__fetch_profile__404__none(
        self,
        polar_client: PolarAccessLinkClient,
        polar_wiremock: WireMockContext,
    ) -> None:
        polar_wiremock.create_mapping(
            method="GET",
            url_path="/v3/users/dummy-user",
            status=404,
            priority=1,
        )

        profile = await polar_client.fetch_profile()

        assert profile is None
