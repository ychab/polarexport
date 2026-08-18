from collections.abc import Iterable
from pathlib import Path
from typing import Final
from unittest import mock

import httpx

from pydantic import HttpUrl

import pytest
from typer.testing import CliRunner

from polarexport.domain.exceptions import AuthorizationDeniedError
from polarexport.domain.exceptions import AuthorizationStateMismatchError
from polarexport.domain.exceptions import AuthorizationTimeoutError
from polarexport.domain.exceptions import CredentialsAlreadyExistError
from polarexport.infrastructure.adapters.providers.polar.auth import PolarOAuthClient
from polarexport.infrastructure.config.settings.polar import polar_settings
from polarexport.infrastructure.entrypoints.cli.commands.auth import auth_logic
from polarexport.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.auth import AuthReportFactory
from tests.unit.factories.inputs.auth import AuthLoginInputFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


def _http_status_error(status_code: int, json_body: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://polarremote.com/v2/oauth2/token")
    response = httpx.Response(status_code=status_code, request=request, json=json_body)
    return httpx.HTTPStatusError("boom", request=request, response=response)


def _http_status_error_non_json_body(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://polarremote.com/v2/oauth2/token")
    response = httpx.Response(status_code=status_code, request=request, text="not json")
    return httpx.HTTPStatusError("boom", request=request, response=response)


@pytest.fixture(autouse=True)
def deterministic_polar_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # A real .env may exist on the developer's machine — pin these explicitly so the tests never
    # depend on (or leak) the developer's own Polar credentials.
    monkeypatch.setattr(polar_settings, "CLIENT_ID", "settings-client-id")
    monkeypatch.setattr(polar_settings, "CLIENT_SECRET", "settings-client-secret")
    monkeypatch.setattr(polar_settings, "REDIRECT_URI", HttpUrl("http://localhost:8000/callback"))


class TestAuthParserCommand:
    @pytest.fixture(autouse=True)
    def mock_auth_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "polarexport.infrastructure.entrypoints.cli.commands.auth.auth_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            patched.return_value = AuthReportFactory.build()
            yield patched

    @pytest.fixture(autouse=True)
    def mock_get_polar_oauth_client(self) -> Iterable[mock.Mock]:
        client = mock.Mock()
        client.authorization_url.return_value = "https://flow.polar.com/oauth2/authorization?state=abc"
        with mock.patch(
            "polarexport.infrastructure.entrypoints.cli.commands.auth.get_polar_oauth_client", return_value=client
        ) as patched:
            yield patched

    @pytest.fixture(autouse=True)
    def mock_webbrowser_open(self) -> Iterable[mock.Mock]:
        with mock.patch("polarexport.infrastructure.entrypoints.cli.commands.auth.webbrowser.open") as patched:
            yield patched

    def test__timeout_below_minimum__rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["auth", "--no-browser", "--timeout", "5"])

        assert result.exit_code != 0


class TestAuthCommand:
    @pytest.fixture(autouse=True)
    def mock_auth_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "polarexport.infrastructure.entrypoints.cli.commands.auth.auth_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            patched.return_value = AuthReportFactory.build(
                user_id="12345678", member_id="yannick", env_path=Path("/home/user/polarexport/.env")
            )
            yield patched

    @pytest.fixture(autouse=True)
    def mock_get_polar_oauth_client(self) -> Iterable[mock.Mock]:
        client = mock.Mock()
        client.authorization_url.return_value = "https://flow.polar.com/oauth2/authorization?state=abc"
        with mock.patch(
            "polarexport.infrastructure.entrypoints.cli.commands.auth.get_polar_oauth_client", return_value=client
        ) as patched:
            yield patched

    @pytest.fixture(autouse=True)
    def mock_webbrowser_open(self) -> Iterable[mock.Mock]:
        with mock.patch("polarexport.infrastructure.entrypoints.cli.commands.auth.webbrowser.open") as patched:
            yield patched

    def test__nominal__success_output(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        result = runner.invoke(app, ["auth", "--member-id", "yannick"])

        assert result.exit_code == 0
        mock_auth_logic.assert_awaited_once()
        output = clean_typer_text(result.output)
        assert "Authorized as Polar user 12345678" in output
        assert "Registered with your application (member-id: yannick)" in output
        assert "Credentials written to /home/user/polarexport/.env" in output
        assert "Next: polarexport night" in output

    def test__default__opens_browser(
        self, mock_webbrowser_open: mock.Mock, runner: CliRunner, mock_get_polar_oauth_client: mock.Mock
    ) -> None:
        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 0
        mock_webbrowser_open.assert_called_once()
        opened_url = mock_webbrowser_open.call_args.args[0]
        assert opened_url == mock_get_polar_oauth_client.return_value.authorization_url.return_value

    def test__no_browser__prints_url_and_does_not_open_it(
        self, mock_webbrowser_open: mock.Mock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        result = runner.invoke(app, ["auth", "--no-browser"])

        assert result.exit_code == 0
        mock_webbrowser_open.assert_not_called()
        output = clean_typer_text(result.output)
        assert "https://flow.polar.com/oauth2/authorization" in output

    def test__member_id__passed_through(self, mock_auth_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["auth", "--member-id", "custom-id"])

        assert result.exit_code == 0
        auth_in, _kwargs = mock_auth_logic.call_args.args, mock_auth_logic.call_args.kwargs
        assert auth_in[0].member_id == "custom-id"

    def test__force__passed_through(self, mock_auth_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["auth", "--force"])

        assert result.exit_code == 0
        auth_in = mock_auth_logic.call_args.args[0]
        assert auth_in.force is True

    def test__env_file__passed_through(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "custom.env"

        result = runner.invoke(app, ["auth", "--env-file", str(env_file)])

        assert result.exit_code == 0
        auth_in = mock_auth_logic.call_args.args[0]
        assert auth_in.env_file == env_file

    def test__client_id_option__overrides_settings(
        self, mock_get_polar_oauth_client: mock.Mock, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["auth", "--no-browser", "--client-id", "cli-client-id"])

        assert result.exit_code == 0
        mock_get_polar_oauth_client.assert_called_once_with(
            client_id="cli-client-id", client_secret="settings-client-secret"
        )

    def test__missing_client_id__actionable_message__exit_1(
        self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        monkeypatch.setattr(polar_settings, "CLIENT_ID", None)

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "POLAR_CLIENT_ID is not set" in output
        assert "admin.polaraccesslink.com" in output

    def test__missing_client_secret__prompts_hidden(
        self, monkeypatch: pytest.MonkeyPatch, mock_get_polar_oauth_client: mock.Mock, runner: CliRunner
    ) -> None:
        monkeypatch.setattr(polar_settings, "CLIENT_SECRET", None)

        result = runner.invoke(app, ["auth", "--no-browser"], input="typed-secret\n")

        assert result.exit_code == 0
        mock_get_polar_oauth_client.assert_called_once_with(
            client_id="settings-client-id", client_secret="typed-secret"
        )
        assert "typed-secret" not in result.output

    def test__missing_redirect_uri__actionable_message__exit_1(
        self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        monkeypatch.setattr(polar_settings, "REDIRECT_URI", None)

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "POLAR_REDIRECT_URI is not set" in output
        assert "admin.polaraccesslink.com" in output

    def test__authorization_denied__actionable_message__exit_1(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_auth_logic.side_effect = AuthorizationDeniedError("Authorization was declined (access_denied).")

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "declined" in output

    def test__state_mismatch__actionable_message__exit_1(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_auth_logic.side_effect = AuthorizationStateMismatchError("state did not match")

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "state did not match" in output

    def test__timeout__actionable_message__exit_1(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_auth_logic.side_effect = AuthorizationTimeoutError("timed out waiting")

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "timed out" in output

    def test__credentials_already_exist__actionable_message__exit_1(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_auth_logic.side_effect = CredentialsAlreadyExistError("already has POLAR_ACCESS_TOKEN set")

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "already has POLAR_ACCESS_TOKEN" in output

    def test__port_in_use__actionable_message__exit_1(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_auth_logic.side_effect = OSError("Could not bind to port 8000 — it may already be in use.")

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "port 8000" in output

    def test__401_from_token_exchange__actionable_message__exit_1(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_auth_logic.side_effect = _http_status_error(httpx.codes.UNAUTHORIZED)

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "401" in output
        assert "client-id" in output.lower() or "client_id" in output.lower()

    def test__403_from_registration__actionable_message__exit_1(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_auth_logic.side_effect = _http_status_error(httpx.codes.FORBIDDEN)

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "403" in output
        assert "account.polar.com" in output

    def test__invalid_grant__actionable_message__exit_1(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner, clean_typer_text: TextCleaner
    ) -> None:
        mock_auth_logic.side_effect = _http_status_error(httpx.codes.BAD_REQUEST, json_body={"error": "invalid_grant"})

        result = runner.invoke(app, ["auth"])

        assert result.exit_code == 1
        output = clean_typer_text(result.stderr)
        assert "invalid_grant" in output
        assert "10 minutes" in output

    def test__other_bad_request__not_invalid_grant__unhandled(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner
    ) -> None:
        mock_auth_logic.side_effect = _http_status_error(
            httpx.codes.BAD_REQUEST, json_body={"error": "some_other_error"}
        )

        result = runner.invoke(app, ["auth"])

        assert result.exit_code != 0
        assert isinstance(result.exception, httpx.HTTPStatusError)

    def test__400_with_non_json_body__not_invalid_grant__unhandled(
        self, mock_auth_logic: mock.AsyncMock, runner: CliRunner
    ) -> None:
        mock_auth_logic.side_effect = _http_status_error_non_json_body(httpx.codes.BAD_REQUEST)

        result = runner.invoke(app, ["auth"])

        assert result.exit_code != 0
        assert isinstance(result.exception, httpx.HTTPStatusError)

    def test__unhandled_status_code__propagates(self, mock_auth_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_auth_logic.side_effect = _http_status_error(httpx.codes.INTERNAL_SERVER_ERROR)

        result = runner.invoke(app, ["auth"])

        assert result.exit_code != 0
        assert isinstance(result.exception, httpx.HTTPStatusError)


class TestAuthLogic:
    TARGET_PATH: Final[str] = "polarexport.infrastructure.entrypoints.cli.commands.auth"

    @pytest.fixture(autouse=True)
    def mock_get_auth_callback_receiver(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.get_auth_callback_receiver", return_value=mock.Mock()) as patched:
            yield patched

    @pytest.fixture(autouse=True)
    def mock_get_credentials_store(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.get_credentials_store", return_value=mock.Mock()) as patched:
            yield patched

    @pytest.fixture
    def mock_auth_login_use_case(self) -> Iterable[mock.Mock]:
        instance = mock.Mock()
        instance.login = mock.AsyncMock(return_value=AuthReportFactory.build())
        with mock.patch(f"{self.TARGET_PATH}.AuthLoginUseCase", return_value=instance) as patched:
            yield patched

    @pytest.fixture
    def client(self) -> PolarOAuthClient:
        return PolarOAuthClient(
            client_id="dummy-client-id",
            client_secret="dummy-client-secret",
            authorization_url=HttpUrl("https://flow.polar.com/oauth2/authorization"),
            token_url=HttpUrl("https://polarremote.com/v2/oauth2/token"),
            registration_base_url=HttpUrl("https://www.polaraccesslink.com"),
        )

    async def test__nominal__delegates_to_use_case(
        self, mock_auth_login_use_case: mock.Mock, client: PolarOAuthClient
    ) -> None:
        auth_in = AuthLoginInputFactory.build()

        report = await auth_logic(auth_in, client=client, state="expected-state")

        use_case_instance = mock_auth_login_use_case.return_value
        use_case_instance.login.assert_awaited_once_with(auth_in, state="expected-state")
        assert report is use_case_instance.login.return_value
        mock_auth_login_use_case.assert_called_once_with(
            auth_provider=client, auth_callback_receiver=mock.ANY, credentials_store=mock.ANY
        )
