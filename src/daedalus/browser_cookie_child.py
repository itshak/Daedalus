"""Private account-scoped IkaBot IPC child, restored from a server-verified cookie.

No password, cookie or lobby token is sent over CLI, environment or stdout.
The child reads only its exact account binding from the backend OS keyring,
independently attests the world/player, and owns a private IPC descriptor.
"""
from __future__ import annotations

import json
import sys
import time

from daedalus.accounts import Account


def main() -> int:
    session = None
    server = None
    try:
        raw = sys.stdin.buffer.readline(4097)
        if len(raw) > 4096:
            return 2
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"id", "world", "player"}:
            return 2
        account = Account(
            id=data["id"], world=data["world"], player=data["player"],
            label="Verified cookie worker", enabled=True,
        )
        from daedalus.saved_session_recovery import (
            _email_binding, _real_restore, _world_cookie_binding,
            verify_restored_identity,
        )
        from ikabot.helpers.ipc import start_dedicated_ipc_server, stop_ipc_server

        email = _email_binding(account)
        cookie = _world_cookie_binding(account)
        if cookie is None:
            return 3
        session = _real_restore(account, email, cookie)
        verify_restored_identity(session, account)
        server = start_dedicated_ipc_server(session)
        if server is None:
            return 3
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        return 0
    except Exception:
        # Never print upstream exceptions: they may contain private game URLs.
        return 1
    finally:
        if server is not None:
            try:
                stop_ipc_server()
            except Exception:
                pass
        if session is not None:
            http = getattr(session, "s", None)
            if callable(getattr(http, "close", None)):
                try:
                    http.close()
                except Exception:
                    pass


if __name__ == "__main__":
    sys.exit(main())
