# Finish cross-platform operation parity and acceptance

## Why
The preceding implementation delivered the reviewed native operation baseline but did not achieve complete upstream option parity or release acceptance. The owner requested archiving that implementation change. This successor retains all unresolved scope; the archive is a source baseline, not production approval.

## What changes
- Close operation-level gaps recorded in the original coverage matrix, including full options, authoritative route ETA, additional batch scopes and shared generated contracts.
- Provide reviewed protected administrative workflows with write-only configuration, bounded connectivity checks, safe extension/release management and an authenticated service equivalent, without exposing raw engine services or secrets.
- Complete cross-platform UI/accessibility, CI, packaging, and owner-operated live acceptance; reconcile overlapping active changes and deploy only after separate verified rollout approval.

The original proposal, design, tasks and specification targets are retained verbatim alongside this proposal. They remain the reference for scope; no unchecked original criterion is discarded. Work already implemented should be reused, not repeated.

## Impact
Controller, engine, desktop, web, security, tests, docs and release workflow. No live game mutation is authorized by this proposal.


**Owner scope decision (2026-11-26, superseded):** proxy configuration was initially deferred (issue #98); the owner subsequently restored it to scope. Implement host-approved account-specific profiles, fixed credential-free HTTPS tests and explicit idle-account changes. Arbitrary endpoint and authentication provisioning remain protected host-local; live acceptance and other outstanding requirements remain open.

## Archival scope
The delivered source milestone is archived at the owner's request. Remaining option-level, verification and rollout gates continue in verify-and-release-cross-platform-parity. This does not mark unperformed criteria complete.
