# Daedalus native Mac quick start (guided preview)

The native application controls an authenticated Daedalus backend. Its Mac Selenium browser signs into Gameforge automatically when needed; the authoritative Linux worker alone owns game tasks and independently verifies sessions. No game automation starts merely by connecting or opening a page.

## Connect directly over HTTPS — no SSH needed

1. On your Mac, launch Daedalus and open **Connection**. Enter the private controller's **HTTPS address** provided by your backend administrator, such as `https://your-daedalus-server.example`. The server may use Cloudflare Tunnel, another trusted HTTPS gateway, or an existing private network to expose a stable hostname, but it must require valid TLS and the backend's own API authorization.
2. Paste the **Daedalus API access token** once. This is **not** the Gameforge `gf-token-production` or any Ikariam password; do not substitute those credentials.
3. Leave **Save token securely in Keychain and reconnect on startup** checked (the default), then click the main **Connect** button. After the authenticated handshake succeeds, the app stores the bearer token **only in the OS Keychain**, and the validated server URL in a private preferences file. No token is written to plaintext configuration.
4. Next time, Daedalus automatically reconnects to that previously approved HTTPS server using the saved Keychain token. The **Reconnect saved server** button is also available. If the Keychain is locked or the server cannot be reached, unlock or troubleshoot it normally; the game does not start any new task on reconnect.
5. **Forget saved access** deletes the private URL preference and the corresponding keychain credential. If you change HTTPS server addresses, enter the token again: Daedalus deliberately does **not** forward credentials from one origin to another.

An existing local backend can still be reached through `http://127.0.0.1:8765` for testing; only loopback HTTP or trusted HTTPS is permitted. The optional SSH fallback and synthetic demo are under **Show advanced connection options**, not part of normal use. The app never disables TLS verification or silently converts a saved SSH connection into an HTTPS credential. A public hostname without backend authentication is **not** a supported deployment.

Server operators: see [private-origin HTTPS deployment](REMOTE-HTTPS.md). The service can remain bound to `127.0.0.1` while the gateway supplies a publicly trusted certificate and HTTPS address.

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
through a secure Mac form, and can save them to **macOS Keychain plus an encrypted
server backup**, bound to the exact backend HTTPS origin, account ID and world.
The server stores only encrypted material and cannot reconstruct the password
without the same Mac's Keychain vault key. The **Accounts → More → Back up
saved logins to server** action can migrate previously saved Mac logins. Subsequently those
credentials are reused automatically and no password input is needed until
they are unavailable or changed. They never leave the Mac for the Daedalus API.

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

## Advanced manual browser fallback

For exceptional situations, expand Advanced recovery in Accounts, select the world/player and click **Manual browser fallback**. An isolated native Gameforge browser opens in the app. Complete your Gameforge login and any MFA/CAPTCHA yourself, open the selected world, then approve **Verify session on server**. The session is encrypted for a one-time HTTPS handoff; the backend independently checks the game-world player before it will accept the cookie. No host-side browser, VNC or SSH is involved. If the button is disabled, the currently connected backend has not yet been started with the optional `--enable-native-browser-login` flag, or the account is disabled. Do not restart a production worker while it has uncertain tasks. See [native Mac login and acceptance boundaries](NATIVE-MAC-LOGIN.md).

## Find and manage accounts

The **Home** dashboard prioritizes a currently authenticated account and offers clear shortcuts to **View warehouses**, **Manage automations** and **View accounts**. The Accounts page shows connection/recovery status. Opening Accounts or Warehouses never starts tasks.

## Run an automation without writing JSON

1. Open **Home → Manage automations** for an authenticated account or navigate to **Automations**.
2. Filter by category or search by friendly name. For example, **Attack alerts** corresponds to the engine's `alertAttacks` task. **Explore** shows all operations; select a supported background task and click **Configure selected automation** to jump to its guided setup. Interactive-only operations are not misrepresented as runnable.
3. Read the readiness notice. The Mac asks the backend to check known nonsecret prerequisites against the selected authenticated engine session before Start becomes available. Three alert tasks require notifications to be configured in the existing IkaBot account. Those alerts will show **Needs setup: Telegram or Discord** and disable Start until that prerequisite passes.
4. Adjust form fields (integer and numeric settings use spinboxes, options use checkboxes, more complex values use typed input). Where provided, defaults are prefilled. Raw JSON is **not required** for ordinary tasks. **Show advanced JSON options** is available for people who need precise control and remains subject to the same engine validation.
5. Check the explicit approval box, click **Start automation** and confirm the review dialog. Every launch gets a unique idempotency ID; the engine separately validates it and no other session is started. Monitor the running task list and stop a selected Daedalus-managed task with **Stop selected task**.
6. If a previous request is `unconfirmed`, **do not press Start again**. Refresh the task history and verify engine and game state independently before **Mark checked request as reconciled**. A typed, proven pre-launch rejection now says why it was rejected and does not create an ambiguous task request. Genuine timeouts/unknown results still block replay.

**Notifications**: This preview detects missing Telegram/Discord destinations, but still uses IkaBot's existing notification setup for secret bot tokens/webhooks; it does not transmit them through the ordinary Daedalus REST API. Do not paste those secrets into an automation JSON field.

## Read-only military dashboard (Troops / Fleet / Movements)

Open **Military** from the main navigation. Select a particular account or
**All accounts** (the default), then choose **Troops**, **Fleet**, or
**Movements**. Click **Refresh military data**. Daedalus queries only the
currently authenticated, account-bound IkaBot session. The troop/fleet views
show per-city units and ships; Movements shows origin, destination, mission,
time remaining, troop and ship counts and hostile/returning indicators.

The screen performs **no recruitment, battle, dispatch or recall**. Data is
cleared when changing backend context; a disconnected account reports
*unavailable*, never an invented zero. All-account reads run sequentially,
with independent per-account results. The original viewArmy and
shipMovements CLI functions remain intact and are not misrepresented as
background tasks.

The Automations workspace keeps the explicit consent and launch actions
visible beneath task-specific native tables; its outer scroll owns long
configuration content. Unsupported combat and administrative operations
remain clearly labeled as requiring a reviewed native planner.

## Current acceptance boundaries

One owner-authorized field smoke verified Monjo saved-cookie restoration, the exact game-world player, seven city records and seven real warehouse snapshots on the Mac. No owner-approved game-task execution, **new native Mac Gameforge browser/CAPTCHA login**, dedicated-worker rebind, persistent server keyring after host reboot or completed production cutover has been demonstrated. Those live acceptance checks remain open in the owner acceptance checklist in [NATIVE-MAC-LOGIN.md](NATIVE-MAC-LOGIN.md). GUI and backend synthetic tests cannot substitute for them.

The GitHub Actions macOS build produces an ad-hoc signed preview app. Updating backend code on Linux does **not** automatically replace an older installed Mac `.app`; to use new GUI controls, install the rebuilt preview from the relevant successful macOS CI run. Windows/Linux GUI support is not a guarantee of notarized macOS distribution.
