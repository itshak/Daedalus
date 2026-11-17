# ADR-002: Track upstream public IkaBot and port local modifications selectively

**Status:** Accepted (design baseline)

## Context
Public IkaBot 7.7.2 includes task/session fixes, while the live server has extensive local session/auth changes. Upstream CLI/IPC JSON task dispatch is developed in PRs #499, #502 and #510 but is not part of the reviewed master baseline.

## Decision
Import a pristine upstream revision through a reviewable tracked source mechanism. Keep original MIT copyright/license notices. Adapt proposed CLI/IPC code only after tests; retain backward-compatible upstream task modules. Port modified production behaviors one feature at a time with synthetic tests; never import live local account data or git histories.

## Consequences
Upstream merges remain possible. Unreleased IPC changes are treated as external candidate code, not guaranteed stable APIs. Product-specific scheduling and read-only reporting remain in the backend/adapter.
