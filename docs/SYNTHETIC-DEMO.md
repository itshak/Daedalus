# Test the native Daedalus desktop with synthetic data

Use this explicit offline sample mode when you want to inspect the Mac
desktop, multi-account navigation, warehouse filtering, island grouping,
task inventory and CSV/JSON/TXT exports **without** a Gameforge login, an
IkaBot engine process or any production credentials.

**All displayed accounts, cities and resource values are fictional.**
The API, native window, connection label and warehouse page visibly identify
the synthetic mode. This is not a live automation demonstration.

## Easiest: one click in the native Mac preview

Open the app, switch to **Connection**, and press **Try offline demo — no game login**. The GUI starts an ephemeral synthetic-only local backend and connects itself without pasting any bearer token. The backend stops when you close the native app. See [one-click demo](ONECLICK-DEMO.md). The manual two-terminal steps below remain available for standalone backend testing.

## Start a local synthetic backend

In a separate terminal, after installing the project and extras:

```bash
python -m pip install -e ".[server,desktop]"
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
daedalus serve --demo --host 127.0.0.1 --port 8765
```

The demo only binds loopback and still requires a strong bearer token. It
loads hardcoded `demo_alpha` and `demo_beta` accounts and sample warehouse
resources. It does **not** read your `~/.config/daedalus/accounts.toml`, IPC
discovery files, Gameforge account storage or browser profiles.

## Connect the Mac app

In another terminal in the same environment run:

```bash
daedalus-desktop
```

Open **Connection**, enter `http://127.0.0.1:8765` and paste the token
generated in the first terminal. You should see **SYNTHETIC DEMO** in the
window title, connection status and warehouse page. Use the Accounts tab to
view the two fictional identities and Warehouses to inspect the sample
Athens/Sparta/Miletus entries. The existing 220K unsecured-resource filter,
unknown resource placeholders and grouped/exportable reports can be tried.
Task controls, account editing and session attachment remain unavailable.

If the backend is on a remote trusted host, use an authenticated SSH tunnel.
The server never listens on a public interface. Do not expose the API bearer
token in command-line arguments, screenshots, logs or repository files.

## Safety properties

Demo cannot be combined with `--accounts-file`, `--connect-existing-ipc`,
`--ipc-descriptor`, `--enable-task-control`, `--task-ledger` or
`--enable-account-editing`. The constructor also rejects injected real
data providers, task controllers and session coordinators. No remote
Gameforge login, game HTTP, real task execution, session restoration or
account mutation takes place in this mode.

Synthetic demo resources are generated on request and carry timestamps
representing sample generation, **not real game observations**.

To work with your own account, first stop the demo and separately configure
the explicitly opted-in secure existing-session backend, following
`docs/EXISTING-IPC.md` and `docs/TASK-CONTROL.md`. A supervised new-account
login/cookie handoff is still unfinished, so do not migrate production bots.

## Offline verification

Run:

```bash
python -m pytest tests/test_demo.py tests/test_desktop.py
python -m ruff check src tests packaging
openspec validate --all --strict --no-interactive
```

These tests run with synthetic data and mock/in-process HTTP only. The normal
GitHub macOS workflow validates the Cocoa-backed Qt app and preview bundle.
