# Tasks
- [x] Wire native Mac human Gameforge browser recovery and authenticated one-use encrypted world-session transfer, with synthetic GUI/API/worker tests. Host-only CLI remains optional.
- [x] Implement independently verified server-side player identity attestation for recovered world sessions, with synthetic negative tests.
- [ ] Run the owner-approved isolated real-account browser/CAPTCHA and saved-cookie recovery workflow; record sanitized results.
- [ ] Verify live dedicated-worker rebind, session expiration, manual recovery and explicit task dispatch without duplicate game operations.
- [ ] Reconcile findings, update docs and CI, and approve production cutover only after the owner reports successful real testing.

Partial field evidence (2026-11-19): one owner-authorized existing-account
lobby renewal, strict game-world player attestation, single dedicated-worker
startup, and seven read-only cities plus seven warehouse snapshots succeeded.
The three checklist gates remain open: this is not a human browser/CAPTCHA
acceptance, expired-session/dedicated-rebind/task-dispatch verification, or
production cutover approval. No public document contains account secrets.
