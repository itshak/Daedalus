# Human browser recovery (offline-verified implementation)

Daedalus provides two **opt-in** local paths, neither of which collects passwords or solves CAPTCHA:

- `daedalus sessions assist-browser-login ACCOUNT_ID --config /private/accounts.toml --confirm-read-only-network` opens the official lobby in the system browser and accepts a manually copied **world** `ikariam` cookie through an echo-free terminal prompt.
- `daedalus sessions assist-playwright-login ACCOUNT_ID --config /private/accounts.toml --confirm-read-only-network` opens an **ephemeral, visible Chromium browser**. The operator logs in, solves any challenge, and navigates to the configured world. After typing `YES` in the original terminal, Daedalus reads only the secure `ikariam` cookie scoped to the exact world host. No cookie appears in terminal input, API requests, logs or browser-profile files.

For Playwright, install `pip install -e '.[browser-recovery]'` and `python -m playwright install chromium` on the same authorized host. Bind the existing saved IkaBot email first using `sessions bind-email ACCOUNT_ID`. Both paths require an interactive local terminal, protected OS keyring, canonical world, account-owner lease and explicit network consent. The game engine validates the cookie with a read-only world request and verifies its configured world/player before storing it. The browser closes, and the lease is released after verification. Neither path starts a second game worker.

**Remote deployment fallback:** use a trusted, authenticated graphical remote-desktop session *on the authoritative worker host*, then run `assist-playwright-login` in a terminal there. This keeps browser, cookie and keyring on the same host. Do not use a public VNC server, upload browser profiles or tunnel cookies through the Daedalus API. The Daedalus HTTP API intentionally does not provide a remote cookie-upload endpoint. An SSH terminal without a graphical browser can instead use `assist-browser-login` only if a trusted local browser on that same host is available.

**Important limitations:** These flows provision a verified cookie for subsequent cookie-only worker startup. They **do not** hot-swap credentials into an already-running engine worker, do not prove actual server-side player identity beyond the existing engine's session metadata, and do not create a new saved IkaBot identity. Existing-session monitoring can acknowledge manual help and independently revalidate an existing worker; it cannot infer that a separate browser login updated that worker. Real Gameforge compatibility remains untested until an authorized end-to-end run. Never operate recovery against an independently owned production session.

## Offline verification

`tests/test_browser_recovery.py` exercises account locking during human interaction, explicit consent, exact origin/world cookie selection, cleanup, keyring persistence only after engine validation, and rejection of invalid or mismatched sessions using a fake browser. No Gameforge requests or real credentials are used. The optional Playwright test has also been executed against a locally installed headless Chromium browser with all page traffic intercepted and synthetic cookie isolation: **7/7 browser recovery tests passed**. This verifies actual Chromium cookie-domain isolation, **not** Gameforge compatibility or real login.


## Dedicated-worker rebind API (offline-verified internal primitive)

`SavedCookieWorker.recover_from_verified_cookie(controller, confirmed=True)` provides an internal, explicit recovery step for a *dedicated* cookie-only worker on the same host. It checks the controller's managed-task list and durable uncertain requests, restores and verifies the new keyring cookie, stops the old IPC endpoint, and starts a replacement while retaining the original world/player lease. It does not replay any task; if the new IPC fails, the lease remains held for manual reconciliation. This is an **internal primitive**, not yet a GUI button or remotely callable operation; it does not alter independently running legacy workers.
