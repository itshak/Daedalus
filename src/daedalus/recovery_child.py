"""Account-scoped, trusted IkaBot engine worker.

Never launched directly from HTTP and never exposes a session on public ports.
A validated parent policy holds the world/player OS lease; this child runs the
maintained IkaBot loginLink path using a protected lobby credential received
through a local anonymous pipe, then serves a *private account-specific* IPC.
"""
from __future__ import annotations

import json
import sys
import time

from daedalus.accounts import Account


def main() -> int:
    try:
        raw = sys.stdin.buffer.readline(8193)
        if len(raw) > 8192:
            return 2
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {
            "id", "world", "player", "email", "lobby_token",
        }:
            return 2
        account = Account(
            id=data["id"], world=data["world"],
            player=data["player"], label="Isolated recovery worker", enabled=True,
        )
        if not isinstance(data["email"], str) or "@" not in data["email"]:
            return 2
        from ikabot.helpers.ipc import start_dedicated_ipc_server, stop_ipc_server
        from ikabot.web.session import Session

        from daedalus.saved_session_recovery import verify_restored_identity

        # This may mint a fresh *game-world* loginLink. It is not the cookie-only
        # check used by ordinary read-only monitoring and may log out a browser.
        session = Session.from_saved(
            mail=data["email"], world=account.world, player=account.player,
            cookies_only=False, lobby_token_override=data["lobby_token"],
        )
        verify_restored_identity(session, account)
        server = start_dedicated_ipc_server(session)
        if server is None:
            return 3
        # The parent uses the authenticated IPC descriptor as readiness; never
        # print or transmit the world cookie or refresh credential.
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        return 1
    except Exception:  # noqa: BLE001 - sanitized boundary or independent recovery loop
        # The parent exposes only fixed status codes. Never print a traceback;
        # upstream exceptions sometimes embed a Gameforge URL or response.
        return 1
    finally:
        # Child dies as a process group on parent shutdown; this cleanup also
        # handles a normal exit without leaving a stale descriptor.
        try:
            if "server" in locals():
                stop_ipc_server()
        except Exception:  # noqa: BLE001, S110 - no secrets in failure logging
            pass


if __name__ == "__main__":
    sys.exit(main())
