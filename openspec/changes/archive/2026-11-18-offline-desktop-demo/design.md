# Design — opted-in synthetic data pipeline

`--demo` selects an explicit backend-only mode. It refuses `--accounts-file`, `--connect-existing-ipc`, `--ipc-descriptor`, `--enable-task-control`, `--task-ledger` and `--enable-account-editing`. The API constructor also refuses any injected real account path, IPC client, task controller, snapshot provider, session coordinator or editor when `demo_mode=True`.

Only hardcoded, visibly labeled fake `demo_*` accounts are loaded from package-local Python constants. The warehouses are constructed as typed `CityWarehouseSnapshot` records through the same read-only API contract, with exact numeric values, true zero distinct from unknown None, multiple island groups and a >220K example. The capture time represents the sample generation time, not a real game observation.

The API health mode is `synthetic_demo`; account records, capability inventory and reporting envelopes carry `synthetic_demo` or `synthetic` flags. Warehouse and connection UI surfaces show unmissable synthetic labels. Task control, editing and existing-session attachment remain unavailable; the bearer token and loopback/SSH constraints are unchanged.

The demo is usable with `daedalus serve --demo` and `daedalus-desktop` using an operator-generated bearer token. It never reads private account TOML, launches IkaBot, opens a browser, calls Ikariam or writes session files. This is an isolated user-facing preview, **not** a simulation of live automation.
