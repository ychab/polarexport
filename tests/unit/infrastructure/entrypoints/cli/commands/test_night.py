from collections.abc import AsyncIterator
from collections.abc import Iterable
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Final
from unittest import mock

import httpx

import pytest
import time_machine
import typer
from typer.testing import CliRunner

from polarexport.domain.enums import NightSource
from polarexport.domain.exceptions import ArchiveAlreadyExistsError
from polarexport.domain.exceptions import NoNightDataError
from polarexport.infrastructure.entrypoints.cli.commands.night import night_logic
from polarexport.infrastructure.entrypoints.cli.commands.night import parse_sources
from polarexport.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.export import ExportManifestFactory
from tests.unit.factories.entities.export import ExportReportFactory
from tests.unit.factories.entities.sync import SourceSyncStatFactory
from tests.unit.factories.entities.sync import SyncReportFactory
from tests.unit.factories.inputs.night import NightExportInputFactory
from tests.unit.factories.inputs.night import NightSyncInputFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://www.polaraccesslink.com/v3/users/sleep/2026-08-15")
    response = httpx.Response(status_code=status_code, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


class TestNightParserCommand:
    def test__parse_sources__valid(self) -> None:
        assert parse_sources(["sleep", "recharge"]) == ["sleep", "recharge"]

    def test__parse_sources__invalid(self) -> None:
        with pytest.raises(typer.BadParameter, match="Invalid source: 'nope'"):
            parse_sources(["nope"])

    def test__parse_sources__all_shorthand(self) -> None:
        assert parse_sources(["all"]) == [source.value for source in NightSource]

    def test__parse_sources__none_defaults_to_all(self) -> None:
        assert parse_sources(None) == [source.value for source in NightSource]

    @pytest.fixture(autouse=True)
    def mock_night_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "polarexport.infrastructure.entrypoints.cli.commands.night.night_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            patched.return_value = (None, ExportReportFactory.build())
            yield patched

    def test__source__invalid__surfaces_bad_parameter(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["night", "--no-refresh", "--source", "not-a-source"])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert "Invalid value for '--source'" in output
        assert "Invalid source: 'not-a-source'" in output


class TestNightCommand:
    @pytest.fixture(autouse=True)
    def mock_night_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "polarexport.infrastructure.entrypoints.cli.commands.night.night_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            patched.return_value = (None, ExportReportFactory.build())
            yield patched

    def test__nominal(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["night", "--no-refresh"])

        assert result.exit_code == 0
        mock_night_logic.assert_awaited_once()

    def test__default_dates_resolved_from_today(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        with time_machine.travel(datetime(2026, 8, 18, 12, 0, tzinfo=UTC)):
            result = runner.invoke(app, ["night", "--no-refresh"])

        assert result.exit_code == 0
        _sync_in, export_in = mock_night_logic.call_args.args
        assert export_in.date_range.date_min == date(2026, 7, 22)
        assert export_in.date_range.date_max == date(2026, 8, 18)

    def test__explicit_dates(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            ["night", "--no-refresh", "--date-min", "2026-08-01", "--date-max", "2026-08-05"],
        )
        # fmt: on

        assert result.exit_code == 0
        _sync_in, export_in = mock_night_logic.call_args.args
        assert export_in.date_range.date_min == date(2026, 8, 1)
        assert export_in.date_range.date_max == date(2026, 8, 5)

    def test__source__subset(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            ["night", "--no-refresh", "--source", "sleep", "--source", "recharge"],
        )
        # fmt: on

        assert result.exit_code == 0
        _sync_in, export_in = mock_night_logic.call_args.args
        assert export_in.sources == frozenset({NightSource.SLEEP, NightSource.RECHARGE})

    def test__refresh__sync_input_built(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["night", "--force-refresh"])

        assert result.exit_code == 0
        sync_in, _export_in = mock_night_logic.call_args.args
        assert sync_in is not None
        assert sync_in.force_refresh is True

    def test__no_refresh__sync_input_is_none(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["night", "--no-refresh"])

        assert result.exit_code == 0
        sync_in, _export_in = mock_night_logic.call_args.args
        assert sync_in is None

    def test__no_refresh_and_force_refresh__rejected(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["night", "--no-refresh", "--force-refresh"])

        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "--force-refresh cannot be combined with --no-refresh" in output

    def test__no_raw(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["night", "--no-refresh", "--no-raw"])

        assert result.exit_code == 0
        _sync_in, export_in = mock_night_logic.call_args.args
        assert export_in.include_raw is False

    def test__output_dir(self, mock_night_logic: mock.AsyncMock, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(app, ["night", "--no-refresh", "--output-dir", str(tmp_path)])

        assert result.exit_code == 0
        _sync_in, export_in = mock_night_logic.call_args.args
        assert export_in.output_dir == tmp_path

    def test__force(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["night", "--no-refresh", "--force"])

        assert result.exit_code == 0
        _sync_in, export_in = mock_night_logic.call_args.args
        assert export_in.force is True

    def test__limit(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["night", "--no-refresh", "--limit", "3"])

        assert result.exit_code == 0
        _sync_in, export_in = mock_night_logic.call_args.args
        assert export_in.limit == 3

    def test__history_window_warning__printed_yellow(
        self, mock_night_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        manifest = ExportManifestFactory.build(history_window_warning="outside the retention window")
        mock_night_logic.return_value = (None, ExportReportFactory.build(manifest=manifest))

        result = runner.invoke(app, ["night", "--no-refresh"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert "outside the retention window" in output

    def test__sync_report_present__sync_table_printed(
        self, mock_night_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        sync_report = SyncReportFactory.build(stats={NightSource.SLEEP: SourceSyncStatFactory.build()})
        mock_night_logic.return_value = (sync_report, ExportReportFactory.build())

        result = runner.invoke(app, ["night"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert "Sync" in output
        assert "sleep" in output

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
        mock_night_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        archive_size_bytes: int,
        expected: str,
    ) -> None:
        export_report = ExportReportFactory.build(archive_size_bytes=archive_size_bytes)
        mock_night_logic.return_value = (None, export_report)

        result = runner.invoke(app, ["night", "--no-refresh"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert expected in output

    def test__invalid_date_range__exit_1(
        self, mock_night_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            ["night", "--no-refresh", "--date-min", "2026-08-10", "--date-max", "2026-08-01"],
        )
        # fmt: on

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "must not be after" in output
        mock_night_logic.assert_not_awaited()

    def test__no_night_data__exit_1(
        self, mock_night_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_night_logic.side_effect = NoNightDataError("No night data found for 2026-08-01 to 2026-08-05")

        result = runner.invoke(app, ["night"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "No night data found" in output
        assert "try again without --no-refresh" not in output

    def test__no_night_data__no_refresh__hints_offline_store_empty(
        self, mock_night_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_night_logic.side_effect = NoNightDataError("No night data found for 2026-08-01 to 2026-08-05")

        result = runner.invoke(app, ["night", "--no-refresh"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "try again without --no-refresh" in output

    def test__archive_already_exists__exit_1(
        self, mock_night_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_night_logic.side_effect = ArchiveAlreadyExistsError("Archive already exists: export/foo.zip")

        result = runner.invoke(app, ["night", "--no-refresh"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "Archive already exists" in output

    def test__unauthorized__actionable_message__token_not_echoed(
        self, mock_night_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_night_logic.side_effect = _http_status_error(httpx.codes.UNAUTHORIZED)

        result = runner.invoke(app, ["night"])

        assert result.exit_code == 1
        output = clean_typer_text(result.output)
        assert "Authentication failed (401" in output
        assert "docs/authentication.md" in output
        assert "dummy-access-token" not in output

    def test__other_http_status_error__propagates(self, mock_night_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_night_logic.side_effect = _http_status_error(httpx.codes.INTERNAL_SERVER_ERROR)

        result = runner.invoke(app, ["night"])

        assert result.exit_code != 0
        assert isinstance(result.exception, httpx.HTTPStatusError)


@pytest.mark.usefixtures("mock_get_night_store", "mock_get_night_mapper", "mock_get_night_archiver")
class TestNightLogic:
    TARGET_PATH: Final[str] = "polarexport.infrastructure.entrypoints.cli.commands.night"

    @pytest.fixture
    def today(self) -> date:
        return date(2026, 8, 17)

    @pytest.fixture
    def generated_at(self) -> datetime:
        return datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

    @pytest.fixture
    def mock_get_polar_client(self) -> Iterable[mock.Mock]:
        client = mock.AsyncMock()

        @asynccontextmanager
        async def _get_polar_client() -> AsyncIterator[mock.AsyncMock]:
            yield client

        with mock.patch(f"{self.TARGET_PATH}.get_polar_client", side_effect=_get_polar_client) as patched:
            yield patched

    @pytest.fixture
    def mock_get_night_store(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.get_night_store", return_value=mock.Mock()) as patched:
            yield patched

    @pytest.fixture
    def mock_get_night_mapper(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.get_night_mapper", return_value=mock.Mock()) as patched:
            yield patched

    @pytest.fixture
    def mock_get_night_archiver(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.get_night_archiver", return_value=mock.Mock()) as patched:
            yield patched

    @pytest.fixture
    def mock_night_sync_use_case(self) -> Iterable[mock.Mock]:
        instance = mock.Mock()
        instance.sync = mock.AsyncMock(return_value=SyncReportFactory.build())
        with mock.patch(f"{self.TARGET_PATH}.NightSyncUseCase", return_value=instance) as patched:
            yield patched

    @pytest.fixture
    def mock_night_export_use_case(self) -> Iterable[mock.Mock]:
        instance = mock.Mock()
        instance.export = mock.AsyncMock(return_value=ExportReportFactory.build())
        with mock.patch(f"{self.TARGET_PATH}.NightExportUseCase", return_value=instance) as patched:
            yield patched

    async def test__sync_in_none__polar_client_never_constructed(
        self,
        mock_get_polar_client: mock.AsyncMock,
        mock_night_export_use_case: mock.Mock,
        today: date,
        generated_at: datetime,
    ) -> None:
        export_in = NightExportInputFactory.build()

        sync_report, export_report = await night_logic(None, export_in, today=today, generated_at=generated_at)

        assert sync_report is None
        assert export_report is mock_night_export_use_case.return_value.export.return_value
        mock_get_polar_client.assert_not_called()

    async def test__sync_in_provided__both_use_cases_awaited_once(
        self,
        mock_get_polar_client: mock.AsyncMock,
        mock_night_sync_use_case: mock.Mock,
        mock_night_export_use_case: mock.Mock,
        today: date,
        generated_at: datetime,
    ) -> None:
        sync_in = NightSyncInputFactory.build()
        export_in = NightExportInputFactory.build()

        sync_report, export_report = await night_logic(sync_in, export_in, today=today, generated_at=generated_at)

        mock_get_polar_client.assert_called_once()
        sync_instance = mock_night_sync_use_case.return_value
        sync_instance.sync.assert_awaited_once_with(sync_in, today=today)
        export_instance = mock_night_export_use_case.return_value
        export_instance.export.assert_awaited_once_with(export_in, today=today, generated_at=generated_at)
        assert sync_report is sync_instance.sync.return_value
        assert export_report is export_instance.export.return_value
