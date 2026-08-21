from datetime import date
from pathlib import Path

from pydantic import ValidationError

import pytest

from polarexport.application.inputs.exercise import ExerciseExportInput
from polarexport.application.inputs.exercise import ExerciseSyncInput
from polarexport.domain.value_objects.date_range import DateRange


class TestExerciseSyncInput:
    def test__defaults(self) -> None:
        sync_in = ExerciseSyncInput()

        assert sync_in.with_samples is True
        assert sync_in.with_zones is True
        assert sync_in.force_refresh is False


class TestExerciseExportInput:
    @pytest.fixture
    def date_range(self) -> DateRange:
        return DateRange(date_min=date(2026, 7, 20), date_max=date(2026, 7, 27))

    def test__defaults(self, date_range: DateRange) -> None:
        export_in = ExerciseExportInput(date_range=date_range, output_dir=Path("export"))

        assert export_in.sports == frozenset()
        assert export_in.include_raw is True
        assert export_in.include_samples is True
        assert export_in.force is False
        assert export_in.limit is None

    def test__limit_zero_rejected(self, date_range: DateRange) -> None:
        with pytest.raises(ValidationError):
            ExerciseExportInput(date_range=date_range, output_dir=Path("export"), limit=0)
