# Human browser recovery (offline-verified implementation)

Daedalus provides two **opt-in** local paths, neither of which collects passwords or solves CAPTCHA:

- `daedalus sessions assist-browser-login ACCOUNT_ID --config /private/accounts.toml --confirm-read-only-network` opens the official lobby in the system browser and accepts a manually copied **world** `ikariam` cookie through an echo-free terminal prompt.
- `daedalus sessions assist-playwright-login ACCOUNT_ID --config /private/accounts.toml --confirm-read-only-network` opens an **ephemeral, visible Chromium browser**. The operator logs in, solves any challenge, and navigates to the configured world. After typing `YES` in the original terminal, Daedalus reads only the secure `ikariam` cookie scoped to the exact world host. No cookie appears in terminal input, API requests, logs or browser-profile files.

For Playwright, install `pip install -e '.[browser-recovery]'` and `python -m playwright install chromium` on the same authorized host. Bind the existing saved IkaBot email first using `sessions bind-email ACCOUNT_ID`. Both paths require an interactive local terminal, protected OS keyring, canonical world, account-owner lease and explicit network consent. The game engine validates the cookie with a read-only world request and verifies its configured world/player before storing it. The browser closes, and the lease is released after verification. Neither path starts a second game worker.

**Remote deployment fallback:** use a trusted, authenticated graphical remote-desktop session *on the authoritative worker host*, then run `assist-playwright-login` in a terminal there. This keeps browser, cookie and keyring on the same host. Do not use a public VNC server, upload browser profiles or tunnel cookies through the Daedalus API. The Daedalus HTTP API intentionally does not provide a remote cookie-upload endpoint. An SSH terminal without a graphical browser can instead use `assist-browser-login` only if a trusted local browser on that same host is available.

**Updated offline scope:** Both cookies-only restoration and existing-worker
active validation now require a recognizable **server-rendered current-player
name** on a fresh TLS-verified, nonredirecting game-world response matching the
configured account. Saved IkaBot usernames and HTTP 200 alone do not prove
which player the world cookie represents. An unfamiliar game-page layout
fails closed and needs a reviewed adaptation; this is not yet proven against
a real Gameforge account.

An already-owned **dedicated** cookie-only worker supports a separate
host-local recovery procedure. The remote Mac desktop can select
*Host recovery instructions* and *Prepare idle worker recovery*, which
creates a short-lived nonsecret assistance ticket and blocks new game work.
The operator must use a trusted graphical terminal on the **authoritative
worker host**, under the same OS user, to run:

~~~
daedalus sessions stage-playwright-login ACCOUNT_ID --config /private/accounts.toml --confirm-read-only-network
~~~

(Or use `stage-world-cookie` with the same flags for a hidden local
terminal cookie prompt.) The official browser login and CAPTCHA are entirely
human-operated. New cookies are staged in a **separate, unverified** OS-keyring
entry and cannot start an authenticated worker.

Back in the desktop, choose *Check login assistance*, *Confirm manual step
complete*, then *Verify staged cookie and rebind worker*. The backend checks
the same owned world/player lease, ticket and absence of active/uncertain
tasks; verifies the staged cookie; replaces only the managed dedicated IPC
endpoint; and performs a new read-only independent server-side player check.
No cookie crosses the controller API, and no game task is automatically
replayed. Uncertain IPC restart retains the lease for manual reconciliation.

Unused staging may be cleared on the worker host with
`daedalus sessions discard-staged-cookie ACCOUNT_ID --config /private/accounts.toml`.
This does **not** create a new saved IkaBot identity, hot-swap an arbitrary
legacy session, or authorize the production bot installation. See
[LIVE-ACCEPTANCE.md](LIVE-ACCEPTANCE.md) for the owner test procedure.

## Offline verification

`tests/test_browser_recovery.py` exercises account locking during human interaction, explicit consent, exact origin/world cookie selection, cleanup, keyring persistence only after engine validation, and rejection of invalid or mismatched sessions using a fake browser. No Gameforge requests or real credentials are used. The optional Playwright test has also been executed against a locally installed headless Chromium browser with all page traffic intercepted and synthetic cookie isolation: **7/7 browser recovery tests passed**. This verifies actual Chromium cookie-domain isolation, **not** Gameforge compatibility or real login.


## Dedicated-worker rebind API (offline-verified opt-in integration)

`SavedCookieWorker.recover_from_verified_cookie(..., require_staged=True)`
is now routed through a trusted monitor and bearer-protected, nonsecret API
recovery preparation and approval. Only the existing dedicated lease owner
can promote a world cookie, after independent game-world player attestation.
Worker recovery checks the engine task list and durable dispatch ledger before
restarting the isolated IPC endpoint. A failed/uncertain replacement retains
ownership and cannot trigger automatic task replay. The HTTP API never
receives a cookie or password and does not control a browser remotely.
