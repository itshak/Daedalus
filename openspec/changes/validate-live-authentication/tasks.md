# Tasks
- [x] Wire native Mac human Gameforge browser recovery and authenticated one-use encrypted world-session transfer, with synthetic GUI/API/worker tests. Host-only CLI remains optional.
- [x] Implement independently verified server-side player identity attestation for recovered world sessions, with synthetic negative tests.
- [x] Add secret-free host deployment preflight for unresolved task receipts, volatile keyring evidence and truthful owner-acceptance status; verify a separate native-login API process can issue/cancel a one-use challenge with no game network.
- [x] Update the live acceptance runbook to the Mac-first HTTPS/Keychain + encrypted handoff flow, preserving only optional host-local recovery fallback.
- [x] Investigate the exact prior Monjo uncertain request, preserve a private backup/audit, verify zero current managed tasks, and reconcile the request without replay.
- [x] Replace the volatile session keyring dependency with host-encrypted systemd credentials, independently revalidate and encrypt Monjo's saved world session, and verify a controlled service restart with authenticated read-only reporting and native login enabled.
- [x] Fix the combined owned-worker/native-login startup ordering regression and add an end-to-end CLI synthetic check.
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

Remediation update (2026-11-19): the outdated one-receipt/volatile-keyring
state above is preserved as **historical evidence**, not the current status.
The receipt is now `operator_reconciled` (not replayed or described as
executed), with private 0600 audit and backup. An encrypted systemd credential
provider is provisioned using host-bound encryption with a root-owned key
file, verified by a separate transient service and one controlled daemon
restart. The current backend reports authenticated Monjo, seven real warehouse
cities, zero unresolved receipts, and opt-in Mac login available through
verified HTTPS; no Mac SSH/VNC is required. A native-login startup-order bug
was diagnosed and fixed. Rebooting the **whole host**, real Mac
Gameforge/CAPTCHA use, a dedicated worker rebind and owner-approved game task
remain untested and block final production acceptance.
