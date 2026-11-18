# Check previously saved IkaBot cookies without logging in again

This is an **explicit local validation probe**, not automatic login, task start or a production supervisor. It reads an existing saved world cookie from IkaBot's own private account store and makes one ordinary read-only request to the configured game world. It cannot fetch a new login link, bypass a CAPTCHA or authenticate with an email/password. A failed probe reports that human-assisted recovery is needed.

## Setup

Use a separate authorized test account and machine first. Install Daedalus, the vendored public experimental IkaBot engine and OS keyring support:

```bash
python -m pip install -e ".[server,recovery]"
python -m pip install -e ./engine/ikabot
```

The `~/.config/daedalus/accounts.toml` metadata record must include a stable account ID and **canonical** world name such as `s301-en`, with its exact in-game player name. It must **not** contain an email, password, cookies or Gameforge tokens.

To associate the account with the **already saved** IkaBot user, run:

```bash
daedalus sessions bind-email alpha
```

The command privately prompts for the email without showing it on screen. It stores only a reference in the operating system keyring, never in TOML, Git or the backend API. Your existing IkaBot saved sessions remain in their original private engine storage.

After ensuring no independent production worker/browser is controlling the same account, explicitly test the saved world cookies:

```bash
daedalus sessions probe-saved-cookies alpha --confirm-read-only-network
```

A successful result reports `saved_session_valid`. Expired or missing cookies instead request manual recovery; **no new login is attempted**. The probe closes its network session and releases its lease in either case, so it does not leave a running game bot. The host-local lease cannot detect unrelated live game clients on other computers or legacy engines; do not probe those sessions.

To remove the saved email association, run:

```bash
daedalus sessions forget-email alpha
```

Use `--config /secure/path/accounts.toml` after any of these commands to select a custom secret-free metadata file.

## Security and limitations

- Existing engine `Session.from_saved` can otherwise request a Gameforge loginLink when a world cookie fails. Daedalus's explicit `cookies_only=True` implementation refuses that fallback; ordinary upstream CLI behavior is unchanged.
- Only a 200 response from the exact world hostname and a previously saved `ikariam` cookie are accepted for the probe. The returned player and world are checked again.
- A probe refuses disabled profiles, missing or changed keyring references, noncanonical worlds, held Daedalus leases, and any unexpected authentication response. No raw network errors or engine tokens are printed.
- The command performs a genuine read-only game request when explicitly authorized; only synthetic mocks are used in CI.
- It does not create authenticated worker ownership, automatically resume tasks, solve CAPTCHA, or provide a web browser. Those are pending further `unify-authentication` work.

See `docs/SESSION-OWNERSHIP.md` and `engine/UPSTREAM.md` for host-local ownership limits and the proposed upstream engine overlay.
