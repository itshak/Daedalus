# Manual assistance acknowledgment design

A trusted engine process first holds an `OwnedAccountSession` lease. It calls `AssistanceBroker.request(lease, fixed_reason)`, transitioning the lease to needs_assistance and creating a one-use random UUID ticket held only in memory. Reasons are `session_expired`, `login_required` and `manual_challenge` with no user-supplied text.

An explicitly injected in-process broker enables bearer-protected `GET /api/v1/accounts/{account_id}/auth-assistance` and `POST /api/v1/accounts/{account_id}/auth-assistance/{ticket_id}/approve`. The POST accepts exactly `{"confirmed": true}`. It checks the account ID, current ticket ID, one-use status, bounded TTL and active worker lease. The acknowledged session remains assisted_login; it is **not authenticated**.

The trusted worker alone calls `begin_validation` and `complete_validation(valid=...)` after independent engine verification. Success moves the owner to authenticated. Failure returns it to needs_assistance and requires a new ticket. Expired requests pause the held owner without releasing its lease.

The desktop selects the account, reads a nonsecret reason/state, asks separate Yes/No consent, and shows that worker verification is still required. No HTTP or Qt route opens a browser, transfers a cookie/token, claims authentication, or starts automation.

Tickets are intentionally volatile: restarted workers must reconcile and reissue help requests. The broker is not yet wired to production worker startup, browser handoff or a durable supervisor.
