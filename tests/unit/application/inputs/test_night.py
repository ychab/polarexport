from datetime import date
from pathlib import Path

from pydantic import ValidationError

import pytest

from polarexport.application.inputs.night import NightExportInput
from polarexport.application.inputs.night import NightSyncInput
from polarexport.domain.enums import NightSource
from polarexport.domain.value_objects.date_range import DateRange


class TestNightSyncInput:
    @pytest.fixture
    def date_range(self) -> DateRange:
        return DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 27))

    def test__defaults(self, date_range: DateRange) -> None:
        sync_in = NightSyncInput(date_range=date_range)

        assert sync_in.sources == frozenset(NightSource)
        assert sync_in.force_refresh is False
        assert sync_in.limit is None

    def test__empty_sources_rejected(self, date_range: DateRange) -> None:
        with pytest.raises(ValidationError):
            NightSyncInput(date_range=date_range, sources=frozenset())

    def test__limit_zero_rejected(self, date_range: DateRange) -> None:
        with pytest.raises(ValidationError):
            NightSyncInput(date_range=date_range, limit=0)


class TestNightExportInput:
    @pytest.fixture
    def date_range(self) -> DateRange:
        return DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 27))

    def test__defaults(self, date_range: DateRange) -> None:
        export_in = NightExportInput(date_range=date_range, output_dir=Path("export"))

        assert export_in.sources == frozenset(NightSource)
        assert export_in.include_raw is True
        assert export_in.force is False
        assert export_in.limit is None

    def test__empty_sources_rejected(self, date_range: DateRange) -> None:
        with pytest.raises(ValidationError):
            NightExportInput(date_range=date_range, output_dir=Path("export"), sources=frozenset())

    def test__limit_zero_rejected(self, date_range: DateRange) -> None:
        with pytest.raises(ValidationError):
            NightExportInput(date_range=date_range, output_dir=Path("export"), limit=0)
