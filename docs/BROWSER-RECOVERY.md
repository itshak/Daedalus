# Human Gameforge browser recovery

The normal controller path is now **Sign in on this Mac** using a temporary native Qt WebEngine browser and a one-time, encrypted session handoff to the Linux worker. The browser handles no automatic password entry, MFA or CAPTCHA solving. It accepts only an exact-world secure `ikariam` cookie, and the server independently verifies the game-world player under the correct lease before accepting it. This is the **implemented synthetic-tested Mac-first path**; full real-account login acceptance is still pending.

See **[NATIVE-MAC-LOGIN.md](NATIVE-MAC-LOGIN.md)** for end-user steps, cryptography, deployment prerequisites, failure modes and remaining owner acceptance. Direct HTTPS and secure Keychain reconnect are described in **[GUI-QUICKSTART.md](GUI-QUICKSTART.md)**.

## Optional host-only maintenance fallback

The legacy opt-in host-local commands remain for expert troubleshooting only:

- `daedalus sessions assist-playwright-login ACCOUNT_ID --config /private/accounts.toml --confirm-read-only-network` uses isolated human Chromium on the Linux host and verifies the exact world under a temporary account lease.
- `daedalus sessions stage-playwright-login ACCOUNT_ID --config /private/accounts.toml --confirm-read-only-network` places an unverified world cookie into the host's protected keyring for an existing dedicated worker which has been manually prepared/paused.
- `daedalus sessions discard-staged-cookie ACCOUNT_ID --config /private/accounts.toml` explicitly clears an unverified host-side staging entry.

These are **not required by the native Mac workflow** and should not be presented as ordinary GUI instructions. Protected host-local staging still requires the correct OS user, keyring, exact configured identity and explicit consent. Never paste raw cookies or credentials into REST API payloads, logs or GitHub.

The independently verified player identity check remains mandatory in both paths. A cookie restore that redirects to login, has unrecognized player markup, or disagrees with world/player **fails closed**. Browser automation never starts game-changing tasks. The pending owner validation and production acceptance criteria are in [NATIVE-MAC-LOGIN.md](NATIVE-MAC-LOGIN.md).
