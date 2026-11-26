# Host-local warehouse E2E acceptance

Use the actual authenticated controller API; do not inspect credentials, cookies,
private IPC descriptors, or game logs. The Linux runner is an operator utility,
not a public endpoint or an authorization bypass. Install only a reviewed
revision as root, outside writable checkouts. Existing approved server
administrators run it through systemd. Do not grant blanket sudo rights or
expose the controller token to a client process outside that trust boundary.

Example provisioning (synthetic names only; configure the actual policy privately):

```sh
install -d -m 0750 -o root -g debian /etc/daedalus
install -d -m 0700 -o debian -g debian /var/lib/daedalus/e2e
install -o root -g root -m 0755 scripts/warehouse_e2e.py /usr/local/libexec/daedalus-warehouse-e2e.py
install -o root -g debian -m 0640 /dev/null /etc/daedalus/e2e-scope.json
```

Set the root-owned scope JSON to a uniquely configured player, destination,
resource and fleet type. Example:

```json
{"player":"ExamplePlayer","city":"ExampleCity","resource":"wood","useFreighters":false}
```

Invoke from an authorized root administrative execution context:

```sh
systemd-run --quiet --wait --pipe --collect --uid=debian --gid=debian \
  --property=EnvironmentFile=/home/debian/.config/daedalus/backend.env \
  --property=NoNewPrivileges=yes --property=PrivateTmp=yes \
  --property=ProtectSystem=strict \
  --property=ReadWritePaths=/var/lib/daedalus/e2e --property=UMask=0077 \
  /usr/bin/python3 /usr/local/libexec/daedalus-warehouse-e2e.py inspect
```

Use the existing service environment-file path only if it is already provisioned
and protected on that host. Systemd injects the existing bearer credential; do
not print it, copy it into a command argument, or commit an environment file.
This runner uses the existing administrative authorization; its root-owned
policy and fixed command restrict normal operator invocation, but it is **not**
a separately revocable, server-enforced scoped bearer token. If delegating
access to someone who is not already a trusted server administrator, provision
a genuinely scoped backend credential first. Never grant arbitrary systemd-run
permission as a substitute.

Modes (replace the final argument in the command):
- `inspect`: account/task state, warehouse snapshot, and read-only movements.
  For older deployed releases use `inspect --skip-movements` because their
  movement read can enter legacy session recovery.
- `observe`: fresh warehouse preview observation, without retaining a launch
  ticket or submitting a game action; useful for verifying incoming quantities.
- `preview`: generates and stores a short-lived, account-bound review in the
  private runtime directory and prints a new request ID and reviewed allocation.
- `start --confirm-request REQUEST_UUID`: only after explicit authorization of
  that exact fresh review; consumes local ticket before one launch attempt and
  rechecks the durable receipt. A lost response must never trigger a second POST.

The script serializes invocations, rejects ambiguous account/city identity,
unresolved dispatches, and active tasks before starting. It never reconciles an
old request, logs in, stops a task, restarts a service, or replays a shipment.
An expired local review is replaced only by a fresh preview. A started receipt
is evidence of child registration, not cargo delivery. Use observe/inspect to
compare current incoming cargo and actual warehouse/source stock; game production
and unrelated manual changes can affect those quantities. Keep live observations
private. If the operation is running, report it as running; if receipts or game
observations are incomplete, report delivery as unverified. Do not call a
reconciled historical request successful merely because its status was changed.

Production rollout: ensure no active or unresolved jobs across all configured
accounts, verify required CI on the exact release commit, use the documented
deployment mechanism, recheck worker health, and obtain a fresh review after
deployment. Do not restart while any worker or dispatch cannot be reconciled.
