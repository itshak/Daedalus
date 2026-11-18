# Protected account metadata editing (opt-in)

Daedalus can now manage **nonsecret account metadata** through the same
authenticated local/remote controller API and native Fluent Accounts page.
The mode is OFF by default and never logs in to Ikariam, starts a game worker,
or reads Gameforge credentials.

## Start an editing-only backend

Create or select an owner-private account configuration **outside the Git
checkout**. By default the path is `~/.config/daedalus/accounts.toml`.
The backend may create this file when the default path is initially absent.
For an existing configuration, set its owner-only permissions:

```bash
mkdir -p ~/.config/daedalus
chmod 700 ~/.config/daedalus
chmod 600 ~/.config/daedalus/accounts.toml  # only when the file already exists
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
daedalus serve --enable-account-editing
```

For a custom path, pass `--accounts-file /absolute/private/path/accounts.toml`;
its containing directory must be private and owned by the server user.
For an account-free start, the default path can be absent. Paths inside the
repository, symlinks, group-readable metadata and unrecognized account fields
are rejected. Never put passwords, email addresses, cookies or tokens in this
configuration. Account records contain only `id`, `world`, `player`, `label`
and `enabled`.

**Editing is mutually exclusive with `--enable-task-control`.** To use task
control, stop the editing backend and separately start the explicitly opted-in
existing-session task controller, with the appropriate compatible engine.
This workflow does not affect existing IkaBot workers or production sessions.

## Native UI

Connect the Daedalus desktop over loopback or a protected remote HTTPS/SSH
tunnel and open **Accounts**. The Add, Edit, Enable/Disable and Remove controls
are enabled only when the connected backend advertises account editing.
Select a table row before editing, disabling or removing it. Each change
requires a separate confirmation dialog; the GUI sends only allowed metadata,
not credentials. After successful persistence the current accounts view is
refreshed. A conflict requires reloading/reconnecting before resubmitting.

The editor provides account metadata onboarding, **not** a Gameforge login
assistant or session supervisor.

## API and consistency

All editor calls require the normal bearer token. The editor offers:

- `GET /api/v1/account-config` — returns `enabled`, `revision`, and sanitized
  account metadata. Read-only servers return `enabled: false`.
- `PUT /api/v1/account-config` — a JSON object with exactly `revision`,
  `accounts`, and `confirmed: true`. A revision is a SHA-256 generation of
  the current TOML bytes. A missing or stale revision returns HTTP 422/409.
  Task-control or read-only servers respond 503.

Updates validate all identity fields, reject duplicate world/player identities
and unknown keys, serialize normalized TOML, and use an owner-only temporary
file and atomic replacement. An exclusive file lock prevents concurrent
Daedalus metadata writers on this host. The controller retains cross-process
world/player identity leases through the write; active local account owners
prevent editing. No game network requests occur as part of this flow.

**Limitations:** These locks are host-local, not a cluster-wide guarantee.
Do not run independent active controllers for the same in-game account across
different machines. Use one authoritative backend; do not mistake metadata
editing for a safe production worker migration. This preview is not notarized.

## Offline verification

Run `python -m pytest tests/test_account_editor.py tests/test_client.py
tests/test_desktop.py`, `python -m ruff check src tests`, and
`openspec validate --all --strict --no-interactive`. The synthetic tests
cover stale revisions, metadata validation, private paths and symlinks, active
leases, authorization, no-confirmation rejection and Qt consent gates.
No test logs in to Gameforge or accesses the production bot state.
