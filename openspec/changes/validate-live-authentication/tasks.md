# Tasks
- [x] Wire native Mac human Gameforge browser recovery and authenticated one-use encrypted world-session transfer, with synthetic GUI/API/worker tests. Host-only CLI remains optional.
- [x] Implement independently verified server-side player identity attestation for recovered world sessions, with synthetic negative tests.
- [x] Add secret-free host deployment preflight for unresolved task receipts, volatile keyring evidence and truthful owner-acceptance status; verify a separate native-login API process can issue/cancel a one-use challenge with no game network.
- [x] Update the live acceptance runbook to the Mac-first HTTPS/Keychain + encrypted handoff flow, preserving only optional host-local recovery fallback.
- [ ] Run the owner-approved isolated real-account browser/CAPTCHA and saved-cookie recovery workflow; record sanitized results.
- [ ] Verify live dedicated-worker rebind, session expiration, manual recovery and explicit task dispatch without duplicate game operations.
- [ ] Reconcile findings, update docs and CI, and approve production cutover only after the owner reports successful real testing.

Partial field evidence (2026-11-19): one owner-authorized existing-account
lobby renewal, strict game-world player attestation, single dedicated-worker
startup, and seven read-only cities plus seven warehouse snapshots succeeded.
The three checklist gates remain open: this is not a human browser/CAPTCHA
acceptance, expired-session/dedicated-rebind/task-dispatch verification, or
production cutover approval. No public document contains account secrets.

Additional offline evidence (2026-11-19): `daedalus doctor --smoke --deployment-check`
passed synthetic API checks without Gameforge network access, and the real
host's private metadata-only audit reported exactly one unresolved task request
and only a volatile keyring collection. The live backend and Monjo saved-cookie
worker were not restarted; their prior authenticated warehouse path remains
available through the TLS-verified HTTPS controller. The new version was also
started separately with a synthetic account on a different loopback port;
its native-browser capability, one-use challenge, cancellation and shutdown
passed without touching a real account or Gameforge.
