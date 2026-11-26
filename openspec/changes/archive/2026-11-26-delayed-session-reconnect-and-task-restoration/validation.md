# Baseline validation and risk register (planning)

Date: 2026-11-21. Code revision observed: 38789a5 at start of investigation; proposal branch may include subsequent approved merges. No live account sessions or credentials were accessed.

## Source findings

1. The maintained upstream IkaBot engine distinguishes session rotation via lobby redirects/reload, prints a "session expired" notice and may terminate related processes. A separately stored lobby token and world cookie are different: the former MAY permit a new loginLink; the latter can be invalidated on takeover.
2. Daedalus's ExistingSessionRecoveryMonitor uses read-only active validation, normally every 300 seconds, then requests operator assistance; it intentionally has no automatic reauthentication or task replay.
3. SavedCookieWorker is cookie-only, requires exact host-local account ownership and game-world player verification; it cannot automatically mint a new game-world session after the cookie expires.
4. TaskLedger has request IDs, config hashes, receipts and last engine task IDs/PIDs, but no durable task configurations. Engine managed task listing also omits config. An approved desired-state journal and a reviewed import path are prerequisites for restoring the jobs that were running at rotation.
5. The live controller showed ten configured accounts and zero authenticated game workers during inspection; no live rotation or token validity could be verified safely.

## Offline validation performed

- Session monitor, task controller and saved worker synthetic suite: **39 passed**, no failures.
- No game requests were sent, no token value was inspected, no account automation was started/stopped and no production daemon setting was changed for this proposal.

## Must validate during implementation

- Whether a protected **server-usable** Gameforge lobby credential is available for each enabled account; the existing desktop sealed vault does not prove that.
- Whether the maintained noninteractive engine loginLink path works after a browser takeover for the exact target world/player without CAPTCHA or renewed blackbox; fail closed if not.
- The correct restartability class for every task; exact desired-job config capture; engine process cleanup and IPC availability after IkaBot's session-rotation exit.
- Timing from detection vs actual user login. Current monitor may take up to one polling interval to detect a takeover, plus the deliberate five-minute grace.
- Five minutes cannot establish that the human stopped browsing; an automatic reconnect may rotate their new browser session. Provide the prominent pause/Resume now controls and wording.
- Crash-safe, duplicate-free reconciliation, particularly for non-idempotent transports/attacks/construction and mid-flight results.
- Owner-operated real browser takeovers and a successful verified, one-account task restoration before bulk production activation.

**Status:** Code/source hypothesis validated; proposed automatic reconnection and job restoration remain unimplemented and unaccepted.
