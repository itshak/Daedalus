# Design — account lease and session states

## Identity
An account is identified by its game world and player name with normalized Unicode/case. The account ID remains a stable local UI key, but does not identify the lock. Duplicate IDs and normalized world/player identities fail before acquisition.

## Locking and state
Use the cross-platform filelock package for a nonblocking, OS-backed lock per identity. Place opaque hash-named lock files in a private per-user state directory outside the checkout. Do not store cookies or authentication material in lock files. A held lock prevents another process on the same host and same state directory from starting a worker for the identical world/player. A context-managed owner closes and releases the lease.

The coordinator only exposes a status state machine: validating_session, authenticated, needs_assistance, assisted_login, validating_handoff, paused and failed. Notably assisted_login cannot jump directly to authenticated; validating_handoff is required. The manager has no login/network code.

## Controller
Keep FastAPI's read-only status. An optional in-process coordinator is injected at application creation. Account listing and a per-account GET route report status; no mutations, password exchange or task dispatch are available. The unauthenticated health endpoint reports only counts.

## Deployment boundary
Locks are host-local: a second Daedalus backend on another machine can still start a game session. Do not promise distributed correctness. An account must be assigned to exactly one authoritative backend; remote desktops do not own separate game sessions. Later real workers must acquire a lease *before* login and release it only when their game process is stopped.

## Verification
Include tests for cross-process exclusivity, duplicate identities, closed handles, disabled accounts, permitted and denied transitions, file permission hardening, symlink rejection, and authenticated API state visibility. All tests remain offline.
