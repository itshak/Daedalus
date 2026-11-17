# Design — read-only controller API

## Configuration
Use Python 3.11's `tomllib`. Default configuration is `~/.config/daedalus/accounts.toml`, overridable through an explicit path. Only `id`, `world`, `player`, `label`, `enabled` are permitted. Reject any unknown fields, including email, password, cookies or token fields; a future protected credential store owns auth material. Duplicate account IDs and world/player identities fail validation.

## Server
FastAPI is an optional `daedalus[server]` extra. `daedalus serve` requires `DAEDALUS_API_TOKEN` to be provided via the environment. Reject secrets shorter than 32 characters. Bind only to 127.0.0.1 or ::1. Remote clients connect through protected tunnels; raw 0.0.0.0 binding is intentionally unsupported.

Endpoints:
- `GET /api/v1/health`: unauthenticated, minimal read-only status.
- `GET /api/v1/accounts`: authenticated list of nonsecret account metadata.
- `GET /api/v1/capabilities`: authenticated AST-derived public engine operation registry.
- `GET /api/v1/warehouses/{account_id}`: authenticated read-only snapshot provider, 503 until connected.

No engine process is started or game HTTP action invoked by the server.

## Warehouse data
Parse `js_plunderable_{resource}` spans and the first `js_capacity_{resource}` span, matching the existing GUI. Prefer exact hidden tooltip amounts over rounded visible strings. Unknown values MUST remain null rather than become zero. Normalize 'crystal' to GUI 'glass'. A warehouse parser can accept an already-authenticated IkaBot Session, delegating the GET to `session.get` only; no independent network client or browser login.

## Tests
Use fake TOML accounts, fake HTML and mock existing game sessions. Check that no session is constructed at API startup. Verify unauthorized requests, invalid API keys, duplicate identities, missing warehouse values, capacity, tooltip precision and provider failures.
