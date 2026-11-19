# Existing IkaBot session bridge — opt-in, read-only milestone

Daedalus can now query the vendored IkaBot IPC interface for **already-authenticated** account sessions, city identities, and warehouse resources without starting another login or browser. This connects the backend and native GUI reporting workflow, but **does not yet provide live start/stop game-task controls or account authentication handoff**.

## Prerequisites and ownership

1. The IkaBot process must run the Daedalus-vendored engine with the new `list_sessions`, `list_cities_existing`, and `warehouse_snapshots_existing` actions. **Unmodified stable IkaBot and the existing production bot are not compatible with these additional IPC operations.** Do not upgrade/restart a live production session to test this feature.
2. Start one compatible IkaBot engine process in a **separate authorized test environment** and authenticate it normally. The bot's own in-memory logged-in session must be present. Daedalus **never calls** `Session.from_saved` or opens a second game login for this bridge.
3. The engine and controller must run **on the same host as the same OS user**, with a protected `~/.ikabot/ipc.json` descriptor, an authenticated loopback socket, and the same HOME directory. The controller will refuse group/world-readable, symlinked, malformed, non-loopback or stale descriptors.
4. Configure only secret-free `~/.config/daedalus/accounts.toml` metadata; `world` and `player` must match the existing authenticated engine session. Neither this file nor Git contains Gameforge credentials or IkaBot IPC keys.

## Start the read-only backend

```bash
python -m pip install -e ".[server,client]"
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
daedalus serve --accounts-file ~/.config/daedalus/accounts.toml --connect-existing-ipc
```

The backend binds **127.0.0.1:8765 only**. It reads the existing `~/.ikabot/ipc.json` when a request arrives; it does not attempt authentication at startup.

If the existing IPC descriptor is elsewhere, use `--ipc-descriptor /protected/path/ipc.json` with `--connect-existing-ipc`. Do not copy or print the file: it contains a live IPC authentication key.

## Native GUI test

On the Mac with the installed Daedalus GUI, use **Connection** to connect to your local backend or a protected SSH tunnel to a remote backend. Paste its backend bearer token (different from the IkaBot IPC authkey). In **Accounts**, click **Check IkaBot sessions**; accounts with matching engine sessions will show **Attached**. In **Warehouses**, choose an account and **Load warehouses**; a compatible existing engine session fetches its real per-city warehouse spans, and the backend returns only typed resource values to the GUI. The familiar 220K unsecured-resource filter and CSV/JSON export work on those snapshots.

Remote clients do **not** read IkaBot's IPC file, session cookies, password or Gameforge tokens. Only the backend process on the engine host communicates with the local IPC socket.

## Read-only API additions

All endpoints require the Daedalus backend bearer token:

- `GET /api/v1/engine/connected-accounts` — IDs of configured, enabled accounts with a **unique** matching existing IkaBot in-memory session
- `GET /api/v1/accounts/{id}/cities` — city IDs/names/coordinates/trade goods, existing session required
- `GET /api/v1/warehouses/{id}` — typed per-city unsecured resource values and storage capacity; missing quantities stay `null` rather than zero

Engine HTML is parsed inside its process; **raw game HTML and hidden action tokens are not returned over IPC**. If no compatible logged-in session exists, return 503 rather than starting a login or inventing inventory. Requests for warehouse snapshots do invoke normal read-only `session.get` operations of the existing authenticated game session, so only enable this explicitly where you intend to query live data.

## Current limitations

The bridge is opt-in and does not authorize a second daemon to share game session ownership. Host-local Daedalus file locks still do not coordinate different computers or independent OS users. It also cannot stop tasks, renew credentials, restore a lost login, automatically navigate CAPTCHA, or migrate existing production tmux sessions. These are limitations of **this read-only IPC bridge**, not a description of the entire current app. Separate later changes added task control, native Mac human recovery and protected credentials; unattended CAPTCHA and production-wide migration are not supported, and owner-only live acceptance remains open in [issue #60](https://github.com/itshak/Daedalus/issues/60).

**Offline CI** uses a synthetic localhost socket, mock game sessions and fabricated warehouse HTML. It never calls Gameforge.
