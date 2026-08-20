from datetime import UTC
from datetime import date
from datetime import datetime

from polarexport.domain.entities.night import Night
from polarexport.domain.entities.sleep import Sleep
from polarexport.domain.enums import ContinuityClass
from polarexport.domain.enums import NightlyRechargeStatus
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.value_objects.alertness_hour import AlertnessHour
from polarexport.domain.value_objects.sleep_stages import SleepStages
from polarexport.infrastructure.adapters.archivers.serializers import _iso
from polarexport.infrastructure.adapters.archivers.serializers import _render_continuity_class_table
from polarexport.infrastructure.adapters.archivers.serializers import _render_gaps_list
from polarexport.infrastructure.adapters.archivers.serializers import _render_hypnogram_table
from polarexport.infrastructure.adapters.archivers.serializers import _render_nightly_recharge_status_table
from polarexport.infrastructure.adapters.archivers.serializers import _render_readme
from polarexport.infrastructure.adapters.archivers.serializers import _render_source_availability_table
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_alertness_hour
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_heart_rate
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_manifest
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_night
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_nights_document
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_recharge
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_skin_temperature
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_sleep
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_sleep_stages
from polarexport.infrastructure.adapters.archivers.serializers import _serialize_sleepwise

from tests.unit.factories.entities.export import ExportManifestFactory
from tests.unit.factories.entities.heart_rate import ContinuousHeartRateFactory
from tests.unit.factories.entities.recharge import NightlyRechargeFactory
from tests.unit.factories.entities.skin_temperature import SkinTemperatureFactory
from tests.unit.factories.entities.sleep import SleepFactory
from tests.unit.factories.entities.sleepwise import SleepWiseFactory
from tests.unit.factories.value_objects.date_range import DateRangeFactory


class TestIso:
    def test__none__returns_none(self) -> None:
        assert _iso(None) is None

    def test__value__returns_isoformat(self) -> None:
        value = datetime(2026, 7, 20, 23, 0, tzinfo=UTC)
        assert _iso(value) == value.isoformat()


class TestSerializeSleepStages:
    def test__none__returns_none(self) -> None:
        assert _serialize_sleep_stages(None) is None

    def test__stages__returns_dict(self) -> None:
        stages = SleepStages(light_seconds=1, deep_seconds=2, rem_seconds=3, unrecognized_seconds=4)
        assert _serialize_sleep_stages(stages) == {
            "light_seconds": 1,
            "deep_seconds": 2,
            "rem_seconds": 3,
            "unrecognized_seconds": 4,
        }


class TestSerializeSleep:
    def test__none__returns_none(self) -> None:
        assert _serialize_sleep(None) is None

    def test__with_continuity_class__serializes_value(self) -> None:
        sleep = SleepFactory.build(date=date(2026, 7, 20), continuity_class=ContinuityClass.VERY_CONTINUOUS)
        result = _serialize_sleep(sleep)
        assert result is not None
        assert result["continuity_class"] == ContinuityClass.VERY_CONTINUOUS.value

    def test__without_continuity_class__serializes_none(self) -> None:
        sleep = SleepFactory.build(date=date(2026, 7, 20), continuity_class=None)
        result = _serialize_sleep(sleep)
        assert result is not None
        assert result["continuity_class"] is None

    def test__with_stages_and_timing__serializes_efficiency_percent(self) -> None:
        sleep = SleepFactory.build(
            date=date(2026, 7, 20),
            stages=SleepStages(light_seconds=500, deep_seconds=0, rem_seconds=0, unrecognized_seconds=500),
            sleep_start_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            sleep_end_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC).replace(minute=16, second=40),
        )
        result = _serialize_sleep(sleep)
        assert result is not None
        assert result["efficiency_percent"] == 50.0

    def test__without_stages__serializes_efficiency_percent_as_none(self) -> None:
        sleep = Sleep(date=date(2026, 7, 20), stages=None)
        result = _serialize_sleep(sleep)
        assert result is not None
        assert result["efficiency_percent"] is None


class TestSerializeRecharge:
    def test__none__returns_none(self) -> None:
        assert _serialize_recharge(None) is None

    def test__with_status__serializes_value(self) -> None:
        recharge = NightlyRechargeFactory.build(
            date=date(2026, 7, 20), nightly_recharge_status=NightlyRechargeStatus.GOOD
        )
        result = _serialize_recharge(recharge)
        assert result is not None
        assert result["nightly_recharge_status"] == NightlyRechargeStatus.GOOD.value

    def test__without_status__serializes_none(self) -> None:
        recharge = NightlyRechargeFactory.build(date=date(2026, 7, 20), nightly_recharge_status=None)
        result = _serialize_recharge(recharge)
        assert result is not None
        assert result["nightly_recharge_status"] is None


class TestSerializeSkinTemperature:
    def test__none__returns_none(self) -> None:
        assert _serialize_skin_temperature(None) is None

    def test__with_values__serializes_celsius_and_deviation(self) -> None:
        skin_temperature = SkinTemperatureFactory.build(date=date(2026, 7, 20), celsius=33.8, deviation=-0.5)
        result = _serialize_skin_temperature(skin_temperature)
        assert result == {"celsius": 33.8, "deviation": -0.5}


class TestSerializeAlertnessHour:
    def test__serializes_all_fields(self) -> None:
        hour = AlertnessHour(
            start_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            end_time=datetime(2026, 7, 21, 0, 0, tzinfo=UTC),
            alertness_level="ALERTNESS_LEVEL_HIGH",
            validity="VALIDITY_VALID",
        )
        assert _serialize_alertness_hour(hour) == {
            "start_time": hour.start_time.isoformat(),
            "end_time": hour.end_time.isoformat() if hour.end_time is not None else None,
            "alertness_level": "ALERTNESS_LEVEL_HIGH",
            "validity": "VALIDITY_VALID",
        }


class TestSerializeSleepwise:
    def test__none__returns_none(self) -> None:
        assert _serialize_sleepwise(None) is None

    def test__with_alertness_hourly__serializes_entries(self) -> None:
        hour = AlertnessHour(
            start_time=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            alertness_level="ALERTNESS_LEVEL_HIGH",
        )
        sleepwise = SleepWiseFactory.build(date=date(2026, 7, 20), alertness_hourly=(hour,), grade=7.4)
        result = _serialize_sleepwise(sleepwise)
        assert result is not None
        assert result["alertness_hourly"] == [_serialize_alertness_hour(hour)]
        assert result["grade"] == 7.4


class TestSerializeHeartRate:
    def test__none__returns_none(self) -> None:
        assert _serialize_heart_rate(None) is None

    def test__with_samples__serializes_samples(self) -> None:
        sample = (datetime(2026, 7, 20, 23, 0, tzinfo=UTC), 55)
        heart_rate = ContinuousHeartRateFactory.build(date=date(2026, 7, 20), samples=(sample,))
        result = _serialize_heart_rate(heart_rate)
        assert result is not None
        assert result["samples"] == [{"time": sample[0].isoformat(), "heart_rate": 55}]


class TestSerializeNight:
    def test__all_sources_absent__nulls_everywhere(self) -> None:
        night = Night(date=date(2026, 7, 20))

        result = _serialize_night(night)

        assert result["date"] == "2026-07-20"
        assert result["sleep"] is None
        assert result["recharge"] is None
        assert result["skin_temperature"] is None
        assert result["sleepwise"] is None
        assert result["heart_rate"] is None


class TestSerializeNightsDocument:
    def test__sorts_nights_ascending_by_date(self) -> None:
        date_range = DateRangeFactory.build(date_min=date(2026, 7, 19), date_max=date(2026, 7, 21))
        later = Night(date=date(2026, 7, 21))
        earlier = Night(date=date(2026, 7, 19))

        document = _serialize_nights_document([later, earlier], date_range)

        assert [night["date"] for night in document["nights"]] == ["2026-07-19", "2026-07-21"]
        assert document["night_count"] == 2
        assert document["date_range"] == {"date_min": "2026-07-19", "date_max": "2026-07-21"}


class TestSerializeManifest:
    def test__serializes_enum_members_to_their_values(self) -> None:
        manifest = ExportManifestFactory.build(
            sources_requested=(NightSource.SLEEP,),
            source_availability={NightSource.SLEEP: SourceAvailability.AVAILABLE},
            gaps=(date(2026, 7, 22),),
        )

        result = _serialize_manifest(manifest)

        assert result["sources_requested"] == ["sleep"]
        assert result["source_availability"] == {"sleep": "available"}
        assert result["gaps"] == ["2026-07-22"]


class TestRenderSourceAvailabilityTable:
    def test__only_lists_requested_sources__in_enum_order(self) -> None:
        table = _render_source_availability_table({NightSource.SLEEP: SourceAvailability.AVAILABLE})

        assert "`sleep`" in table
        assert "`recharge`" not in table


class TestRenderGapsList:
    def test__no_gaps__returns_none_message(self) -> None:
        assert _render_gaps_list(()) == "None — every requested date has at least one source of data."

    def test__with_gaps__lists_sorted_dates(self) -> None:
        result = _render_gaps_list([date(2026, 7, 22), date(2026, 7, 20)])
        assert result == "- 2026-07-20\n- 2026-07-22"


class TestRenderScaleTables:
    def test__continuity_class_table__lists_every_member(self) -> None:
        table = _render_continuity_class_table()
        for member in ContinuityClass:
            assert member.label in table

    def test__nightly_recharge_status_table__lists_every_member(self) -> None:
        table = _render_nightly_recharge_status_table()
        for member in NightlyRechargeStatus:
            assert member.label in table

    def test__hypnogram_table__lists_every_stage_code(self) -> None:
        table = _render_hypnogram_table()
        assert "| 0 | Wake |" in table
        assert "| 5 | Unknown |" in table


class TestRenderReadme:
    def test__with_history_window_warning__includes_it(self) -> None:
        manifest = ExportManifestFactory.build(history_window_warning="date_min is outside the retention window")

        readme = _render_readme(manifest)

        assert "date_min is outside the retention window" in readme

    def test__without_history_window_warning__includes_default_note(self) -> None:
        manifest = ExportManifestFactory.build(history_window_warning=None)

        readme = _render_readme(manifest)

        assert "within Polar's 28-day retention window" in readme
