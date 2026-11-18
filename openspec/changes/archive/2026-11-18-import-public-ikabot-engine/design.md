# Design — upstream engine import

Import a known public upstream revision via a tracked source mechanism; record SHA and retain original LICENSE, copyright and notices. Do not nest a Git repository inside the monorepo. Establish repeatable upstream-update procedure.

The proposed JSON CLI/IPC is not in reviewed master; test candidate patches with fake sessions and account identities before deciding whether to adopt them. Preserve legacy public IkaBot task implementations and keep game HTTP logic inside the engine.

Port local production session/login improvements one audited patch at a time. Never copy .env account files, saved sessions, tokens, cookies, logs or private data. Add mocked integration tests before any deployment.

## Final production-source reconciliation (2026-11-18)

Reviewed six modified **tracked Python source files**, without accessing
private runtime directories or credentials. The production source baseline was
IkaBot 7.7.0 at `2d2cda7e61938e1d393fdcb157ae3425103f5d45`.
A SHA-256 fingerprint of its uncommitted six-file Python patch is recorded in
`docs/ENGINE-AUTH-RECONCILIATION.md`, along with each file's independent
port/decline/covered-by-upstream decision. The owner-authored Selenium GUI was
reviewed as a separate implementation and not mistaken for upstream source.

Safe concepts reimplemented on the upstream 7.7.2 + proposed PR #499 engine:
bounded external blackbox token API retries with 400/422 compatibility fallback,
no response-body or credential-bearing exception leakage, bounded connect/read
timeouts, and explicit fail-fast for detached EOF/manual reauthentication.
Unsafe environment-seeded login credentials, automatically selected accounts,
indefinite menu parking, unattended web server start and raw cookie/token debug
fields were rejected, not copied. Existing Daedalus cookie/keyring/browser
recovery remains the supported separate security boundary.

The official public master and open PR #499 head had **not changed** since the
pinned import revisions. The source-only reconciliation closes this change;
real browser/Gameforge login, recovered-player attestation, worker rebind and
production cutover are explicitly deferred to `validate-live-authentication`.
