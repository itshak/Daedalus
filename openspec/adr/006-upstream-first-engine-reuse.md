# ADR-006: Upstream-first engine reuse and minimal divergence

**Status:** Accepted

**Date:** 2026-11-26

**Related:** ADR-001 (unified platform), ADR-002 (upstream integration and provenance), ADR-003 (session ownership).

## Context

IkaBot is the sole game-operation engine of Daedalus. The imported stable engine and experimental upstream JSON CLI/IPC integration provide working game helpers, request construction, operation loops and queue-specific waiting mechanisms. Parallel implementations in Daedalus can silently diverge from upstream request parameters, response parsing, selected-city context and timing semantics. This has already caused warehouse transport and fleet-wait compatibility failures.

## Decision

**Reuse upstream first. Extend the harness, not the gameplay engine, unless a demonstrated need makes an upstream change unavoidable.**

1. Before implementing or modifying an operation, inspect the pinned upstream source and existing CLI/IPC configuration and execution paths. Reuse the highest-level suitable upstream operation; reuse lower-level helpers only where the new feature genuinely requires composition.
2. Preserve upstream task preparation, JSON contracts, resource and capacity calculations, request construction, parsers, queue checks, and operation-specific waiting and retry semantics wherever compatible with Daedalus safety requirements. Do not invent parallel helpers, alternate game request forms, arbitrary polling intervals, or second execution loops merely to accommodate the GUI.
3. Keep UI, API validation, planning, scheduling, lifecycle tracking, account isolation, authentication recovery, persistence and reviewed-operation policy in the Daedalus harness or narrow adapters. Adapt existing calls at the session boundary rather than changing every gameplay function. Do not weaken authentication, explicit review, uncertain-outcome reconciliation or no-replay protections to achieve upstream parity.
4. Where an upstream interactive operation contains inline logic that cannot be called noninteractively, prefer a mechanical extraction of that same logic into one shared helper. Both upstream-style CLI and native entry points must use it. Preserve original arguments, request forms and default behavior.
5. A new or modified gameplay implementation is permitted only if no suitable upstream helper exists, the existing upstream behavior is demonstrably incompatible with a required capability, or a correctness/security defect requires a change. Document the evidence, the alternatives considered, why an adapter or shared extraction is insufficient, the smallest necessary patch, and its upstream provenance. Review whether the change belongs upstream.
6. Every intentional deviation must have offline regression coverage, including original CLI behavior and the reviewed harness path. Compare normalized JSON inputs, exact request shapes and observable outcomes where applicable. Protect unchanged helpers with source-parity checks; refresh those checks only for reviewed, intentional upstream changes. Do not silently replace a failing upstream path with a separate implementation.
7. Source parity and synthetic tests do not establish real-game acceptance. Keep actual multi-iteration completion and uncertain outcomes visible as separate verification gates.

## Examples

- Warehouse fill supplies reviewed route allocations and storage policy to the original sendResources / executeRoutes / sendGoods pipeline. Fleet availability uses the original waitForArrival and getMinimumWaitingTime helpers.
- Recruitment, workshop, construction and miracles retain their own upstream queue or cooldown helpers; fleet timing is not a substitute for unrelated waits.
- Native previews may add strict ownership and stale-state checks; the reviewed executor uses the same game request construction as the CLI.
- Infrastructure timeouts, cancellation, account reconnection and task restoration remain harness responsibilities, not gameplay waits.

## Consequences

Upstream code remains the canonical implementation and future updates become easier to review. Some narrow local changes remain necessary for noninteractive task preparation, verified-cookie sessions, review policy and restart-safe reconciliation. Those changes must be inventoried, tested and minimized rather than concealed by claims of a pristine engine. A wholesale rollback of necessary integration safeguards is not implied.

See [engine parity audit](../../docs/UPSTREAM-ENGINE-PARITY.md), [waiting audit](../../docs/UPSTREAM-WAIT-AUDIT.md), and [upstream provenance](../../engine/UPSTREAM.md).
