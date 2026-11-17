# Design — existing-only engine IPC

The engine owns the actual in-memory session. Add distinct actions `list_sessions`, `list_cities_existing`, and `warehouse_snapshots_existing`; each existing-only action selects **exactly one** authenticated world/player identity, refusing missing or ambiguous matches rather than calling `Session.from_saved`.

The warehouse action uses the native engine's session and city lookup to request warehouse HTML, but extracts only the `js_plunderable_*` and `js_capacity_*` span values; raw HTML, passwords, cookies and action tokens never leave the engine process. The backend parses these numeric strings with the existing Daedalus warehouse formatter and preserves unknown values as `null`.

`ExistingIPCClient` is a separate transport over the engine's authenticated loopback socket. The IPC key is obtained from an owner-only `ipc.json` file in the local user's protected home. The client validates owner, mode, absolute loopback host, port, PID and key shape. It has a hard-coded read-action allowlist, timeouts, response-size limit and generic error messages to avoid leaking engine error details.

The FastAPI backend uses `--connect-existing-ipc` to construct the bridge **without starting or connecting to the game on startup**. New HTTP GETs require the backend bearer token. The connected-accounts endpoint filters against configured identities, so the browser never sees unrelated IkaBot sessions. A missing/unsupported IPC connection returns HTTP 503. Account host leases remain separate from read-only observation; the new code does not misrepresent itself as the authenticated game worker.

The native GUI fetches attached-engine status only on an explicit user click and preserves existing warehouse reporting. CI creates a synthetic socket worker and a mocked IkaBot Session to assert that no restoration/login call occurs.
