from tests.unit.factories.entities.exercise_export import ExerciseExportReportFactory
from tests.unit.factories.entities.exercise_export import ExerciseManifestFactory
from tests.unit.factories.entities.exercise_export import SportSummaryFactory


class TestSportSummary:
    def test__fields(self) -> None:
        summary = SportSummaryFactory.build(session_count=3, total_calories=2000)
        assert summary.session_count == 3
        assert summary.total_calories == 2000


class TestExerciseManifest:
    def test__fields(self) -> None:
        manifest = ExerciseManifestFactory.build(exercise_count=3)
        assert manifest.exercise_count == 3

    def test__defaults(self) -> None:
        manifest = ExerciseManifestFactory.build(sports=(), profile=None, history_window_warning=None)
        assert manifest.sports == ()
        assert manifest.profile is None
        assert manifest.history_window_warning is None


class TestExerciseExportReport:
    def test__fields(self) -> None:
        report = ExerciseExportReportFactory.build()
        assert report.manifest is not None
        assert report.exercises == ()
