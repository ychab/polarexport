import asyncio
import logging
from urllib.parse import parse_qs
from urllib.parse import urlparse

from polarexport.application.ports.receivers.callback import AuthCallbackReceiverPort
from polarexport.domain.exceptions import AuthorizationDeniedError
from polarexport.domain.exceptions import AuthorizationStateMismatchError
from polarexport.domain.exceptions import AuthorizationTimeoutError

logger = logging.getLogger(__name__)

_RESPONSE_BODY = b"<html><body>Authorization complete \xe2\x80\x94 you can close this tab.</body></html>"


class LocalHttpCallbackReceiver(AuthCallbackReceiverPort):
    """`AuthCallbackReceiverPort` implementation: a one-shot local HTTP listener.

    Binds to the host/port parsed from `redirect_uri` and serves exactly one matching request before
    closing, so `polarexport auth` can catch the OAuth redirect without a permanent local server.
    """

    def __init__(self, redirect_uri: str) -> None:
        self._redirect_uri = redirect_uri

    async def wait_for_code(self, *, expected_state: str, timeout: float) -> str:
        parsed = urlparse(self._redirect_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 80
        callback_path = parsed.path or "/"

        code_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                await self._handle_request(reader, writer, callback_path, expected_state, code_future)
            finally:
                writer.close()

        try:
            server = await asyncio.start_server(handle_client, host=host, port=port)
        except OSError as e:
            raise OSError(
                f"Could not bind to port {port} — it may already be in use (an old "
                "`python3 -m http.server` from the manual flow may still be running)."
            ) from e

        async with server:
            try:
                async with asyncio.timeout(timeout):
                    return await code_future
            except TimeoutError as e:
                raise AuthorizationTimeoutError(
                    "Timed out waiting for the Polar authorization callback — the browser tab was "
                    "never completed. Just re-run `polarexport auth`."
                ) from e

    @staticmethod
    async def _handle_request(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        callback_path: str,
        expected_state: str,
        code_future: "asyncio.Future[str]",
    ) -> None:
        request_line = await reader.readline()
        while True:
            line = await reader.readline()
            if not line or line in (b"\r\n", b"\n"):
                break

        try:
            _method, target, _version = request_line.decode("latin-1").split(" ", 2)
        except ValueError:
            return

        parsed_target = urlparse(target)
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: "
            + str(len(_RESPONSE_BODY)).encode()
            + b"\r\nConnection: close\r\n\r\n"
            + _RESPONSE_BODY
        )
        await writer.drain()

        if parsed_target.path != callback_path or code_future.done():
            return

        query = parse_qs(parsed_target.query)
        error = query.get("error", [None])[0]
        if error is not None:
            code_future.set_exception(AuthorizationDeniedError(f"Authorization was declined ({error})."))
            return

        state = query.get("state", [None])[0]
        if state != expected_state:
            code_future.set_exception(
                AuthorizationStateMismatchError(
                    "The callback's state did not match the request — re-run `polarexport auth`."
                )
            )
            return

        code = query.get("code", [None])[0]
        if code is not None:
            code_future.set_result(code)
