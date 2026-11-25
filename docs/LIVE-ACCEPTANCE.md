# Owner-supervised real-account acceptance — Mac-first

**Status (2026-11-19): release implementation merged, final live acceptance blocked.** Native macOS Gameforge login and one-use encrypted session transfer are merged in [PR #57](https://github.com/itshak/Daedalus/pull/57). Synthetic tests, a separate Linux daemon with native-login enabled, and authenticated real Monjo read-only warehouse requests passed. A real Mac Gameforge/MFA/CAPTCHA browser login, live dedicated rebind, game-changing task trial and reboot durability were **not** completed. Never label the app production-ready on synthetic evidence alone. The completed `validate-live-authentication` **implementation** OpenSpec record
is archived. Owner-only acceptance remains open in
[issue #60](https://github.com/itshak/Daedalus/issues/60), and production
cutover has **not** been approved.

## A. Preflight: no game effects

1. Obtain the Mac preview from the successful macOS CI build for [PR #57](https://github.com/itshak/Daedalus/pull/57). It includes Qt WebEngine. Verify you installed the **new** app, not an older preview.
2. From the Linux backend host, use `daedalus doctor --smoke --deployment-check --protected-store-directory /private/encrypted/store` before changing the service. The `--smoke` part uses only in-process fake accounts; `--deployment-check` reads private local keyring **metadata** and task-ledger **status counts**, not passwords, cookies, email or task payloads. No network to Gameforge, no API token, no user secrets. It **cannot** approve production on its own. Use `--task-ledger /private/ledger.sqlite3` only if the service has a custom ledger; never put secrets in arguments.
3. If `deployment_preflight.task_ledger.status` is `unresolved`, verify the real engine and game state *outside* this command and reconcile the exact request only after establishing what happened. Never auto-clear or replay an `unconfirmed` request. If `keyring_durability` reports `volatile_session_only_or_unprovisioned`, first provision a reboot-persistent, protected server keyring. `encrypted_collection_file_present_unverified` or `host_encrypted_collection_present_unverified` only means a protected file exists, **not** that the service can unlock it after restart. Use the opted-in [systemd encrypted credential store](PERSISTENT-CREDENTIALS.md) for a headless worker; never migrate credentials without independent player verification.
4. Back up the private backend configuration, owner-only request ledger and existing keyring through your trusted secure backup process. Preserve account identity and restore paths. Do not export the cookie or keyring contents into the repository, HTTP API, issue tracker or logs. Ensure the same world/player is not running in an independent legacy bot (the lease guard is host-local only).
5. **Host remediation completed on 2026-11-19:** the exact stale `alertAttacks` request was examined against the engine (no running tasks, no task ID/PID) and marked `operator_reconciled` through the authorized API, preserving a private 0600 backup and an audit record. Its result is **not** assumed to be a successful game action. Monjo's saved account binding and independently reverified world cookie were sealed into a new 0700/0600 AES-GCM store using a root-owned host-encrypted systemd credential. A transient service verified actual decryption under `User=debian`. The live Daedalus service was restarted under the new configuration, `--enable-native-browser-login` was enabled, and its VNC unit dependency removed. Fresh API checks confirmed the authenticated Monjo identity, seven warehouse cities, zero managed tasks, zero unresolved requests, healthy HTTPS and a tokenless 401. An initial restart exposed a monitor-attachment ordering bug; that was fixed and protected with an integration regression test. **The full physical-host reboot, real Mac Gameforge/MFA/CAPTCHA sign-in, live rebind and task trial remain open owner-acceptance checks.**

## B. Enable the native Mac login endpoint in a controlled window

Once the exact account is idle and earlier uncertain operations are reconciled, the operator can schedule a controlled service restart. Use the fixed-account service's existing flags and additionally enable `--enable-native-browser-login` (requires installed backend revision, `cryptography`, and working protected OS keyring). Preserve `--connect-existing-ipc --enable-task-control --monitor-existing-sessions --restore-saved-account ACCOUNT --confirm-read-only-network` if the service owns an already verified dedicated worker. Keep the API bound to `127.0.0.1` behind the authenticated HTTPS origin; do **not** publish the daemon port, disable TLS, or add a second owner for Monjo.

Do **not** turn a live restart into an account-recovery experiment. Check `systemctl is-active daedalus.service`, authenticated backend session and accounts, then verify `/api/v1/native-browser-login` reports `enabled: true`. If the stored cookie has expired, a controlled restore may fail closed: perform the supervised login procedure rather than weakening identity checks. Do not make this change during a game task or while the request ledger is uncertain.

## C. Owner's native Mac sign-in (no SSH or VNC)

1. Open Daedalus.app → **Connection**. Connect to the trusted HTTPS Daedalus hostname (for the current installation: `https://daedalus.tongrix.com`). Paste the **Daedalus API access token**, not a Gameforge lobby token. Mac Keychain saves the token by default after a successful handshake and auto-reconnects to that exact HTTPS origin thereafter. No Mac-side SSH forwarding, VNC server or Terminal is needed.
2. Open **Accounts** and select only the explicitly authorized test world/player. Click **Sign in on this Mac**. The server must have native login enabled, and any dedicated worker must be idle, without `unconfirmed` or `dispatching` task requests. Otherwise the button will fail closed with a nonsecret reason.
3. In the isolated, off-the-record Mac browser, manually complete Gameforge login and any MFA/CAPTCHA. Open the **exact configured game world** using the dialog action, then click **Check signed-in session**. Daedalus extracts only the secure, exact-world `ikariam` cookie, never the password, MFA response, challenge answer or lobby token.
4. Approve **Verify session on server**. The Mac encrypts the world cookie in memory with the server's one-use X25519/AES-GCM challenge bound to the exact account/world/player and submits the ciphertext over authenticated HTTPS. The Linux worker independently fetches a fresh TLS-verified game-world page and verifies the **actual rendered player**. Wrong account, missing player marker, redirect, expired session or stale ticket fails closed. No plaintext game cookie is accepted by ordinary API fields or printed.
5. If the account already has a dedicated worker, it may rebind only if idle under the same exclusive lease. It must not start a new game-changing task or automatically retry a previous one. If this is a **first binding with no dedicated worker**, success stores a verified world session but **does not automatically start** a dedicated worker. The underlying engine also requires a compatible previously saved IkaBot account association; brand-new Gameforge account provisioning is not implemented by cookie exchange alone.
6. Open **Warehouses**, fetch that account, and compare city names/resources to the game. Expire a **separate isolated test session** (not the production worker) and confirm tasks fail closed until a new manual Mac login. Re-run recovery once to confirm no duplicate worker or replayed operation.

## D. One approved task trial and restart durability

On an isolated owner-authorized game account only, choose a reversible background automation from the guided GUI, inspect native parameter controls and read-only prerequisites, and explicitly approve **one new request**. Verify its task ID and real game effect once, then use the application's managed-task Stop and refresh actions. Never send an old idempotency ID with altered parameters, retry an unknown/timed-out request, or terminate an unrelated tmux worker/PID. Record only sanitized statuses, timestamps and counts.

In a separate controlled window, restart the host/service after persistent keyring provisioning and verify the same bound email/world cookie is usable **without a new manual credential entry** (subject to game session validity), the Mac Keychain reconnects to HTTPS automatically, and the worker passes fresh server-side player attestation. An in-memory session collection is insufficient for this step; machine-bound encrypted credentials are now configured and a normal Daedalus service restart has passed, but a full host reboot remains untested. If keyring unlock fails, leave worker/task ownership blocked and restore from the approved secure mechanism; do not use plaintext secret files as a fallback.

## E. Sanitized owner acceptance record

Record each row as `pass`, `fail` or `not-tested`, including the UTC timestamp, app/backend version, test account label, expected/observed nonsecret result and error category. Never include real emails, passwords, cookies, private HTML/screenshots, bearer tokens or request headers. The owner, **not CI**, must approve production cutover after all of these hold:

- [ ] New native Mac CI preview and updated backend are installed; native login capability is enabled
- [ ] Approved isolated test account has a valid saved IkaBot identity, no second active owner and no uncertain requests
- [ ] Real Gameforge Mac browser sign-in, MFA/CAPTCHA if present, and encrypted handoff succeeded
- [ ] Fresh independent game-world player attestation and read-only warehouse comparison passed
- [ ] Expired/wrong-player session and unauthorized requests fail closed
- [ ] Idle dedicated-worker rebind preserved the same lease, with no duplicate worker or task replay
- [ ] One explicit reversible game task was started/observed/stopped exactly once
- [ ] Protected Linux keyring survives a controlled service/host restart, and Mac Keychain auto-reconnects
- [ ] No credentials leaked into API/logs/repository; production and other bots unaffected
- [ ] Owner explicitly approves production cutover with sanitized evidence

**Unverified statuses must not be checked off.** Record owner results on
[issue #60](https://github.com/itshak/Daedalus/issues/60) without any secrets.
The archived implementation OpenSpec record does not close this checklist or
authorize cutover. Manual login, approval and observation of real game effects
cannot be replaced with an automated simulation.

Owner update (2026-11-26): manual Mac installation/UI and live-account checks for the cross-platform parity milestone are deferred to issue #60, not marked passed. Automated CI, packaging and safe deployment checks remain required.
