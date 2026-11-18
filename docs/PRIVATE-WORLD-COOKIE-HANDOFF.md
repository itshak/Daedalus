# Private local handoff of a browser-authenticated game-world cookie

This workflow is **an opt-in host-local bridge** for an existing IkaBot saved account. It is not a replacement for browser-assisted login in the desktop, and it does not start a bot or resume tasks.

## Prerequisites

Use a separately authorized test account and the Daedalus-vendored engine. Have one canonical world and player in your secret-free `~/.config/daedalus/accounts.toml`, and an existing saved IkaBot user record on this machine. Stop other Daedalus workers and avoid using a production session or browser that another independent bot controls. Host-local locks do not coordinate independent legacy bots or other machines.

Install Daedalus plus the OS credential store and engine:

```bash
python -m pip install -e ".[server,recovery]"
python -m pip install -e ./engine/ikabot
```

First bind the corresponding saved IkaBot login email in the local OS keyring (the input is hidden):

```bash
daedalus sessions bind-email alpha
```

## Import only an already authenticated world cookie

Finish any ordinary login and CAPTCHA **yourself** in a trusted browser. In the browser's own developer tools, inspect the world site's cookies and copy the value for the `ikariam` cookie. Treat it like a password: do not post it in chat, screenshots, Git, shell commands or logs.

Run on the *same host as the saved IkaBot user*:

```bash
daedalus sessions bind-world-cookie alpha --confirm-read-only-network
```

Daedalus prompts privately for the cookie with terminal echo disabled. It validates a single exact already-saved IkaBot world/player using only a read-only world GET under the local session lease, never a lobby loginLink. A successful probe stores the cookie **only in the OS keyring**, scoped to that exact account/world/player. Failed verification leaves the existing binding unchanged.

Use a custom metadata file with `--config /absolute/private/accounts.toml`. This command deliberately cannot receive the cookie as a command-line argument, environment variable, desktop API payload or uploaded file.

To check the verified binding later or remove it:

```bash
daedalus sessions probe-saved-cookies alpha --confirm-read-only-network
daedalus sessions forget-world-cookie alpha
```

The normal `sessions forget-email` command independently removes the saved-user email mapping. Both secrets stay outside the project repository and never appear in the API.

## Limitations

Important: the probe checks the saved account selector and the cookie-authenticated world page; it does not independently prove the server-side player identity from page HTML. Do not reuse a cookie from a different player on the same world. A future explicit player-identity attestation is required before production cutover.

The user must already have a compatible saved IkaBot user record; this does not configure a brand-new Gameforge account or import passwords. Imported cookies remain in the OS keyring until deliberately deleted, and importing one does **not** modify any IkaBot worker already running in another process. It does not solve CAPTCHA, automate the browser, transfer a remote Mac cookie to a Linux backend, start game tasks or resume interrupted tasks. Real browser authentication recovery and supervised worker startup remain pending in the `unify-authentication` change.

Only offline mock sessions and synthetic cookie strings are used in CI. A real read-only world GET occurs only when the operator explicitly invokes the import or probe commands.
