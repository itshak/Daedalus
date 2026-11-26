# Design

The existing-session worker reads owned city stock, destination free storage, fleet capacity and the military advisor's incoming resource rows. Allocate in stable city-ID order, limited to the aggregate budget. Unknown movement cargo fails closed. Dispatch only an account-bound reviewed plan, with fresh ownership, stock, incoming cargo and storage verification before each non-retried shipment. Before another shipment, require evidence of the previous accepted cargo in the advisor, otherwise stop for reconciliation. Concurrent manual changes and production can affect arrival-time capacity; no server-side warehouse reservation is claimed. A zero allocation is a safe no-op, and manual review is required after interruption.

## Native worker launch and operator acceptance

Adopt the exact authenticated coordinator-owned lease after protected IPC
verification rather than acquiring a second lease. Validate ownership before
reserving a dispatch; only an attempted engine start can have an unknown
outcome. A managed warehouse child waits until parent registration succeeds
before entering the task. Preserve nonzero exit status on failures or
unconfirmed cargo; a child exit alone does not establish delivery.

Cookie-only advisor reads share the bounded existing GET path for preview,
movement inspection and fleet waiting. Reviewed transport uses the existing
IkaBot sender with an independently attested same-world session and fresh
request token, one nonredirecting POST per action, no reauthentication or
automatic replay. The ordinary legacy session path is unchanged.

A trusted host administrator can use the fixed-loopback authenticated runner
with root-managed operation scope and private expiring review state. An
explicit exact request-ID confirmation is required for mutation. This is not
a new delegated scoped bearer credential. No live identifiers, tokens,
observations or game mutations are included in public CI.

## Consolidated upstream transport pipeline

The warehouse task is a planning/policy adapter only. Translate its reviewed
source allocation into the upstream sendResources JSON route shape
(`from`, `to`, `resources`, and `useFreighters`). The existing
`prepare_sendResources` normalizes IDs, resource vectors and fleet selection;
both CLI and warehouse invoke `execute_prepared_shipments` and the single
`executeRoutes` / `sendGoods` implementation. An internal, non-JSON warehouse
policy rechecks the aggregate remaining budget, source ownership, incoming
cargo and confirmed movement before advancing the shared route loop. The
reviewed amount is an upper bound, never a recurring refill or an obligation
to exhaust depleted source stocks. Stock shrinkage before preparation may
reduce a route or cause a safe rejection; capacity is refreshed after waits.

The protected cookie-session adapter sits behind the existing Session.post
interface for the two existing upstream transport actions. It preserves
exact upstream form fields, checks the selected source and token immediately
before submission, and refuses redirects, implicit login and automatic replay.
Ambiguous or contradictory game feedback is not a definitive rejection;
checkpoint and warehouse progress may only advance after their corresponding
positive evidence. Normal upstream CLI sessions retain their existing path.
