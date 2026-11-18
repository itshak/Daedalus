# Production authentication source reconciliation (offline)

Reviewed **2026-11-18**, using *tracked Python source diffs only* from an owner-authorized local IkaBot checkout. This record is a source review, not a real-account login test. The source checkout and its running processes, saved users, cookies, environment files, browser profiles, and runtime directories were **not modified or inspected**. No private code blobs or runtime values were copied into Daedalus.

## Versions and source scope

| Source | Reviewed revision | Disposition |
| --- | --- | --- |
| Official [Ikabot-Collective/ikabot](https://github.com/Ikabot-Collective/ikabot), stable `master` | `3ea1e0eebfb2e52b5f53ea8b5051df2a9a887579` (7.7.2) | Current Daedalus public base; still the upstream tip at review |
| Upstream proposed [PR #499](https://github.com/Ikabot-Collective/ikabot/pull/499) including #502/#511 | `062feec0f5f6ea5810bfe91126e337a2b86aa3e3` | Already vendored and tested, still unreleased; do not reimport twice |
| Owner-authorized production checkout (uncommitted tracked-code changes only) | Clean HEAD `2d2cda7e61938e1d393fdcb157ae3425103f5d45` (7.7.0) | Six modified tracked Python files below, compared against public 7.7.2/PR #499 |
| Owner-authored private Selenium/Fluent GUI, a *different* implementation | `0f47b891545ee584c0a3f76603948b75f545bdcf` | Architecture reviewed separately under `docs/LEGACY-GUI-AUDIT.md`; no wholesale import |

The six-file production working-tree patch has SHA-256
`a1bec8c8e793fd1b1faa83df883494d00cb926e882804c1f4ebb5db858d84600`.
This identifies **source changes**, not account state. A different patch digest
requires a new review; the privately modified source is not committed here.
No untracked Python source appeared under the audited engine package.

## File-by-file reconciliation

| Production source diff | Decision in Daedalus | Why |
| --- | --- | --- |
| `ikabot/command_line.py`: scripted environment-driven menu input and indefinite detached-menu parking | **Do not port** | Silently queues game operations and can leave a process sleeping indefinitely. Daedalus already has explicitly confirmed, idempotent managed task IPC |
| `ikabot/config.py`: API connect timeout and retry controls | **Adapt** | Bounded nonsecret `IKABOT_BLACKBOX_CONNECT_TIMEOUT` (maximum 30s), `IKABOT_BLACKBOX_TIMEOUT` (maximum 120s), `IKABOT_BLACKBOX_RETRIES` (0–3 retries) with safe defaults |
| `ikabot/function/webServer.py`: skip Enter confirmation if stdin is detached | **Do not port** | Could automatically start an unprotected listener; Daedalus uses a separately opted-in, authenticated, loopback-only controller |
| `ikabot/helpers/apiComm.py`: retry token API network errors and retain API compatibility fallback | **Adapt with hardening** | Bounded exponential transport retries, no retries on HTTP rejection, retain 400/422 fallback, validate payload and suppress error response/exception-body leakage. Does not create a Gameforge login |
| `ikabot/helpers/pedirInfo.py`: stop recursive prompts on detached stdin EOF | **Adapt with hardening** | First detached EOF raises a sanitized `EOFError` rather than silently returning `None` and causing unsafe downstream behavior |
| `ikabot/web/session.py`: environment-backed mail/password/lobby-cookie/blackbox overrides, manual fallbacks, token-only defaults, session debugging hooks, and login-prompt handling | **Mixed** | **Adapt** explicit no-TTY guards for manual password/token assistance. **Retain existing upstream** browser-context blackbox, regional headers and ordinary saved-session behavior. **Do not port** plaintext environment credential bootstrapping, ambiguous saved-account fallback, raw cookie/token debug attributes, unverified manual cookie binding, direct login/replay or stored-session mutation. Daedalus instead keeps explicit exact-account saved-cookie and browser recovery on the authoritative host |

All adapted behavior is independently rewritten as a small, reviewable
Daedalus-maintained overlay against the pinned MIT engine, not copied from the
uncommitted production working tree. The rest remains a documented rejected
or already-covered difference.

## Safety and validation boundaries

- New token API retries occur **only for transport failures** and are bounded.
  HTTP 401/403/5xx responses and malformed payloads fail closed; hidden response
  bodies and network exception text do not enter error messages.
- No `IKABOT_GF_TOKEN`, blackbox payload, password, account selection, or
  remote browser session is read from production files or copied to public
  settings. Authentication remains under the Daedalus backend's account lease,
  browser consent, keyring and world-session validation boundaries.
- A detached process requiring new login/password/CAPTCHA/manual blackbox input
  fails explicitly. It does not prompt recursively or launch a competing
  browser login. An operator must use the separately reviewed assistance flow.
- Existing public IkaBot CLI compatibility is retained. No methods that
  execute a Gameforge command were replaced or removed. Tests use only mocked
  responses and synthetic identities; the reviewed production checkout is
  never imported or invoked.
- Actual Gameforge/browser login, independent server-reported player
  attestation, remote UI assistance and worker acceptance **remain open**
  under `validate-live-authentication`. This source audit cannot certify
  production readiness or validate real cookie behavior.

## Repeatability

A later source-only review can compare the six tracked production Python
files against local Git HEAD, record a new patch digest **without exporting
diff contents**, and compare changed functions with the above decisions.
Reviewers must not read `.env`, account directories, profiles or session
files or copy them into this public repository. Official upstream updates
require a new pinned revision and isolated engine tests before integration.

The first-party Daedalus engine overlay and the original upstream MIT license
remain documented in `engine/UPSTREAM.md`.

## Offline regression evidence

- Daedalus-vendored IkaBot: **339 passed**, 9 skipped, 107 pytest subtests
  passed, with only synthetic game identities and mocked network responses.
- Daedalus controller and desktop: **322 passed**, with no real backend token
  or game-session interaction.
- Focused production reconciliation: **15 passed**, including token API
  recoverable failures, HTTP rejection, malformed payloads, maximum retries,
  no exception-body leakage, and noninteractive manual-auth failures.
- Protected CI, strict OpenSpec and build verification must pass before merge.
  These are source and synthetic checks, not proof of live Gameforge login.
