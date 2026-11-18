"""Opt-in local-only synthetic API for one-click native desktop preview.

On explicit user request, starts exactly one ephemeral demo FastAPI server on
an OS-selected 127.0.0.1 port. It never reads real account files, IPC,
Gameforge credentials, keyring, cookies or environment bearer tokens.
The in-memory backend secret is never printed or persisted.
"""

from __future__ import annotations

import secrets
import socket
import threading
import time
from typing import Self


class OfflineDemoUnavailable(RuntimeError):
    """Sanitized failure; no internal HTTP response or token is exposed."""


class EmbeddedDemoServer:
    def __init__(self) -> None:
        self._server: object | None = None
        self._thread: threading.Thread | None = None
        self._token: str | None = None
        self._port: int | None = None

    @property
    def url(self) -> str:
        if self._port is None:
            raise OfflineDemoUnavailable("Offline demo backend is not running")
        return f"http://127.0.0.1:{self._port}"

    @property
    def token(self) -> str:
        if self._token is None:
            raise OfflineDemoUnavailable("Offline demo backend is not running")
        return self._token

    @property
    def running(self) -> bool:
        return (
            self._server is not None
            and getattr(self._server, "started", False) is True
            and self._thread is not None
            and self._thread.is_alive()
        )

    def start(self) -> Self:
        if self.running:
            return self
        if self._thread is not None:
            raise OfflineDemoUnavailable("Previous demo backend did not stop cleanly")
        try:
            import uvicorn

            from daedalus.api import create_app
        except ImportError as exc:
            raise OfflineDemoUnavailable(
                'Install the Daedalus server dependency to run the isolated demo'
            ) from exc

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", 0))
            sock.listen(16)
            port = sock.getsockname()[1]
            token = secrets.token_urlsafe(48)
            app = create_app(api_token=token, demo_mode=True)
            config = uvicorn.Config(
                app, host="127.0.0.1", port=port, log_level="error",
                access_log=False, proxy_headers=False, lifespan="off",
            )
            server = uvicorn.Server(config)

            def serve() -> None:
                try:
                    server.run(sockets=[sock])
                finally:
                    sock.close()

            worker = threading.Thread(
                target=serve, name="daedalus-synthetic-demo", daemon=True,
            )
            self._server = server
            self._thread = worker
            self._port = port
            self._token = token
            worker.start()
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                if self.running:
                    return self
                if not worker.is_alive():
                    break
                time.sleep(0.025)
        except Exception as exc:
            self.stop()
            sock.close()
            raise OfflineDemoUnavailable(
                "Cannot start the isolated local synthetic demo backend"
            ) from exc

        self.stop()
        raise OfflineDemoUnavailable("Local synthetic demo backend did not start")

    def stop(self) -> None:
        server = self._server
        worker = self._thread
        if server is not None:
            server.should_exit = True
        if worker is not None:
            worker.join(timeout=9)
        if worker is not None and worker.is_alive():
            raise OfflineDemoUnavailable(
                "Synthetic demo backend is still shutting down"
            )
        self._server = None
        self._thread = None
        self._port = None
        self._token = None

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *_unused: object) -> None:
        self.stop()
