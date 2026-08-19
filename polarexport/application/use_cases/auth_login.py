from datetime import datetime

from polarexport.application.inputs.auth import AuthLoginInput
from polarexport.application.ports.providers.auth import AuthProviderPort
from polarexport.application.ports.receivers.callback import AuthCallbackReceiverPort
from polarexport.application.ports.stores.credentials import CredentialsStorePort
from polarexport.domain.entities.auth import AuthReport


class AuthLoginUseCase:
    def __init__(
        self,
        auth_provider: AuthProviderPort,
        auth_callback_receiver: AuthCallbackReceiverPort,
        credentials_store: CredentialsStorePort,
    ) -> None:
        self._auth_provider = auth_provider
        self._auth_callback_receiver = auth_callback_receiver
        self._credentials_store = credentials_store

    async def login(self, auth_in: AuthLoginInput, *, state: str, obtained_at: datetime) -> AuthReport:
        code = await self._auth_callback_receiver.wait_for_code(expected_state=state, timeout=auth_in.timeout)
        tokens = await self._auth_provider.exchange_code(code, redirect_uri=auth_in.redirect_uri)

        member_id = auth_in.member_id if auth_in.member_id is not None else tokens.user_id
        newly_registered = await self._auth_provider.register_user(
            access_token=tokens.access_token, member_id=member_id
        )

        await self._credentials_store.write(
            access_token=tokens.access_token,
            user_id=tokens.user_id,
            obtained_at=obtained_at,
            expires_in=tokens.expires_in,
            path=auth_in.credentials_file,
            force=auth_in.force,
        )

        return AuthReport(
            user_id=tokens.user_id,
            member_id=member_id,
            newly_registered=newly_registered,
            credentials_path=auth_in.credentials_file,
        )
