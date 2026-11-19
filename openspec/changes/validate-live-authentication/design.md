# Design — supervised integration gate

Use a separately authorized account and isolated backend. Keep one authoritative worker host. Verify a real world page and server-side player identity before any user-approved new task. Capture only sanitized status and synthetic regression fixtures. Require explicit consent before each live network or game-changing operation. Do not touch the production tmux installation. Retain the offline fallback if live browser behavior changes.


## Offline implementation delivered (2026-11-18)

The first two tasks are implemented with synthetic native Qt, HTTP API, IPC,
browser isolation and engine tests. On the desktop, an operator selects the
account and requests fixed **authoritative-host** recovery instructions; no
cookie, password or browser profile is sent over HTTPS/SSH-tunneled control
traffic. In dedicated cookie-only mode an operator may explicitly prepare an
**idle** worker, which holds its lease, prevents new game tasks and emits a
short-lived nonsecret assistance ticket. The human completes the real Gameforge
login/CAPTCHA **on the authoritative worker host**, then stages a world-only
cookie in a *separate, unverified OS-keyring slot*. The desktop only sends
confirmation of the ticket. The trusted worker checks there are no running or
uncertain tasks, independently verifies the staged cookie from the TLS-verified,
nonredirecting game-world page, compares the server-rendered player to the
configured account, swaps its dedicated IPC owner, and revalidates the new
worker before recording success. Neither controller API nor remote desktop
receives the cookie. No game operation is replayed.

The engine also requires independently attested player identity on every
cookies-only restore and existing-worker active validation. Saved usernames,
lobby metadata, a bare HTTP 200 and actionRequest alone are insufficient.
Missing/ambiguous/currently-unrecognized game markup **fails closed**.
This deliberately means Gameforge layout incompatibilities may cause recovery
to fail for the real test account until the owner supplies a sanitized failure
category and a reviewed parser update is made.

The real-account browser, task effects, session expiration, worker rebind and
production cutover gates remain unchecked. No one has tested a real account
or authorized production in this change. See docs/LIVE-ACCEPTANCE.md.

## New native Mac implementation (2026-11-19)

The implementation change `native-mac-browser-login` replaces the default host-only GUI guidance with a native Mac off-the-record Gameforge login and an authenticated, account-bound, one-use X25519/HKDF/AES-GCM world-cookie exchange. The backend still independently attests the game-world player and retains the existing dedicated worker lease for a safe idle-only rebind; no Gameforge password or CAPTCHA response is transferred or solved. All offline synthetic steps are archived separately. The owner-controlled real login/CAPTCHA, daemon keyring persistence, live task dispatch, no-duplicate verification and explicit production cutover are **not** completed or waived by this change.
