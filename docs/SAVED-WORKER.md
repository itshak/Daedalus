# Explicit saved-cookie IkaBot worker (experimental)

This opt-in path runs a **single** authenticated IkaBot world session in the
Daedalus API process. It never logs into the Gameforge lobby, asks for a
password/CAPTCHA, or starts a game task automatically. The first network
operation is a read-only world validation using a previously saved session.

## Requirements

- Install Daedalus with server and recovery extras and make the **maintained
  vendored IkaBot engine** importable (for a source checkout, use
  `PYTHONPATH=src:engine/ikabot` from the checkout root).
- Configure a canonical account world such as `s301-en` and exact player in a
  private, secret-free accounts TOML file outside the repository.
- Bind the corresponding saved IkaBot email using the private interactive
  `daedalus sessions bind-email ACCOUNT_ID --config /private/accounts.toml`
  command. A manually imported, validated world cookie may be used instead of
  existing engine cookies.
- Ensure no other IkaBot IPC owner is running. This worker will **not** take
  over or modify another worker's IPC descriptor.

## Start

```sh
PYTHONPATH=src:engine/ikabot daedalus serve \
  --accounts-file /private/accounts.toml \
  --connect-existing-ipc \
  --restore-saved-account ACCOUNT_ID \
  --confirm-read-only-network
```

For explicitly confirmed game task controls, also supply
`--enable-task-control`; only tasks targeting the exact authenticated
world/player are accepted. Do not enable it for a read-only preview.

The worker owns the account lease until API shutdown and closes its session
and dedicated IPC endpoint on exit. It cannot perform interactive login or
recover expired cookies. The assisted-login ticket protocol does not yet launch a browser or recover
expired cookies. An operator must complete browser authentication separately
and explicitly import the validated world cookie using the hidden local
`daedalus sessions bind-world-cookie` flow before retrying. Any managed
background task subprocesses may outlive the API; reconcile those tasks
individually before starting another worker. Run the synthetic
`daedalus doctor --smoke` first to test the local API without contacting the
game. Do not commit private account files, credentials or cookie values.
