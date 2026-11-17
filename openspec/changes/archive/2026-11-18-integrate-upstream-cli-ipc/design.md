# Design — upstream master plus CLI/IPC proposal

## Provenance

Base: public IkaBot master `3ea1e0eebfb2e52b5f53ea8b5051df2a9a887579`.
Overlay: upstream PR #499 head `062feec0f5f6ea5810bfe91126e337a2b86aa3e3`, including #502 and #511 changes.

Merge with Git in a temporary checkout using `git merge --no-commit --no-ff`; this yields a conflict-free union of current master fixes and the candidate CLI interface. Only import public source subtrees, not any locally customized bot or saved credentials. Preserve original MIT notices, original line endings, and upstream test fixtures.

## Engine and application separation

Leave upstream `ikabot` modules and public CLI/IPC implementation intact, rather than implementing a second game client. The new engine allows `--task`, `--config`, `--batch`, and `--cities`, and binds its IPC service to `127.0.0.1` with an authenticated local discovery file.

Daedalus's AST-based inventory reports whether candidate CLI/IPC entry points are present but does not automatically mark every task as fully schema-compatible or enable backend dispatch. Some tasks still require additional prepare hooks or typed parameter adapters.

## Safety

No live game sessions are opened by tests or diagnostics. Existing account workers and production tmux processes remain untouched. The daemon/controller must later own exclusive account leases, isolate IPC credentials, and validate every requested task.

## Verification

Run the upstream `tests/ikabot` offline against the merged source with a sandbox HOME, including focused IPC/config/task relaunch cases. Run Daedalus tests, Ruff, OpenSpec validation and credential-path checks. The engine CI matrix on GitHub must pass before merge. Public workflow permissions remain read-only.
