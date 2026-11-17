# Enforce host-local account-session ownership

## Why
Daedalus now has upstream task-launching capabilities and a read-only controller API, but cannot safely connect real workers without preventing duplicate account sessions and coordinating interactive login recovery.

## What Changes
- Add cross-process host-local ownership locks scoped to world/player, not only account ID.
- Add a narrow, explicit authentication state machine for session restoration, human assistance and validated handoff.
- Provide read-only account status through the existing authenticated API, with no new task-launch or login routes.
- Test lock contention between coordinator objects and separate Python processes; prohibit disabled or duplicate accounts.

## Capabilities
### Modified Capabilities
- `account-sessions`: local single-owner session lease and validation transitions.
- `controller-api`: read-only state visibility without login or task commands.

## Non-goals
No Selenium login port, Gameforge token extraction, live worker startup, distributed lock across hosts, task execution, CAPTCHA bypass or production account migration.

## Impact
Prepares a controlled worker startup and human-assisted recovery path. See ADR-003 and ADR-004.
