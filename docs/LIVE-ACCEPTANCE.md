# Owner-supervised isolated real-account acceptance

**Status: a limited, owner-authorized live smoke passed saved lobby-session renewal, independent world-player attestation, and read-only city/warehouse reporting on one isolated account. Manual browser/CAPTCHA login, live rebind/expiration behavior, and real task dispatch have NOT been accepted.** This is the test plan for the remaining active OpenSpec proposal `validate-live-authentication`. It does not authorize production cutover or modification of an independently running IkaBot instance.

## 0. Preconditions and hard safety boundaries

Use a **separately authorized test game account**, an isolated OS user/host, and a private account metadata file. Preserve the production IkaBot processes, tmux sessions and account state. Do not run two IkaBot owners for the same world/player, even on different hosts: Daedalus's lease is host-local, not distributed.

You need a saved IkaBot identity record for the exact test world's player under this isolated OS user's IkaBot installation. Daedalus's cookie-only restoration **does not register a brand-new Gameforge/IkaBot identity**; it reuses an existing saved IkaBot account association. A valid browser cookie alone does not create this record. If no such saved identity exists, do not borrow the running production account's live session: report **blocked: test account not provisioned** and arrange first-time, isolated upstream provisioning.

Every new browser login/CAPTCHA is manually performed by the account owner on the **authoritative worker host**. Daedalus does not ask for Gameforge passwords or solve CAPTCHA. Never place password, lobby token, cookie, browser profile or screenshot of secrets in an API, GitHub issue, TOML file, terminal command arguments or uploaded logs. The desktop may be on a separate Mac; the graphical browser and OS keyring must be on the **same OS user and host that runs the worker**.

The source combines public IkaBot 7.7.2 and still-proposed CLI/IPC PR #499. This is a test preview, not a published stable release, and the Mac `.app` preview is ad-hoc signed and unnotarized. Do not bypass platform safety warnings on an untrusted download.

## 1. Set up the isolated authoritative worker host

From a clean Daedalus checkout of the finished PR (prefer `main` after the protected CI merge):

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev,server,desktop,browser-recovery]"
python -m pip install -e ./engine/ikabot
python -m playwright install chromium
daedalus doctor --smoke
```

If the worker host is headless, use a trusted authenticated graphical desktop session on that **host**, not a separate browser on the client computer. Playwright Chromium needs a working GUI for human login; do not invoke a fake headless game login.

Create your **private** account metadata outside the Git checkout, for example `~/.config/daedalus/accounts.toml`:

```toml
schema = 1

[[accounts]]
id = "test-alpha"
world = "s301-en"
player = "EXACT_TEST_PLAYER"
label = "Isolated test account"
enabled = true
```

Replace `s301-en` and `EXACT_TEST_PLAYER` with the actual authorized test-world/player pair. The `id` is your local, nonsecret alias. Never add an email, token or password to TOML. Before proceeding, make sure the same exact account is not currently owned by a production bot, another Daedalus backend or a separate host.

Use the protected **host-local terminal** to bind the existing saved IkaBot email:

```bash
daedalus sessions bind-email test-alpha --config ~/.config/daedalus/accounts.toml
```

This prompts with no echo and stores the association in the OS keyring. It does not create an IkaBot saved identity. To validate an already saved world cookie before starting the worker, optionally run:

```bash
daedalus sessions probe-saved-cookies test-alpha --config ~/.config/daedalus/accounts.toml --confirm-read-only-network
```

If the saved world cookie is unavailable or expired, on this same trusted **host graphical session** use:

```bash
daedalus sessions assist-playwright-login test-alpha --config ~/.config/daedalus/accounts.toml --confirm-read-only-network
```

Complete the login, any challenge, and navigate to the exact world. Type `YES` at the terminal only when finished. The ephemeral browser reads a secure `ikariam` cookie for the exact world; the engine makes one TLS-verified, **nonredirecting** read-only world request. A fresh server-rendered player name must match the configured player; a mere saved username is insufficient. Only then does Daedalus store the verified cookie to its protected OS keyring.

If the page markup lacks the currently supported `avatarName`/`playerName` identity marker, validation will deliberately **fail closed**. This might be a legitimate site-layout change; report `player_attestation_unrecognized` (without uploading the HTML or cookies), and the code will need a reviewed markup adaptation. Do **not** disable attestation to bypass it.

## 2. Start one isolated cookie-only worker and backend

On the authoritative host, create the API bearer token privately in your shell (do not commit or transmit it in a URL):

```bash
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"

daedalus serve \
  --host 127.0.0.1 --port 8765 \
  --accounts-file ~/.config/daedalus/accounts.toml \
  --connect-existing-ipc --enable-task-control \
  --monitor-existing-sessions \
  --restore-saved-account test-alpha --confirm-read-only-network
```

This explicitly starts **one** dedicated worker from a verified saved world cookie. It refuses another IPC owner, holds the account lease, and does not perform a Gameforge loginLink or replay any task. The same user must own the account binding and IPC descriptor.

On a local Mac, launch `daedalus-desktop` or the CI-built Daedalus.app preview. On another computer, use an authenticated SSH port-forward (e.g. `ssh -L 8765:127.0.0.1:8765 HOST`, with `HOST` replaced by your trusted worker host). Connect the desktop to `http://127.0.0.1:8765` through that tunnel, using the API bearer token. Remote direct HTTP and public VNC servers are not supported.

## 3. First healthy read-only checks

In **Accounts**, refresh and verify that the test account's world/player and session phase match. Click **Check IkaBot sessions**, then **Monitor verified session** if appropriate. In **Warehouses**, retrieve a snapshot for only this account, and compare the city names/resources with the game manually, without taking screenshots of sensitive browser content.

Expected: account identity is independently attested from the actual server page; the backend displays no cookies or game tokens. If the game layout has changed, the account remains unverified and no task starts.

## 4. Test the explicit, host-local human recovery and dedicated rebind

Do this only **when no game-changing task is running**. In the desktop **Accounts** view, select the test account and click **Host recovery instructions**, then **Prepare idle worker recovery**. Confirm. The backend checks the engine task list and durable ambiguous requests and refuses if any are running/uncertain; it creates a short-lived nonsecret assistance ticket and blocks new tasks.

In a trusted graphical terminal on the **authoritative worker host** (same OS user), stage a newly authenticated cookie:

```bash
daedalus sessions stage-playwright-login test-alpha --config ~/.config/daedalus/accounts.toml --confirm-read-only-network
```

Manually complete the browser login and challenge. Alternatively, if the operator already has a game-world `ikariam` cookie on this very host, run `sessions stage-world-cookie` with the same flags and paste it into the **echo-free terminal prompt**. The staged cookie is **UNVERIFIED**, separate from the active cookie, and cannot start a worker by itself.

Return to the native desktop. Click **Check login assistance**, **Confirm manual step complete**, then **Verify staged cookie and rebind worker**. The backend uses the still-owned lease, rejects active/uncertain tasks, validates the staged cookie with the exact game world and actual player marker, replaces its dedicated IPC worker, and performs a **second** fresh existing-session verification. Only then can it report `worker_recovered_verified`.

Expected: no cookie crosses the HTTP API or the client Mac; exactly one dedicated IPC owner remains; the old game session is closed without logout; account lease is retained; no task is automatically repeated. If verification fails, the old IPC is preserved if possible; if IPC shutdown/restart is uncertain, the account remains locked for manual reconciliation.

To discard an unused staged cookie, run on the **host only**:

```bash
daedalus sessions discard-staged-cookie test-alpha --config ~/.config/daedalus/accounts.toml
```

## 5. Test one explicitly confirmed NEW game task

Only on the isolated account, when the server-side identity is verified and the new IPC is stable: inspect the current managed-task list, select a harmless/reversible registered background task, review its validated parameters, and consciously approve **one** request with a fresh UUIDv4. Record only the nonsecret request ID and result status. Do not replay a timed-out request; uncertain dispatches require manual inspection and reconciliation. Confirm stop/list behavior, but never terminate a task from another account or an arbitrary PID.

Compare game-side effects **once** with the expected task action and confirm no duplicate execution after a retry, refresh or recovery. Do not assert success merely because an API returned HTTP 200.

## 6. Record sanitized acceptance evidence

Fill this checklist locally or send the statuses in a reply. Do not attach cookie values, page HTML, real email, passwords, authorization headers, raw screenshots, or private log files.

- [ ] Backend and Mac desktop preview launched; `daedalus doctor --smoke` passed
- [ ] Exact authorized test world/player and existing saved identity provisioned
- [ ] Official human browser login and any CAPTCHA completed successfully
- [ ] Read-only cookie restoration passed **independent server player attestation**
- [ ] Accounts, city/warehouse reports and session status match the test game
- [ ] Idle dedicated worker recovery ticket created; live active-task conflicts rejected
- [ ] Host-only staging, manual approval and dedicated worker rebind succeeded
- [ ] Expired session correctly blocks new tasks; retry/invalid player fails closed
- [ ] Exactly one new explicitly approved task ran, without duplicate side effects
- [ ] No cookies or credentials crossed API/logs; production worker remained unchanged
- [ ] Owner reviewed sanitized evidence and explicitly approved or refused production cutover

A useful report contains the **step number, observed nonsecret status, expected status, and a sanitized error category**. Report failures even if a later retry worked, as well as environment/version and whether the host was macOS/Linux. The OpenSpec real-account gates stay unchecked until this evidence is supplied. No production cutover is authorized by this document or by passing CI.
