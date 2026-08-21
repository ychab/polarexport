from collections.abc import AsyncIterator
from collections.abc import Iterable
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Final
from unittest import mock

import httpx

import pytest
import time_machine
from typer.testing import CliRunner

from polarexport.domain.exceptions import ArchiveAlreadyExistsError
from polarexport.domain.exceptions import MissingCredentialsError
from polarexport.domain.exceptions import NoExerciseDataError
from polarexport.domain.exceptions import ProviderRateLimitError
from polarexport.infrastructure.entrypoints.cli.commands.exercise import exercise_logic
from polarexport.infrastructure.entrypoints.cli.commands.exercise import parse_sports
from polarexport.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.credentials import StoredCredentialsFactory
from tests.unit.factories.entities.exercise import ExerciseFactory
from tests.unit.factories.entities.exercise_export import ExerciseExportReportFactory
from tests.unit.factories.entities.exercise_export import ExerciseManifestFactory
from tests.unit.factories.entities.exercise_export import ExerciseSyncReportFactory
from tests.unit.factories.entities.exercise_export import SportSummaryFactory
from tests.unit.factories.inputs.exercise import ExerciseExportInputFactory
from tests.unit.factories.inputs.exercise import ExerciseSyncInputFactory
from tests.unit.factories.value_objects.training_load import TrainingLoadFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://www.polaraccesslink.com/v3/exercises")
    response = httpx.Response(status_code=status_code, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


class TestExerciseParserCommand:
    def test__parse_sports__normalizes_hyphen_to_underscore(self) -> None:
        assert parse_sports(["kickboxing-martial-arts"]) == ["KICKBOXING_MARTIAL_ARTS"]

    def test__parse_sports__all_shorthand(self) -> None:
        assert parse_sports(["all"]) == []

    def test__parse_sports__none_defaults_to_no_filter(self) -> None:
        assert parse_sports(None) == []

    @pytest.fixture(autouse=True)
    def mock_exercise_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "polarexport.infrastructure.entrypoints.cli.commands.exercise.exercise_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            patched.return_value = (None, ExerciseExportReportFactory.build())
            yield patched

    def test__date_min__invalid__surfaces_bad_parameter(
        self, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        result = runner.invoke(app, ["exercise", "--no-refresh", "--date-min", "not-a-date"])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert "Invalid value for '--date-min'" in output
        assert "Date must be in YYYY-MM-DD format" in output


class TestExerciseCommand:
    @pytest.fixture(autouse=True)
    def mock_exercise_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "polarexport.infrastructure.entrypoints.cli.commands.exercise.exercise_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            patched.return_value = (None, ExerciseExportReportFactory.build())
            yield patched

    @pytest.fixture(autouse=True)
    def mock_get_credentials_store(self) -> Iterable[mock.Mock]:
        """Defaults to 'no stored credentials' so no test touches the real data/auth/credentials.json."""
        store = mock.Mock()
        store.read = mock.AsyncMock(return_value=None)
        target_path = "polarexport.infrastructure.entrypoints.cli.commands.exercise.get_credentials_store"
        with mock.patch(target_path, return_value=store) as patched:
            yield patched

    def test__nominal(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["exercise", "--no-refresh"])

        assert result.exit_code == 0
        mock_exercise_logic.assert_awaited_once()

    def test__default_dates_resolved_from_today__spans_29_days(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner
    ) -> None:
        with time_machine.travel(datetime(2026, 8, 20, 12, 0, tzinfo=UTC)):
            result = runner.invoke(app, ["exercise", "--no-refresh"])

        assert result.exit_code == 0
        _sync_in, export_in = mock_exercise_logic.call_args.args
        assert export_in.date_range.date_min == date(2026, 7, 22)
        assert export_in.date_range.date_max == date(2026, 8, 20)

    def test__explicit_dates(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            ["exercise", "--no-refresh", "--date-min", "2026-08-01", "--date-max", "2026-08-05"],
        )
        # fmt: on

        assert result.exit_code == 0
        _sync_in, export_in = mock_exercise_logic.call_args.args
        assert export_in.date_range.date_min == date(2026, 8, 1)
        assert export_in.date_range.date_max == date(2026, 8, 5)

    def test__sport__subset(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            ["exercise", "--no-refresh", "--sport", "kickboxing-martial-arts", "--sport", "WALKING"],
        )
        # fmt: on

        assert result.exit_code == 0
        _sync_in, export_in = mock_exercise_logic.call_args.args
        assert export_in.sports == frozenset({"KICKBOXING_MARTIAL_ARTS", "WALKING"})

    def test__sport__all__no_filter(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["exercise", "--no-refresh", "--sport", "all"])

        assert result.exit_code == 0
        _sync_in, export_in = mock_exercise_logic.call_args.args
        assert export_in.sports == frozenset()

    def test__refresh__sync_input_built(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["exercise", "--force-refresh"])

        assert result.exit_code == 0
        sync_in, _export_in = mock_exercise_logic.call_args.args
        assert sync_in is not None
        assert sync_in.force_refresh is True

    def test__no_refresh__sync_input_is_none(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["exercise", "--no-refresh"])

        assert result.exit_code == 0
        sync_in, _export_in = mock_exercise_logic.call_args.args
        assert sync_in is None

    def test__no_refresh_and_force_refresh__rejected(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["exercise", "--no-refresh", "--force-refresh"])

        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "--force-refresh cannot be combined with --no-refresh" in output

    def test__no_raw(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["exercise", "--no-refresh", "--no-raw"])

        assert result.exit_code == 0
        _sync_in, export_in = mock_exercise_logic.call_args.args
        assert export_in.include_raw is False

    def test__no_samples__disables_sync_and_export_samples(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["exercise", "--no-samples"])

        assert result.exit_code == 0
        sync_in, export_in = mock_exercise_logic.call_args.args
        assert sync_in is not None
        assert sync_in.with_samples is False
        assert export_in.include_samples is False

    def test__output_dir(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(app, ["exercise", "--no-refresh", "--output-dir", str(tmp_path)])

        assert result.exit_code == 0
        _sync_in, export_in = mock_exercise_logic.call_args.args
        assert export_in.output_dir == tmp_path

    def test__force(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["exercise", "--no-refresh", "--force"])

        assert result.exit_code == 0
        _sync_in, export_in = mock_exercise_logic.call_args.args
        assert export_in.force is True

    def test__limit(self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["exercise", "--no-refresh", "--limit", "3"])

        assert result.exit_code == 0
        _sync_in, export_in = mock_exercise_logic.call_args.args
        assert export_in.limit == 3

    def test__history_window_warning__printed_yellow(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        manifest = ExerciseManifestFactory.build(history_window_warning="outside the retention window")
        mock_exercise_logic.return_value = (None, ExerciseExportReportFactory.build(manifest=manifest))

        result = runner.invoke(app, ["exercise", "--no-refresh"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert "outside the retention window" in output

    def test__sync_report_present__sync_table_printed(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        sync_report = ExerciseSyncReportFactory.build(fetched=2, profile_fetched=True)
        mock_exercise_logic.return_value = (sync_report, ExerciseExportReportFactory.build())

        result = runner.invoke(app, ["exercise"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert "Sync" in output
        assert "yes" in output

    def test__export_table_printed(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        manifest = ExerciseManifestFactory.build(exercise_count=3, total_duration_seconds=4500.0, total_calories=900)
        mock_exercise_logic.return_value = (None, ExerciseExportReportFactory.build(manifest=manifest))

        result = runner.invoke(app, ["exercise", "--no-refresh"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert "Sessions Exported" in output
        assert "3" in output
        assert "900" in output
        assert "1h 15m" in output

    def test__sport_table__mean_cardio_load_present_and_absent(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        exercise_with_load = ExerciseFactory.build(
            id="with-load",
            detailed_sport_info="KICKBOXING_MARTIAL_ARTS",
            sport=None,
            training_load=TrainingLoadFactory.build(cardio_load=42.0),
        )
        exercise_without_load = ExerciseFactory.build(
            id="without-load", detailed_sport_info="WALKING", sport=None, training_load=None
        )
        sports = (
            SportSummaryFactory.build(sport="Kickboxing Martial Arts", session_count=1, total_calories=500),
            SportSummaryFactory.build(sport="Walking", session_count=1, total_calories=200),
        )
        manifest = ExerciseManifestFactory.build(sports=sports)
        export_report = ExerciseExportReportFactory.build(
            manifest=manifest, exercises=(exercise_with_load, exercise_without_load)
        )
        mock_exercise_logic.return_value = (None, export_report)

        result = runner.invoke(app, ["exercise", "--no-refresh"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert "By Sport" in output
        assert "Kickboxing Martial Arts" in output
        assert "42.0" in output
        assert "Walking" in output
        assert "—" in output

    @pytest.mark.parametrize(
        ("archive_size_bytes", "expected"),
        [
            pytest.param(512, "512 B", id="bytes"),
            pytest.param(2048, "2.0 KB", id="kilobytes"),
            pytest.param(1024**3 * 2, "2.0 GB", id="gigabytes"),
        ],
    )
    def test__archive_size__human_readable(
        self,
        mock_exercise_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        archive_size_bytes: int,
        expected: str,
    ) -> None:
        export_report = ExerciseExportReportFactory.build(archive_size_bytes=archive_size_bytes)
        mock_exercise_logic.return_value = (None, export_report)

        result = runner.invoke(app, ["exercise", "--no-refresh"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert expected in output

    def test__invalid_date_range__exit_1(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            ["exercise", "--no-refresh", "--date-min", "2026-08-10", "--date-max", "2026-08-01"],
        )
        # fmt: on

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "must not be after" in output
        mock_exercise_logic.assert_not_awaited()

    def test__no_exercise_data__exit_1(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_exercise_logic.side_effect = NoExerciseDataError("No exercise data found for 2026-08-01 to 2026-08-05.")

        result = runner.invoke(app, ["exercise"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "No exercise data found" in output
        assert "try again without --no-refresh" not in output

    def test__no_exercise_data__no_refresh__hints_offline_store_empty(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_exercise_logic.side_effect = NoExerciseDataError("No exercise data found for 2026-08-01 to 2026-08-05.")

        result = runner.invoke(app, ["exercise", "--no-refresh"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "try again without --no-refresh" in output

    def test__archive_already_exists__exit_1(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_exercise_logic.side_effect = ArchiveAlreadyExistsError("Archive already exists: export/foo.zip")

        result = runner.invoke(app, ["exercise", "--no-refresh"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "Archive already exists" in output

    def test__missing_credentials__actionable_message__no_traceback(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_exercise_logic.side_effect = MissingCredentialsError("POLAR_ACCESS_TOKEN is not set.")

        result = runner.invoke(app, ["exercise"])

        assert result.exit_code == 1
        assert "Traceback" not in result.output
        output = clean_typer_text(result.stderr)
        assert "No Polar credentials found" in output
        assert "docs/authentication.md" in output

    def test__unauthorized__no_stored_credentials__generic_message__token_not_echoed(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_exercise_logic.side_effect = _http_status_error(httpx.codes.UNAUTHORIZED)

        result = runner.invoke(app, ["exercise"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "Authentication failed (401" in output
        assert "polarexport auth" in output
        assert "docs/authentication.md" in output
        assert "dummy-access-token" not in output

    def test__unauthorized__stored_credentials_not_expired__generic_message(
        self,
        mock_exercise_logic: mock.AsyncMock,
        mock_get_credentials_store: mock.Mock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_exercise_logic.side_effect = _http_status_error(httpx.codes.UNAUTHORIZED)
        obtained_at = datetime.now(UTC)
        mock_get_credentials_store.return_value.read.return_value = StoredCredentialsFactory.build(
            obtained_at=obtained_at, expires_in=473040000
        )

        result = runner.invoke(app, ["exercise"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "Authentication failed (401" in output
        assert "expired" not in output

    def test__unauthorized__stored_credentials_expired__names_expiry_and_auth_command(
        self,
        mock_exercise_logic: mock.AsyncMock,
        mock_get_credentials_store: mock.Mock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_exercise_logic.side_effect = _http_status_error(httpx.codes.UNAUTHORIZED)
        obtained_at = datetime.now(UTC) - timedelta(days=1000)
        mock_get_credentials_store.return_value.read.return_value = StoredCredentialsFactory.build(
            obtained_at=obtained_at, expires_in=100
        )

        result = runner.invoke(app, ["exercise"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "Your Polar token expired on" in output
        assert "polarexport auth" in output
        assert "Authentication failed (401" not in output

    def test__other_http_status_error__actionable_message__no_traceback(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_exercise_logic.side_effect = _http_status_error(httpx.codes.INTERNAL_SERVER_ERROR)

        result = runner.invoke(app, ["exercise"])

        assert result.exit_code == 1
        assert "Traceback" not in result.output
        output = clean_typer_text(result.stderr)
        assert "HTTP 500" in output
        assert "data/raw/" in output

    def test__rate_limited__actionable_message__no_traceback(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_exercise_logic.side_effect = ProviderRateLimitError("Rate limit exceeded for /v3/exercises")

        result = runner.invoke(app, ["exercise"])

        assert result.exit_code == 1
        assert "Traceback" not in result.output
        output = clean_typer_text(result.stderr)
        assert "rate-limited" in output
        assert "data/raw/" in output

    def test__connection_error__actionable_message__no_traceback(
        self, mock_exercise_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_exercise_logic.side_effect = httpx.ConnectError("Connection refused")

        result = runner.invoke(app, ["exercise"])

        assert result.exit_code == 1
        assert "Traceback" not in result.output
        output = clean_typer_text(result.stderr)
        assert "Could not reach Polar" in output
        assert "https://www.polaraccesslink.com" in output
        assert "--no-refresh" in output


@pytest.mark.usefixtures(
    "mock_get_exercise_store", "mock_get_profile_store", "mock_get_exercise_mapper", "mock_get_exercise_archiver"
)
class TestExerciseLogic:
    TARGET_PATH: Final[str] = "polarexport.infrastructure.entrypoints.cli.commands.exercise"

    @pytest.fixture
    def today(self) -> date:
        return date(2026, 8, 20)

    @pytest.fixture
    def generated_at(self) -> datetime:
        return datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

    @pytest.fixture
    def mock_get_polar_client(self) -> Iterable[mock.Mock]:
        client = mock.AsyncMock()

        @asynccontextmanager
        async def _get_polar_client() -> AsyncIterator[mock.AsyncMock]:
            yield client

        with mock.patch(f"{self.TARGET_PATH}.get_polar_client", side_effect=_get_polar_client) as patched:
            yield patched

    @pytest.fixture
    def mock_get_exercise_store(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.get_exercise_store", return_value=mock.Mock()) as patched:
            yield patched

    @pytest.fixture
    def mock_get_profile_store(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.get_profile_store", return_value=mock.Mock()) as patched:
            yield patched

    @pytest.fixture
    def mock_get_exercise_mapper(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.get_exercise_mapper", return_value=mock.Mock()) as patched:
            yield patched

    @pytest.fixture
    def mock_get_exercise_archiver(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.get_exercise_archiver", return_value=mock.Mock()) as patched:
            yield patched

    @pytest.fixture
    def mock_exercise_sync_use_case(self) -> Iterable[mock.Mock]:
        instance = mock.Mock()
        instance.sync = mock.AsyncMock(return_value=ExerciseSyncReportFactory.build())
        with mock.patch(f"{self.TARGET_PATH}.ExerciseSyncUseCase", return_value=instance) as patched:
            yield patched

    @pytest.fixture
    def mock_exercise_export_use_case(self) -> Iterable[mock.Mock]:
        instance = mock.Mock()
        instance.export = mock.AsyncMock(return_value=ExerciseExportReportFactory.build())
        with mock.patch(f"{self.TARGET_PATH}.ExerciseExportUseCase", return_value=instance) as patched:
            yield patched

    async def test__sync_in_none__polar_client_never_constructed(
        self,
        mock_get_polar_client: mock.AsyncMock,
        mock_exercise_export_use_case: mock.Mock,
        today: date,
        generated_at: datetime,
    ) -> None:
        export_in = ExerciseExportInputFactory.build()

        sync_report, export_report = await exercise_logic(None, export_in, today=today, generated_at=generated_at)

        assert sync_report is None
        assert export_report is mock_exercise_export_use_case.return_value.export.return_value
        mock_get_polar_client.assert_not_called()

    async def test__sync_in_provided__both_use_cases_awaited_once(
        self,
        mock_get_polar_client: mock.AsyncMock,
        mock_exercise_sync_use_case: mock.Mock,
        mock_exercise_export_use_case: mock.Mock,
        today: date,
        generated_at: datetime,
    ) -> None:
        sync_in = ExerciseSyncInputFactory.build()
        export_in = ExerciseExportInputFactory.build()

        sync_report, export_report = await exercise_logic(sync_in, export_in, today=today, generated_at=generated_at)

        mock_get_polar_client.assert_called_once()
        sync_instance = mock_exercise_sync_use_case.return_value
        sync_instance.sync.assert_awaited_once_with(sync_in, today=today)
        export_instance = mock_exercise_export_use_case.return_value
        export_instance.export.assert_awaited_once_with(export_in, today=today, generated_at=generated_at)
        assert sync_report is sync_instance.sync.return_value
        assert export_report is export_instance.export.return_value

    async def test__prints_nothing(
        self,
        mock_exercise_export_use_case: mock.Mock,
        today: date,
        generated_at: datetime,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        export_in = ExerciseExportInputFactory.build()

        await exercise_logic(None, export_in, today=today, generated_at=generated_at)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""
