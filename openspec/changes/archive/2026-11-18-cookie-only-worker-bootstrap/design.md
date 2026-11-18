# Design and boundaries

The CLI accepts `serve --accounts-file <private TOML> --connect-existing-ipc --restore-saved-account <ID> --confirm-read-only-network`. No private email, world cookie or bearer token is passed on the CLI. The existing OS keyring binding resolves the saved IkaBot email and optional already-verified cookie; `Session.from_saved(cookies_only=True)` performs exactly the existing read-only world validation, never the lobby loginLink. The configured canonical world and player must match the verified engine session.

The new `SavedCookieWorker` holds the same `OwnedAccountSession` lock for the lifetime of the process and starts only a dedicated localhost IPC endpoint after verification. Existing IPC owners are refused, not reused. If task control is opted in separately, it adopts the identical local lease only after protected IPC identity validation; the engine still validates built-in task parameters, UUID4 idempotency, and process ownership. On shutdown, the API stops accepting new task requests, releases its task controller, stops the private IPC, closes the HTTP connection without game logout, then releases the lease.

Offline tests inject fake keyrings, fake saved engine sessions, fake IPC, and verified identities. No private production directory, Gameforge endpoint, external browser, or real account is touched.

Remaining risks: an unrelated legacy bot without IPC is not covered by the Daedalus lease; one operator must isolate testing to a disposable account. Saved world cookies may be expired; fail closed and require explicit manual recovery. There is no automatic browser login or durable worker restart.
