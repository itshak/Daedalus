# Native Mac Gameforge authentication — headless Selenium default, manual fallback

**Implementation:** automatic headless Selenium Chrome with CAPTCHA-only visible handoff; the older native Qt WebEngine browser remains an Advanced manual fallback. Both paths use one-use encrypted session handoff to the authoritative Linux game worker. Synthetic code and GUI tests passed. **Real Gameforge browser/CAPTCHA and dedicated-worker rebind acceptance remain owner-dependent, and are not certified by CI.**

**The historical native Qt WebEngine instructions below describe only the advanced manual fallback.**

For release preflight, use `daedalus doctor --smoke --deployment-check` on the Linux host. This reads no credential values or game pages and reports unresolved task receipts and evidence (not proof) of persistent keyring provisioning. See [owner-supervised Mac-first acceptance](LIVE-ACCEPTANCE.md) before restarting an existing worker.

## Automatic headless Gameforge sign-in (the prior warehouse-bot workflow)

**The normal path is now automatic Selenium Chrome, not a manual Gameforge browser.**
This is adapted from the original local warehouse bot in
[itshak/ikabot](https://github.com/itshak/ikabot): restore the previously saved
world session when available, otherwise enter Gameforge lobby using stored
email/password, select the game's play/world entry, and detect the exact-world
authenticated city UI. Selenium starts with **headless Chrome**. A visible
Chrome window is opened **only when an actual CAPTCHA is detected**, so the user
can solve it; Selenium resumes navigation itself. A wrong password, missing
browser, timeout or world mismatch does *not* open a random visible browser.
CAPTCHA is never solved or bypassed by software.

In Daedalus **Accounts**, select **Sign in automatically (headless)**, **Sign in
all accounts**, or **Choose sign-in accounts…**. The **Warehouses → All accounts**
button also checks which accounts lack verified sessions and attempts headless
sign-in for those accounts before collecting **one combined warehouse report**.
Already authenticated accounts require no new login. Existing island grouping,
220K filter, native Print preview and CSV/JSON/TXT exports remain unchanged.
All attempts are account-scoped, proceed sequentially and report errors
independently rather than aborting a full multi-account report.

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

For an existing saved IkaBot identity with no active worker, only `--accounts-file` and `--enable-native-browser-login` are needed, with the server optional dependencies installed. **A completely new Gameforge/IkaBot identity without an existing compatible saved IkaBot record is not yet provisioned by this flow**: the underlying cookie-only IkaBot engine still requires an existing account association. Do not represent synthetic first-time email-binding tests as proof of full new-IkaBot-account enrollment. After a verified first-time Mac login, the operator must explicitly start/attach one dedicated worker in a controlled rollout. No new daemon, Gameforge lobby login, Mac SSH tunnel or VNC session is needed for the browser experience. Keep the backend bound to loopback behind an authenticated HTTPS ingress; see [REMOTE-HTTPS.md](REMOTE-HTTPS.md). `daedalus[server]` includes cryptography and OS keyring dependencies; the native `.app` includes Qt WebEngine and its subprocess. Use a protected Linux keyring or the [machine-bound systemd encrypted credential store](PERSISTENT-CREDENTIALS.md) for a headless daemon; a controlled service restart has passed on `aiserver`, while whole-host reboot still needs owner acceptance.

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
