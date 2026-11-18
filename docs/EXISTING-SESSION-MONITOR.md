# Optional existing-session recovery monitor

Daedalus can watch the health of **an already-running, compatible IkaBot session** and request manual help when that session is no longer valid. It cannot create a new Gameforge login, drive Selenium, solve CAPTCHA, restore a browser session or automatically replay tasks. This feature is a safe incremental building block, not a new-account bot supervisor.

## Enable on one authoritative backend

Use only the Daedalus-vendored experimental engine with the `validate_session_existing` IPC action. It must already have an authenticated session in memory on the same host/user. Do not upgrade or restart production bots to test this path.

```bash
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
daedalus serve --connect-existing-ipc --enable-task-control --monitor-existing-sessions \
  --accounts-file ~/.config/daedalus/accounts.toml
```

All three opt-in flags are necessary. The server remains loopback-bound, requires a bearer token, does not create game workers at startup and performs no game validation before an operator attaches a specific account.

In **Daedalus desktop → Accounts**, select the configured account, press **Monitor verified session**, and confirm the dialog. The backend verifies the unique existing world/player session through an authenticated local IPC request using a fixed, read-only world GET. On success the backend holds its own host-local ownership lease. The UI never transmits game credentials.

## Expiry and human help

After explicit attachment, the monitor validates the managed session periodically. If it has expired, the session moves into `needs_assistance` and the existing user-confirmed task start is blocked. The backend creates a random, one-use nonsecret ticket while holding the lease. The desktop checks `GET /api/v1/auth-assistance/pending` and displays a generic notification once per waiting ticket. Select the account and **Check login assistance** to see the fixed reason; **Confirm manual step complete** only after you have really completed an independently trusted manual login action.

The monitor does not transfer browser cookies into an IkaBot process. If the manual step happens in an unrelated browser, its new cookies are **not** automatically handed off to the engine; its validation will remain unsuccessful until a separate secure handoff or engine-side restoration mechanism updates the managed session. This is still unfinished.\n\nThat confirmation **does not** mark authentication successful. The same trusted monitor must independently verify the world page again. On failure a new ticket is required. No task is automatically restarted or sent again after an ambiguous result, preventing accidental duplicate game operations. A real Selenium/browser handoff assistant and task recovery supervisor remain unfinished.

## Security boundaries

- Only a fixed world-host read-only GET is performed through an existing in-memory IkaBot `Session`. No arbitrary URL, saved-session login or lobby loginLink is accepted by this IPC path.
- The public API rejects monitoring without explicit bearer authorization and `confirmed=true`; it refuses disabled or unknown accounts and always returns only account ID, nonsecret reason/state and random ticket ID.
- If the engine cannot provide the compatible action, the monitor fails closed. No synthetic data is presented as live.
- Host-local file locks cannot coordinate independent legacy bots or another computer. Designate only one authoritative backend per world/player. Do not use a production IkaBot worker as a test worker.
- The monitor is voluntary and its periodic read-only world requests occur only for accounts deliberately attached to monitoring. It does not create a fresh game login on errors.

## Synthetic verification

Tests use fabricated world HTML, fake local socket IPC, FastAPI TestClient, mocked desktop Qt dialogs and fake session owners. CI never sends Gameforge traffic. Run:

```bash
python -m pytest -q tests/test_session_monitor.py tests/test_engine_ipc.py tests/test_desktop.py
python -m pytest -q engine/ikabot/tests/ikabot/helpers/test_daedalus_existing_ipc.py
python -m ruff check src tests packaging
openspec validate --all --strict --no-interactive
```
