import asyncio
import socket

import httpx

import pytest

from polarexport.domain.exceptions import AuthorizationDeniedError
from polarexport.domain.exceptions import AuthorizationStateMismatchError
from polarexport.domain.exceptions import AuthorizationTimeoutError
from polarexport.infrastructure.adapters.receivers.local_http import LocalHttpCallbackReceiver


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _wait_until_listening(port: int, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            if asyncio.get_running_loop().time() > deadline:
                raise
            await asyncio.sleep(0.01)
        else:
            writer.close()
            await writer.wait_closed()
            return


class TestLocalHttpCallbackReceiver:
    @pytest.fixture
    def port(self) -> int:
        return _free_port()

    @pytest.fixture
    def redirect_uri(self, port: int) -> str:
        return f"http://127.0.0.1:{port}/callback"

    @pytest.fixture
    def receiver(self, redirect_uri: str) -> LocalHttpCallbackReceiver:
        return LocalHttpCallbackReceiver(redirect_uri=redirect_uri)

    async def test__nominal__returns_code_and_answers_browser(
        self, receiver: LocalHttpCallbackReceiver, port: int
    ) -> None:
        task = asyncio.create_task(receiver.wait_for_code(expected_state="expected-state", timeout=5.0))
        await _wait_until_listening(port)

        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(f"http://127.0.0.1:{port}/callback?code=auth-code&state=expected-state")

        assert response.status_code == 200
        assert "close this tab" in response.text
        code = await task
        assert code == "auth-code"

    async def test__state_mismatch__raises(self, receiver: LocalHttpCallbackReceiver, port: int) -> None:
        task = asyncio.create_task(receiver.wait_for_code(expected_state="expected-state", timeout=5.0))
        await _wait_until_listening(port)

        async with httpx.AsyncClient() as http_client:
            await http_client.get(f"http://127.0.0.1:{port}/callback?code=auth-code&state=wrong-state")

        with pytest.raises(AuthorizationStateMismatchError):
            await task

    async def test__denied__raises(self, receiver: LocalHttpCallbackReceiver, port: int) -> None:
        task = asyncio.create_task(receiver.wait_for_code(expected_state="expected-state", timeout=5.0))
        await _wait_until_listening(port)

        async with httpx.AsyncClient() as http_client:
            await http_client.get(f"http://127.0.0.1:{port}/callback?error=access_denied")

        with pytest.raises(AuthorizationDeniedError):
            await task

    async def test__unrelated_path__ignored__still_waits_for_the_real_callback(
        self, receiver: LocalHttpCallbackReceiver, port: int
    ) -> None:
        task = asyncio.create_task(receiver.wait_for_code(expected_state="expected-state", timeout=5.0))
        await _wait_until_listening(port)

        async with httpx.AsyncClient() as http_client:
            await http_client.get(f"http://127.0.0.1:{port}/favicon.ico")
            await http_client.get(f"http://127.0.0.1:{port}/callback?code=auth-code&state=expected-state")

        code = await task
        assert code == "auth-code"

    async def test__matching_path_no_code_no_error__ignored__still_waits(
        self, receiver: LocalHttpCallbackReceiver, port: int
    ) -> None:
        task = asyncio.create_task(receiver.wait_for_code(expected_state="expected-state", timeout=5.0))
        await _wait_until_listening(port)

        async with httpx.AsyncClient() as http_client:
            await http_client.get(f"http://127.0.0.1:{port}/callback?state=expected-state")
            await http_client.get(f"http://127.0.0.1:{port}/callback?code=auth-code&state=expected-state")

        code = await task
        assert code == "auth-code"

    async def test__timeout__raises(self, receiver: LocalHttpCallbackReceiver) -> None:
        with pytest.raises(AuthorizationTimeoutError):
            await receiver.wait_for_code(expected_state="expected-state", timeout=0.05)

    async def test__port_already_in_use__raises_os_error_naming_the_port(self, redirect_uri: str, port: int) -> None:
        blocker = await asyncio.start_server(lambda _r, _w: None, host="127.0.0.1", port=port)
        try:
            receiver = LocalHttpCallbackReceiver(redirect_uri=redirect_uri)
            with pytest.raises(OSError, match=str(port)):
                await receiver.wait_for_code(expected_state="expected-state", timeout=1.0)
        finally:
            blocker.close()
            await blocker.wait_closed()
