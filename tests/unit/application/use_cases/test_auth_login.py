from unittest import mock

import pytest

from polarexport.application.use_cases.auth_login import AuthLoginUseCase
from polarexport.domain.exceptions import AuthorizationDeniedError
from polarexport.domain.exceptions import AuthorizationStateMismatchError
from polarexport.domain.exceptions import AuthorizationTimeoutError

from tests.unit.factories.entities.auth import OAuthTokensFactory
from tests.unit.factories.inputs.auth import AuthLoginInputFactory


class TestAuthLoginUseCase:
    @pytest.fixture
    def use_case(
        self,
        mock_auth_provider: mock.Mock,
        mock_auth_callback_receiver: mock.AsyncMock,
        mock_credentials_store: mock.AsyncMock,
    ) -> AuthLoginUseCase:
        return AuthLoginUseCase(
            auth_provider=mock_auth_provider,
            auth_callback_receiver=mock_auth_callback_receiver,
            credentials_store=mock_credentials_store,
        )

    async def test__nominal__reports_no_token(
        self,
        use_case: AuthLoginUseCase,
        mock_auth_provider: mock.Mock,
        mock_auth_callback_receiver: mock.AsyncMock,
        mock_credentials_store: mock.AsyncMock,
    ) -> None:
        mock_auth_callback_receiver.wait_for_code.return_value = "auth-code"
        mock_auth_provider.exchange_code.return_value = OAuthTokensFactory.build(
            access_token="tok-must-never-be-logged", user_id="12345678"
        )
        mock_auth_provider.register_user.return_value = True
        auth_in = AuthLoginInputFactory.build(member_id="yannick", timeout=42.0)

        report = await use_case.login(auth_in, state="expected-state")

        mock_auth_callback_receiver.wait_for_code.assert_awaited_once_with(
            expected_state="expected-state", timeout=42.0
        )
        mock_auth_provider.exchange_code.assert_awaited_once_with("auth-code", redirect_uri=auth_in.redirect_uri)
        mock_auth_provider.register_user.assert_awaited_once_with(
            access_token="tok-must-never-be-logged", member_id="yannick"
        )
        mock_credentials_store.write.assert_awaited_once_with(
            access_token="tok-must-never-be-logged", user_id="12345678", env_path=auth_in.env_file, force=auth_in.force
        )
        assert report.user_id == "12345678"
        assert report.member_id == "yannick"
        assert report.newly_registered is True
        assert not any("tok-must-never-be-logged" in str(value) for value in vars(report).values())

    async def test__member_id_not_given__defaults_to_polar_user_id(
        self,
        use_case: AuthLoginUseCase,
        mock_auth_provider: mock.Mock,
        mock_auth_callback_receiver: mock.AsyncMock,
    ) -> None:
        mock_auth_callback_receiver.wait_for_code.return_value = "auth-code"
        mock_auth_provider.exchange_code.return_value = OAuthTokensFactory.build(user_id="12345678")
        mock_auth_provider.register_user.return_value = True
        auth_in = AuthLoginInputFactory.build(member_id=None)

        report = await use_case.login(auth_in, state="expected-state")

        mock_auth_provider.register_user.assert_awaited_once_with(access_token=mock.ANY, member_id="12345678")
        assert report.member_id == "12345678"

    async def test__409_already_registered__treated_as_success(
        self,
        use_case: AuthLoginUseCase,
        mock_auth_provider: mock.Mock,
        mock_auth_callback_receiver: mock.AsyncMock,
        mock_credentials_store: mock.AsyncMock,
    ) -> None:
        mock_auth_callback_receiver.wait_for_code.return_value = "auth-code"
        mock_auth_provider.exchange_code.return_value = OAuthTokensFactory.build(user_id="12345678")
        mock_auth_provider.register_user.return_value = False
        auth_in = AuthLoginInputFactory.build()

        report = await use_case.login(auth_in, state="expected-state")

        assert report.newly_registered is False
        mock_credentials_store.write.assert_awaited_once()

    async def test__force__passed_through_to_credentials_store(
        self,
        use_case: AuthLoginUseCase,
        mock_auth_provider: mock.Mock,
        mock_auth_callback_receiver: mock.AsyncMock,
        mock_credentials_store: mock.AsyncMock,
    ) -> None:
        mock_auth_callback_receiver.wait_for_code.return_value = "auth-code"
        mock_auth_provider.exchange_code.return_value = OAuthTokensFactory.build(user_id="12345678")
        mock_auth_provider.register_user.return_value = True
        auth_in = AuthLoginInputFactory.build(force=True)

        await use_case.login(auth_in, state="expected-state")

        assert mock_credentials_store.write.call_args.kwargs["force"] is True

    async def test__state_mismatch__propagates_before_exchange(
        self,
        use_case: AuthLoginUseCase,
        mock_auth_provider: mock.Mock,
        mock_auth_callback_receiver: mock.AsyncMock,
    ) -> None:
        mock_auth_callback_receiver.wait_for_code.side_effect = AuthorizationStateMismatchError("mismatch")
        auth_in = AuthLoginInputFactory.build()

        with pytest.raises(AuthorizationStateMismatchError):
            await use_case.login(auth_in, state="expected-state")

        mock_auth_provider.exchange_code.assert_not_awaited()

    async def test__timeout__propagates(
        self, use_case: AuthLoginUseCase, mock_auth_callback_receiver: mock.AsyncMock
    ) -> None:
        mock_auth_callback_receiver.wait_for_code.side_effect = AuthorizationTimeoutError("timed out")
        auth_in = AuthLoginInputFactory.build()

        with pytest.raises(AuthorizationTimeoutError):
            await use_case.login(auth_in, state="expected-state")

    async def test__denied__propagates(
        self, use_case: AuthLoginUseCase, mock_auth_callback_receiver: mock.AsyncMock
    ) -> None:
        mock_auth_callback_receiver.wait_for_code.side_effect = AuthorizationDeniedError("declined")
        auth_in = AuthLoginInputFactory.build()

        with pytest.raises(AuthorizationDeniedError):
            await use_case.login(auth_in, state="expected-state")
