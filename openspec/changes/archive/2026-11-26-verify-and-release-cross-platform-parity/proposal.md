# Verify and release cross-platform parity

## Why
The owner requested the implemented operation-review expansion to be archived and manual Mac/live testing deferred. The preceding change delivers the independently reviewed native operation workflows, but an archive is not full upstream option parity or deployment approval.

## What changes
- Verify final source against automated CI and full offline tests, publish the exact matching Mac DMG and checksum, and coordinate a safe verified backend and web release with rollback.
- Retain the unfulfilled original option-level, accessibility, security-boundary and recovery criteria in prior-checklist.md and original-tasks.md. Review and close only with evidence; reuse delivered work.
- Keep manual Mac installation and live game acceptance deferred to owner-assigned issue #60; do not mark these checks passed.
- Keep unsupported or protected-local operations explicitly unavailable rather than using raw execution or unapproved privileged paths.

## Impact
Release verification, packaging, rollout, documentation and remaining implementation criteria. No live game mutation is authorized by this proposal.
