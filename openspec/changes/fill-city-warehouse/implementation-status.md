# Implementation evidence

Desktop and browser: Resources & trade → Fill city warehouse. Select the owned destination and one resource, optionally choose freighters, review the aggregate plan and approve. All other owned cities are included automatically in stable city-ID order. Each source contributes up to its current stock and the remaining shared budget. The preview uses the actual city free-space field, subtracts selected-resource incoming and returning cargo as visible in the military advisor, and independently verifies the sum and exact owned-city scope. Ambiguous matching cargo fails closed; duplicate names may conservatively reserve extra space. The worker rechecks ownership, source stock, free space and incoming quantities before each non-retried transport POST. A competing managed transport prevents launch. The next load is permitted only after observing the preceding accepted cargo; otherwise stop and reconcile. A zero allocation sends nothing. No recurring refill or automatic recovery is enabled.

Limitations: the game does not expose an atomic destination reservation across independent actors. The budget is an observed bound, not a guarantee that other manual transfers, production or unseen inbound cargo cannot affect capacity at arrival. The conservative visibility check may stop before using all otherwise available space. No production game action or live acceptance was performed.

Focused Python, Qt, API and transport regression: 61 passed. Web unit tests: 67 passed; TypeScript and Ruff passed. Strict OpenSpec validation: 16 passed. Required CI and owner live acceptance remain open.

## Preview and navigation repair

Owner reported a live web preview rejection and macOS category clicks selecting alerts. Actual Qt clicks reproduced the latter: the Fluent boolean signal replaced the captured tab index. Corrected both automation and military tab handlers, with regression tests clicking the visible tabs. Warehouse preview now reports fixed, redacted failure stages; unrelated movement rows without player names no longer invalidate the selected destination's preview, while ambiguous matching cargo still fails closed. Negative free space means zero remaining capacity. Extended only read-only preview gateway timeout and made progress, approval and Start explicit. Synthetic desktop review-to-launch, API, engine and UI regression: 99 passed. The exact live preview failure has not yet been reproduced; no real game action was performed.

Owner additionally reported imported account labels in Military. Military account selector and all military inventory tables now use the shared player-name display helper, retaining world/ID disambiguation. The Home account selector had the same label-first bug and now uses the same helper. Military and desktop navigation regression: 25 passed.

## Follow-up to live preview failure

Owner reported a generic preview failure on deployed 687436c. Backend health was active with nine authenticated workers; the selected worker was not identified. Added bounded nonsecret error distinctions for preflight, city inventory, worker transport, observation scope and web HTTP/response validation. Tested a full synthetic route through the actual engine IPC handler, loopback socket, dedicated-account router and authenticated API, including successful review, source read failure and disconnected worker. No real account data or game actions were used. Exact live failure remains unverified; do not claim this diagnostic revision resolves it.

## Cookie-only advisor read compatibility

The deployed worker-unavailable diagnostic is consistent with multiple IPC failures. Source review found that the legacy military advisor POST can enter cookie checking/recovery and SystemExit, while the existing cookie-only GET helper retains bounded same-origin checks. Use the fixed read-only military advisor view through the existing GET helper for cookie-only sessions, parse its expected embedded AJAX response, and fail closed if unavailable. Legacy previews classify SystemExit by the observation stage rather than returning an opaque IPC error. Synthetic tests verify no POST is attempted on the cookie-only read and no incomplete observation authorizes a transfer. Live advisor response format and execution remain unverified. No changes to authentication or mutation transport.

## Launch receipt feedback

Live owner report after 611639a: preview appears to succeed, confirm returned uncertain. Read-only ledger status check found one fill request unconfirmed, with no recorded engine receipt/PID. Do not replay or restart the service while unresolved. Extend only the warehouse launch gateway deadline; keep a single request UUID, look up exact scoped durable receipt on a lost response, display a positive localized confirmation only for a verified started receipt, and prevent review expiry overwriting launch results. A started receipt is not proof of cargo delivery. Actual dispatch cause and live task remain unverified.

## Host-local E2E and launch repair

The authorized host-local runner successfully obtained a live warehouse review.
A synthetic regression reproduced the duplicate lease failure: the native
cookie worker held the authenticated lease and dispatch reserved its ledger
entry before failing to acquire another lease. Fix adoption and move validation
before reservation. Separate source inspection identified legacy POST paths in
movement inspection, fleet waiting and reviewed transport; use bounded cookie
transport and identity attestation instead. Add a managed child registration
gate and preserve nonzero status when cargo confirmation is unavailable.
Public tests use only synthetic identities and HTTP/IPC doubles. The live
review is not a shipment; repaired live dispatch and delivery remain open.
