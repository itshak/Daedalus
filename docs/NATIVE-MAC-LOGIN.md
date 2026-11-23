# Native Mac Gameforge authentication — headless Selenium default, manual fallback

**Implementation:** automatic headless Selenium Chrome with one visible-browser retry on login failure; the older native Qt WebEngine browser remains an Advanced manual fallback. Both paths use one-use encrypted session handoff to the authoritative Linux game worker. Synthetic code and GUI tests passed. **Real Gameforge browser/CAPTCHA and dedicated-worker rebind acceptance remain owner-dependent, and are not certified by CI.**

**The historical native Qt WebEngine instructions below describe only the advanced manual fallback.**

### macOS Keychain and Chromium focus behavior

Daedalus distinguishes **two** independent Keychain operations:

- The genuine **macOS Keychain**, which protects saved Gameforge credentials,
  the API bearer and the Mac-only key used for encrypted login backups. The
  user may need to approve access per item, especially when changing to an
  ad-hoc-signed preview build. Daedalus now restores a valid exact-world legacy
  session first (without any Keychain read), avoids querying both credential
  and vault key records for a single login, and never re-encrypts an existing
  server vault merely because the user signs in again.
- **Chromium Safe Storage**, which is internal to Chrome and not needed for
  Daedalus's temporary browser. On macOS, Selenium uses a fresh owner-private
  profile and Chromium's documented test-only `--use-mock-keychain` switch
  to avoid repeated browser-side OS authorization dialogs. The profile is
  removed when the helper exits, and this switch must NEVER be applied to
  the operator's regular browser profile. The real Daedalus Keychain is still
  used to protect persistent secrets.

Chrome's visibility is also bounded: after the lobby Play click, Selenium
follows the game window without switching back to the lobby every poll,
and secondary windows are inspected at a lower frequency before Play. If
Gameforge changes its registration/login layout, Selenium waits for the
asynchronously rendered tab, uses its accessible text/attributes and, for a
two-tab control, can identify **Sign in** as the sole non-registration tab.
It must not select the first tab blindly or submit a password to the
registration form.

**Limit:** Apple Keychain's consent rules are controlled by macOS, not by
Selenium. An ad-hoc-signed preview cannot guarantee that "Always Allow"
persists across future rebuilds. Stable Developer ID signing and normal
notarized distribution remain the supported way to retain code identity
across releases; the application must not bypass OS approval for persistent
credentials.

### Server-side saved-cookie restart and actual Accounts status

The backend now supports **explicit read-only restoration of previously approved
native browser sessions** at daemon startup. Enable both
`--restore-saved-native-workers` and `--confirm-read-only-network` alongside
`--enable-native-browser-login` and a fixed `--accounts-file`. This attempts
one independent cookie-only IkaBot IPC worker per existing protected account
binding. Each worker must independently validate the exact game world/player
before Session or Worker can become connected. No lobby login, CAPTCHA,
password transfer or previous game task is replayed. Missing/expired cookies
remain disconnected, not reported successful. An existing independent worker
is never overtaken. The operator can disable this startup behavior by removing
the explicit restore flag.

The earlier cookie worker had a bug: its child called required credential-store
functions without their second argument. That prevented every worker from
starting despite verified cookies being stored. A regression now exercises the
real child entrypoint rather than mocking only process creation. The server
should log only sanitized worker exit codes and aggregate restore counts.

Desktop Accounts immediately shows the verified Session and Worker indicators
upon the backend's independently attested IPC worker receipt; it then refreshes
both state sources from the server. A verified cookie alone still does not
make an account connected. The Gameforge registration-first sign-in tab is
selected by the actual React-Bootstrap tab identity, not by assuming its
container is a `div` or asking the user to switch manually.

### Interpreting a successful browser sign-in

A Mac can restore a saved exact-world cookie and the server can independently
verify and save it. When the backend enables native Mac login, Daedalus also
starts an **isolated, cookie-only IkaBot worker** from the server's protected
binding; the child independently attests exact world/player over its private
IPC before either **Session** or **Worker** is shown connected. This action is
part of the operator's explicit Sign in / Load warehouses request: no loginLink,
password transfer, CAPTCHA bypass or background task replay is involved.
Multiple accounts have separate leased IPC children, with ownership checks.
If that second step fails, the cookie remains safely saved, but the desktop
shows **worker unavailable** and must never claim warehouse access. Older
backend versions still return a cookie-only receipt and require deployment
before worker connection becomes available. The Accounts refresh rechecks both
session and actual IPC worker attachment. Fluent notifications stack and stay
readable for two minutes unless closed manually.

When the server rejects an otherwise successful headless cookie handoff, the
client burns that ticket, requests a **new** account-scoped one-time challenge
and opens visible Chrome without replaying the rejected legacy cookie. This
interactive recovery is attempted at most once per selected account; a second
server rejection is terminal and surfaced to Activity. If the backend refuses
the new challenge (for example, an active/uncertain worker), no browser is
launched and the owner must reconcile the worker before retrying. Final
sign-in counts remain visible on Accounts after the activity finishes. The
Activity timeline uses reviewed, nonsecret stage and failure categories,
while raw browser exceptions, passwords, cookies and API bodies stay hidden.

For release preflight, use `daedalus doctor --smoke --deployment-check` on the Linux host. This reads no credential values or game pages and reports unresolved task receipts and evidence (not proof) of persistent keyring provisioning. See [owner-supervised Mac-first acceptance](LIVE-ACCEPTANCE.md) before restarting an existing worker.

## Automatic headless Gameforge sign-in (the prior warehouse-bot workflow)

**The normal path is now automatic Selenium Chrome, not a manual Gameforge browser.**
This is adapted from the original local warehouse bot in
[itshak/ikabot](https://github.com/itshak/ikabot): restore the previously saved
world session when available, otherwise enter Gameforge lobby using stored
email/password, select the game's play/world entry, and detect the exact-world
authenticated city UI. Selenium starts with **headless Chrome**. A visible
Chrome window is opened **when a CAPTCHA is detected or headless login
fails**, including rejected credentials, a changed form or a world timeout.
The operator can complete the challenge, correct the password or log in
manually in the visible window. Selenium then validates the exact selected
world and securely hands off only its world cookie. An invalid world, missing
credentials or cancelled login never initiates an unsolicited browser.
CAPTCHA is never solved or bypassed by software.

In Daedalus **Accounts**, select **Sign in automatically (headless)**, **Sign in
all accounts**, or **Choose sign-in accounts…**. The **Warehouses → All accounts**
button also checks which accounts lack verified sessions and attempts headless
sign-in for those accounts before collecting **one combined warehouse report**.
Already authenticated accounts require no new login. Existing island grouping,
220K filter, native Print preview and CSV/JSON/TXT exports remain unchanged.
All attempts are account-scoped, proceed sequentially and report errors
independently rather than aborting a full multi-account report. The native
**Activity** page now records the live login stages (helper start, saved-login
lookup, Chrome launch, lobby, form submission, world navigation, visible
fallback, error and handoff verification). **Diagnostics** opens a bounded
technical stream; the private macOS `~/Library/Logs/Daedalus/desktop.log`
also records sanitized stages. A browser/Keychain stall does not block the
GUI thread, and cancellation terminates the isolated browser process.
No credentials, browser session, cookie, or raw page exception is logged.

On the first use, Daedalus tries an exact account alias match in the previous
local bot's owner-owned `~/.ikabot/config.ini` and an unexpired, exact-world
session in `~/.ikabot/tokens.json`. Neither source is changed or copied into
Daedalus settings. Otherwise you supply your Gameforge email/password **once**
through a secure Mac form, and can save them to **macOS Keychain**, bound to
the exact backend HTTPS origin, account ID and world. Subsequently those
credentials are reused automatically and no password input is needed until
they are unavailable or changed. When opted in, a client-sealed copy is also
stored persistently on the server and can be restored by the originating Mac.
The **plaintext password never leaves the Mac**, and the API never returns it.
See [the encrypted login vault](LOGIN-VAULT.md) for key-loss limitations.

After login, the Mac extracts **only the exact world's secure `ikariam`
cookie** and uses the existing single-use, account/world/player-bound
X25519/AES-GCM handoff. The authoritative backend independently verifies the
game identity, respects active task/uncertain-request ownership and accepts
or rejects the new session. It does not start game tasks. For emergencies,
**Manual browser fallback** is available under Advanced recovery; it is not
the ordinary sign-in flow.

**Scope and acceptance:** This requires a trusted HTTPS Daedalus connection,
backend native browser handoff enabled, Chrome/Selenium on the Mac and
account-scoped Gameforge credentials or a matching legacy configuration.
Source code and synthetic tests do not establish that a live Gameforge
CAPTCHA, 2FA prompt or world selection currently succeeds. The owner will
perform actual account tests separately; no live credentials or game traffic
were used during implementation.

## What the operator sees

1. Install a fresh Daedalus.app preview with the native browser dependency included, then connect to a trusted **HTTPS** Daedalus server. The Mac securely remembers the API token in Keychain. An administrator must opt in to backend native browser login first.
2. In **Accounts**, select the exact world/player and click **Sign in on this Mac**. Read the confirmation carefully. The server checks account ownership and, for an already-running dedicated worker, requires it to be idle and have no unresolved/uncertain task request. When appropriate, it pauses the original session under the same lease; it never starts a second worker or a task.
3. A temporary, off-the-record Mac browser opens only official HTTPS Gameforge top-level pages. **You** enter your credentials and complete MFA/CAPTCHA. Daedalus does not automate those steps or access them. Open the matching game world with the button in the dialog. Sign-in flow and supported third-party challenges depend on Gameforge's current site and have not been accepted against a live account yet.
4. Click **Check signed-in session**. Daedalus accepts only one secure `ikariam` cookie scoped to the configured world's exact `sNNN-xx.ikariam.gameforge.com` host. It rejects parent-domain, lobby, other-world, insecure and noncanonical cookies. If this is the first binding for an account, optionally enter the saved Gameforge identity email; never enter a password in this extra field.
5. Check the authorization box and click **Verify session on server**. The Mac generates a one-time ephemeral Curve25519 key, encrypts the selected world cookie (and optional binding email) with AES-GCM using the server's one-time public key and exact account/world/player/ticket as authenticated context. Only the resulting ciphertext, ephemeral public key and nonce travel through the bearer-authenticated, TLS-verified API. No plaintext cookie, email, password, CAPTCHA answer, browser profile or lobby token is sent in an HTTP field or saved to Mac preferences.
6. The Linux backend consumes the challenge once and independently performs a fresh cookie-only game-world identity verification. If no worker exists, it stores the verified session only in its protected OS keyring and **does not automatically start a worker**. If the exact dedicated worker owns that account, it stages the cookie in its protected OS keyring, checks its task ledger/lease and independently verifies the actual rendered player and world before switching the single IPC owner. No old task is automatically resumed.
7. On cancellation, expiration, wrong identity, Keychain failure or uncertain IPC replacement, Daedalus refuses to assert login success. A paused worker remains held for manual recovery; start a new login/reconcile safely. The old verified world-cookie binding is not overwritten on a failed identity check. Manual host-only fallback remains available to operators, but is **not the default Mac workflow**.

## Deployment

The fixed-account Linux backend must be started by its administrator with:

```text
--accounts-file /private/accounts.toml
--connect-existing-ipc --enable-task-control
--monitor-existing-sessions
--restore-saved-account ACCOUNT_ID --confirm-read-only-network
--enable-native-browser-login
```

For an existing saved IkaBot identity with no active worker, `--accounts-file` and `--enable-native-browser-login` enable the explicit Mac sign-in path; native login also enables the server's account-scoped read-only IPC router. The backend must have its server and maintained IkaBot engine dependencies installed, and a server-side protected keyring available to its daemon. The newly verified cookie now boots an independent dedicated account worker after an explicit Mac sign-in, without requiring a second manual worker-start command. If the worker cannot start, the client reports this failure instead of presenting a false successful warehouse login. **A completely new Gameforge/IkaBot identity without an existing compatible saved IkaBot record is not yet certified in the real game**; synthetic first-time binding tests are insufficient evidence. No new daemon, Gameforge lobby login, Mac SSH tunnel or VNC session is needed for the browser experience. Keep the backend bound to loopback behind an authenticated HTTPS ingress; see [REMOTE-HTTPS.md](REMOTE-HTTPS.md). `daedalus[server]` includes cryptography and OS keyring dependencies; the native `.app` includes Qt WebEngine and its subprocess. Use a protected Linux keyring or the [machine-bound systemd encrypted credential store](PERSISTENT-CREDENTIALS.md) for a headless daemon; a controlled service restart has passed on `aiserver`, while whole-host reboot still needs owner acceptance.

**A running dedicated backend must be restarted to apply the opt-in flag and new code.** That restart can invalidate its lease/session and is **not** safe during an active task or uncertain request. Do not restart the current Monjo owner until its preexisting unconfirmed task request has been investigated and the operator has approved a controlled window. A source-code merge alone does not enable the new GUI button on an older live server.

## Threat model and limits

- The secure API bearer still authorizes privileged account control. Use HTTPS with normal certificate validation, rate limiting/access policy, and protected macOS Keychain. A stolen bearer permits API calls; encrypted handoff protects in-transit session material from ordinary application/log access but cannot defend against a fully compromised authorized client/server or malicious API endpoint with the bearer.
- Encrypted session transfer is a **narrow exception** to the historical policy prohibiting raw cookies in APIs: no plaintext world cookie or password upload endpoint is provided. A single-use short-lived account-bound challenge is mandatory; the backend never returns decrypted material.
- The Mac GUI uses an off-the-record embedded Qt WebEngine profile and explicitly destroys the browser page before its profile; browser authentication data is not persisted to the Mac's browser profile. Qt renderer subprocess security remains platform-specific. Gameforge may introduce new sign-in domains, popups or CAPTCHA providers requiring a reviewed allowlist change; do not automatically allow arbitrary top-level sites.
- Host-local leases **do not prevent** a different computer from independently logging into the same game account. Preserve the one-authoritative-worker operational policy.
- Offline tests cover ciphertext tampering, expiry, replay, consent, wrong-world/player verification, email mismatch, running/uncertain tasks and worker rebind. They cannot prove real CAPTCHA/login success, current player-page markup compatibility, or durable Secret Service persistence after reboot.

## Acceptance owner checklist (still open)

- [ ] On an authorized isolated test account, sign in using the **Mac** embedded browser and complete any real CAPTCHA/MFA.
- [ ] Verify first-time world-cookie binding, expired-session detection and independent server-rendered player attestation.
- [ ] Verify worker idle/uncertain-task interlocks, dedicated rebind and exact one-owner lease through a real session renewal, without duplicate game actions.
- [ ] Confirm a single newly approved reversible task, monitor/stop it, and observe game-side effects exactly once.
- [ ] Restart in a controlled window and verify protected server keyring availability, client Keychain auto-reconnect, and no VNC/SSH requirement.
- [ ] Review sanitized evidence and explicitly authorize or refuse production cutover. **Do not mark production-ready from CI alone.**
