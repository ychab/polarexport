import logging
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

from polarexport.application.ports.stores.night import StoredPayload
from polarexport.application.use_cases.night_export import NightExportUseCase
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability
from polarexport.domain.exceptions import ArchiveAlreadyExistsError
from polarexport.domain.exceptions import NoNightDataError
from polarexport.domain.value_objects.date_range import DateRange

from tests.unit.factories.entities.recharge import NightlyRechargeFactory
from tests.unit.factories.entities.sleep import SleepFactory
from tests.unit.factories.inputs.night import NightExportInputFactory


class TestNightExportUseCase:
    @pytest.fixture
    def today(self) -> date:
        return date(2026, 8, 17)

    @pytest.fixture
    def generated_at(self) -> datetime:
        return datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

    @pytest.fixture
    def day(self) -> date:
        return date(2026, 8, 10)

    @pytest.fixture
    def date_range(self, day: date) -> DateRange:
        return DateRange(date_min=day, date_max=day)

    @pytest.fixture
    def archive_path(self, tmp_path: Path) -> Path:
        path = tmp_path / "polarexport-nights-2026-08-10_2026-08-10.zip"
        path.write_bytes(b"archive-content")
        return path

    @pytest.fixture
    def use_case(
        self,
        mock_night_store: mock.AsyncMock,
        mock_night_mapper: mock.Mock,
        mock_night_archiver: mock.AsyncMock,
    ) -> NightExportUseCase:
        return NightExportUseCase(
            night_store=mock_night_store,
            night_mapper=mock_night_mapper,
            night_archiver=mock_night_archiver,
        )

    def _stored_payload(self, source: NightSource, day: date, payload: dict[str, object] | None) -> StoredPayload:
        return StoredPayload(
            source=source, date=day, fetched_at=datetime(2026, 8, 10, tzinfo=UTC), api="test", payload=payload
        )

    async def test__all_sources_present__merged_and_archived(
        self,
        use_case: NightExportUseCase,
        mock_night_store: mock.AsyncMock,
        mock_night_mapper: mock.Mock,
        mock_night_archiver: mock.AsyncMock,
        date_range: DateRange,
        day: date,
        today: date,
        generated_at: datetime,
        archive_path: Path,
        tmp_path: Path,
    ) -> None:
        stored_by_source = {
            NightSource.SLEEP: {day: self._stored_payload(NightSource.SLEEP, day, {"raw": "sleep"})},
            NightSource.RECHARGE: {day: self._stored_payload(NightSource.RECHARGE, day, {"raw": "recharge"})},
        }
        mock_night_store.read.side_effect = lambda source, _date_range: stored_by_source.get(source, {})
        sleep = SleepFactory.build(date=day)
        recharge = NightlyRechargeFactory.build(date=day)
        mock_night_mapper.to_sleep.return_value = sleep
        mock_night_mapper.to_nightly_recharge.return_value = recharge
        mock_night_archiver.write.return_value = archive_path
        export_in = NightExportInputFactory.build(
            date_range=date_range,
            sources=frozenset({NightSource.SLEEP, NightSource.RECHARGE}),
            output_dir=tmp_path,
        )

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.night_count == 1
        assert report.nights[0].sleep is sleep
        assert report.nights[0].recharge is recharge
        assert report.archive_path == archive_path
        assert report.archive_size_bytes == archive_path.stat().st_size
        assert report.manifest.source_availability[NightSource.SLEEP] == SourceAvailability.AVAILABLE
        assert report.manifest.source_availability[NightSource.SKIN_TEMPERATURE] == SourceAvailability.NOT_REQUESTED
        call_kwargs = mock_night_archiver.write.call_args.kwargs
        assert call_kwargs["output_dir"] == export_in.output_dir
        assert call_kwargs["include_raw"] == export_in.include_raw
        assert call_kwargs["force"] == export_in.force

    async def test__requested_source_with_no_stored_payloads__reported_no_data(
        self,
        use_case: NightExportUseCase,
        mock_night_store: mock.AsyncMock,
        mock_night_mapper: mock.Mock,
        mock_night_archiver: mock.AsyncMock,
        date_range: DateRange,
        day: date,
        today: date,
        generated_at: datetime,
        archive_path: Path,
        tmp_path: Path,
    ) -> None:
        stored_by_source = {
            NightSource.SLEEP: {day: self._stored_payload(NightSource.SLEEP, day, {"raw": "sleep"})},
        }
        mock_night_store.read.side_effect = lambda source, _date_range: stored_by_source.get(source, {})
        mock_night_mapper.to_sleep.return_value = SleepFactory.build(date=day)
        mock_night_archiver.write.return_value = archive_path
        export_in = NightExportInputFactory.build(
            date_range=date_range,
            sources=frozenset({NightSource.SLEEP, NightSource.RECHARGE}),
            output_dir=tmp_path,
        )

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.source_availability[NightSource.SLEEP] == SourceAvailability.AVAILABLE
        assert report.manifest.source_availability[NightSource.RECHARGE] == SourceAvailability.NO_DATA

    async def test__store_empty_for_every_date__raises_no_night_data(
        self,
        use_case: NightExportUseCase,
        mock_night_store: mock.AsyncMock,
        mock_night_archiver: mock.AsyncMock,
        date_range: DateRange,
        today: date,
        generated_at: datetime,
        tmp_path: Path,
    ) -> None:
        mock_night_store.read.return_value = {}
        export_in = NightExportInputFactory.build(date_range=date_range, output_dir=tmp_path)

        with pytest.raises(NoNightDataError):
            await use_case.export(export_in, today=today, generated_at=generated_at)

        mock_night_archiver.write.assert_not_awaited()

    async def test__one_payload_fails_to_map__error_logged_night_still_exported(
        self,
        use_case: NightExportUseCase,
        mock_night_store: mock.AsyncMock,
        mock_night_mapper: mock.Mock,
        mock_night_archiver: mock.AsyncMock,
        date_range: DateRange,
        day: date,
        today: date,
        generated_at: datetime,
        archive_path: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        stored_by_source = {
            NightSource.SLEEP: {day: self._stored_payload(NightSource.SLEEP, day, {"raw": "bad-sleep"})},
            NightSource.RECHARGE: {day: self._stored_payload(NightSource.RECHARGE, day, {"raw": "recharge"})},
        }
        mock_night_store.read.side_effect = lambda source, _date_range: stored_by_source.get(source, {})
        mock_night_mapper.to_sleep.side_effect = ValueError("malformed sleep payload")
        recharge = NightlyRechargeFactory.build(date=day)
        mock_night_mapper.to_nightly_recharge.return_value = recharge
        mock_night_archiver.write.return_value = archive_path
        export_in = NightExportInputFactory.build(
            date_range=date_range,
            sources=frozenset({NightSource.SLEEP, NightSource.RECHARGE}),
            output_dir=tmp_path,
        )

        with caplog.at_level(logging.WARNING):
            report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.night_count == 1
        assert report.nights[0].sleep is None
        assert report.nights[0].recharge is recharge
        # logger.exception -> ERROR level, and the traceback is what carries the mapping failure detail.
        mapping_failures = [record for record in caplog.records if record.levelno == logging.ERROR]
        assert len(mapping_failures) == 1
        assert mapping_failures[0].exc_info is not None

    async def test__archive_already_exists__propagates_unchanged(
        self,
        use_case: NightExportUseCase,
        mock_night_store: mock.AsyncMock,
        mock_night_mapper: mock.Mock,
        mock_night_archiver: mock.AsyncMock,
        date_range: DateRange,
        day: date,
        today: date,
        generated_at: datetime,
        tmp_path: Path,
    ) -> None:
        mock_night_store.read.return_value = {day: self._stored_payload(NightSource.SLEEP, day, {"raw": "sleep"})}
        mock_night_mapper.to_sleep.return_value = SleepFactory.build(date=day)
        mock_night_archiver.write.side_effect = ArchiveAlreadyExistsError("archive exists")
        export_in = NightExportInputFactory.build(
            date_range=date_range, sources=frozenset({NightSource.SLEEP}), output_dir=tmp_path
        )

        with pytest.raises(ArchiveAlreadyExistsError):
            await use_case.export(export_in, today=today, generated_at=generated_at)

    async def test__stored_payload_none__skipped_without_mapping(
        self,
        use_case: NightExportUseCase,
        mock_night_store: mock.AsyncMock,
        mock_night_mapper: mock.Mock,
        mock_night_archiver: mock.AsyncMock,
        date_range: DateRange,
        day: date,
        today: date,
        generated_at: datetime,
        archive_path: Path,
        tmp_path: Path,
    ) -> None:
        stored_by_source = {
            NightSource.SLEEP: {day: self._stored_payload(NightSource.SLEEP, day, None)},
            NightSource.RECHARGE: {day: self._stored_payload(NightSource.RECHARGE, day, {"raw": "recharge"})},
        }
        mock_night_store.read.side_effect = lambda source, _date_range: stored_by_source.get(source, {})
        recharge = NightlyRechargeFactory.build(date=day)
        mock_night_mapper.to_nightly_recharge.return_value = recharge
        mock_night_archiver.write.return_value = archive_path
        export_in = NightExportInputFactory.build(
            date_range=date_range,
            sources=frozenset({NightSource.SLEEP, NightSource.RECHARGE}),
            output_dir=tmp_path,
        )

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        mock_night_mapper.to_sleep.assert_not_called()
        assert report.nights[0].sleep is None
        assert report.nights[0].recharge is recharge

    async def test__date_min_outside_window__manifest_has_warning(
        self,
        use_case: NightExportUseCase,
        mock_night_store: mock.AsyncMock,
        mock_night_mapper: mock.Mock,
        mock_night_archiver: mock.AsyncMock,
        day: date,
        today: date,
        generated_at: datetime,
        archive_path: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        old_day = date(2026, 7, 1)
        date_range = DateRange(date_min=old_day, date_max=old_day)
        mock_night_store.read.return_value = {
            old_day: self._stored_payload(NightSource.SLEEP, old_day, {"raw": "sleep"})
        }
        mock_night_mapper.to_sleep.return_value = SleepFactory.build(date=old_day)
        mock_night_archiver.write.return_value = archive_path
        export_in = NightExportInputFactory.build(
            date_range=date_range, sources=frozenset({NightSource.SLEEP}), output_dir=tmp_path
        )

        with caplog.at_level(logging.WARNING):
            report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.history_window_warning is not None
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    async def test__include_raw_false__passed_through_to_archiver(
        self,
        use_case: NightExportUseCase,
        mock_night_store: mock.AsyncMock,
        mock_night_mapper: mock.Mock,
        mock_night_archiver: mock.AsyncMock,
        date_range: DateRange,
        day: date,
        today: date,
        generated_at: datetime,
        archive_path: Path,
        tmp_path: Path,
    ) -> None:
        mock_night_store.read.return_value = {day: self._stored_payload(NightSource.SLEEP, day, {"raw": "sleep"})}
        mock_night_mapper.to_sleep.return_value = SleepFactory.build(date=day)
        mock_night_archiver.write.return_value = archive_path
        export_in = NightExportInputFactory.build(
            date_range=date_range, sources=frozenset({NightSource.SLEEP}), output_dir=tmp_path, include_raw=False
        )

        await use_case.export(export_in, today=today, generated_at=generated_at)

        assert mock_night_archiver.write.call_args.kwargs["include_raw"] is False

    @pytest.fixture
    def five_day_range(self) -> DateRange:
        return DateRange(date_min=date(2026, 8, 10), date_max=date(2026, 8, 14))

    @pytest.fixture
    def sleep_on_three_days(self, mock_night_store: mock.AsyncMock, mock_night_mapper: mock.Mock) -> None:
        # Sleep on the 11th, 12th and 14th; the 10th and 13th are gaps.
        days = (date(2026, 8, 11), date(2026, 8, 12), date(2026, 8, 14))
        stored = {day: self._stored_payload(NightSource.SLEEP, day, {"day": day.isoformat()}) for day in days}
        mock_night_store.read.side_effect = lambda source, _range: stored if source == NightSource.SLEEP else {}
        mock_night_mapper.to_sleep.side_effect = lambda payload: SleepFactory.build(
            date=date.fromisoformat(str(payload["day"]))
        )

    async def test__limit_below_night_count__keeps_most_recent_and_drops_earlier_gaps(
        self,
        use_case: NightExportUseCase,
        sleep_on_three_days: None,
        mock_night_archiver: mock.AsyncMock,
        five_day_range: DateRange,
        today: date,
        generated_at: datetime,
        archive_path: Path,
        tmp_path: Path,
    ) -> None:
        mock_night_archiver.write.return_value = archive_path
        export_in = NightExportInputFactory.build(
            date_range=five_day_range,
            sources=frozenset({NightSource.SLEEP}),
            output_dir=tmp_path,
            limit=2,
        )

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert [night.date for night in report.nights] == [date(2026, 8, 12), date(2026, 8, 14)]
        assert report.manifest.night_count == 2
        # The 10th falls before the retained window and is no longer a gap of this export; the 13th still is.
        assert report.manifest.gaps == (date(2026, 8, 13),)

    async def test__limit_above_night_count__exports_every_night(
        self,
        use_case: NightExportUseCase,
        sleep_on_three_days: None,
        mock_night_archiver: mock.AsyncMock,
        five_day_range: DateRange,
        today: date,
        generated_at: datetime,
        archive_path: Path,
        tmp_path: Path,
    ) -> None:
        mock_night_archiver.write.return_value = archive_path
        export_in = NightExportInputFactory.build(
            date_range=five_day_range,
            sources=frozenset({NightSource.SLEEP}),
            output_dir=tmp_path,
            limit=99,
        )

        report = await use_case.export(export_in, today=today, generated_at=generated_at)

        assert report.manifest.night_count == 3
        assert report.manifest.gaps == (date(2026, 8, 10), date(2026, 8, 13))
