# Daedalus native Mac quick start (guided preview)

The native application is a controller for a private authenticated Daedalus backend. It is not a browser, a Gameforge password manager, or a separate game bot on your Mac. Only the authoritative Linux worker talks to Ikariam. No task starts merely by connecting or opening a page.

## Connect directly over HTTPS — no SSH needed

1. On your Mac, launch Daedalus and open **Connection**. Enter the private controller's **HTTPS address** provided by your backend administrator, such as `https://your-daedalus-server.example`. The server may use Cloudflare Tunnel, another trusted HTTPS gateway, or an existing private network to expose a stable hostname, but it must require valid TLS and the backend's own API authorization.
2. Paste the **Daedalus API access token** once. This is **not** the Gameforge `gf-token-production` or any Ikariam password; do not substitute those credentials.
3. Leave **Save token securely in Keychain and reconnect on startup** checked (the default), then click the main **Connect** button. After the authenticated handshake succeeds, the app stores the bearer token **only in the OS Keychain**, and the validated server URL in a private preferences file. No token is written to plaintext configuration.
4. Next time, Daedalus automatically reconnects to that previously approved HTTPS server using the saved Keychain token. The **Reconnect saved server** button is also available. If the Keychain is locked or the server cannot be reached, unlock or troubleshoot it normally; the game does not start any new task on reconnect.
5. **Forget saved access** deletes the private URL preference and the corresponding keychain credential. If you change HTTPS server addresses, enter the token again: Daedalus deliberately does **not** forward credentials from one origin to another.

An existing local backend can still be reached through `http://127.0.0.1:8765` for testing; only loopback HTTP or trusted HTTPS is permitted. The optional SSH fallback and synthetic demo are under **Show advanced connection options**, not part of normal use. The app never disables TLS verification or silently converts a saved SSH connection into an HTTPS credential. A public hostname without backend authentication is **not** a supported deployment.

Server operators: see [private-origin HTTPS deployment](REMOTE-HTTPS.md). The service can remain bound to `127.0.0.1` while the gateway supplies a publicly trusted certificate and HTTPS address.

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

## Current acceptance boundaries

One owner-authorized field smoke verified Monjo saved-cookie restoration, the exact game-world player, seven city records and seven real warehouse snapshots on the Mac. No owner-approved game-task execution, new browser/CAPTCHA login, dedicated-worker rebind, persistent keyring after host reboot or completed production cutover has been demonstrated. Those live acceptance checks remain open in `openspec/changes/validate-live-authentication`. GUI and backend synthetic tests cannot substitute for them.

The GitHub Actions macOS build produces an ad-hoc signed preview app. Updating backend code on Linux does **not** automatically replace an older installed Mac `.app`; to use new GUI controls, install the rebuilt preview from the relevant successful macOS CI run. Windows/Linux GUI support is not a guarantee of notarized macOS distribution.
