# v0.1.0 owner-operated acceptance (deferred, not passed)

Tracking: [issue #60](https://github.com/itshak/Daedalus/issues/60). The owner explicitly deferred manual acceptance from the engineering backlog on 2026-11-26. Engineering changes may archive without these checks. **Stable release acceptance is not granted**. Do not run live game-changing tests or reboot the production host in CI or without explicit owner authorization. Record sanitized timestamps, exact app/backend/web versions, expected and observed outcomes, and pass/fail/not-tested; no secrets, private game data or raw logs.

## O1 — Mac setup and account authentication
- [ ] Install the matching Mac DMG and verify checksum, HTTPS connection, Keychain persistence, automatic reconnect, saved session restoration, headless Selenium and visible fallback, real CAPTCHA/MFA if encountered, correct world/player, cancellation and fail-closed wrong/expired identity.
- [ ] Verify idle dedicated worker rebind, single ownership, no task replay, all/selected account sign-in and warehouse comparison against the game.

## O2 — Actual game execution and observations
- [ ] Verify real warehouse fill preview, explicitly reviewed shipment, exact source/recipient, incoming cargo, multi-load fleet waiting/return, accepted versus delivered quantities and final stock. Repeat the repaired feedback path without duplicating uncertain requests.
- [ ] Verify core task families on owner-approved accounts: construction and supply, ordinary/fixed/recurring transport, troop/ship recruitment, workshop, research, tavern, faith, daily rewards, trade, donation, missions and monitoring as used. Verify task effect, managed receipt, running/stop/history; no automatic replay. Exercise only operations you authorize.

## O3 — Real game-session takeover and job restoration
- [ ] Verify browser takeover, five-minute grace, browser pause/resume, protected token-based reconnect if eligible, correct account and independent unaffected accounts. Confirm safe jobs resume only missing work, fixed cargo is not duplicated, and uncertain/unsupported jobs remain held. Expand accounts only after successful field review.

## O4 — Controlled host reboot and durability
- [ ] During an approved maintenance window, back up and verify protected credentials, durable desired jobs, task and cargo receipts across a full host reboot; confirm Mac Keychain reconnect, no competing workers and no duplicate dispatch. Normal daemon restart evidence is not a full reboot.

## O5 — Real client usability
- [ ] Verify latest authenticated web and native screens (all/selected/one, military actual troop/fleet/movements, warehouse filter/sort/cache/print/export, Activity diagnostics, launch/receipt/stop and recovery). Mac military inventory was owner-confirmed on the earlier fix; updated web rendering and diagnostic presentation remain not accepted.
- [ ] Review real Mac light/dark, sizing, keyboard/VoiceOver, dialogs, multi-account consent and seven UX journeys; browser desktop/mobile/Safari, zoom, accessibility, Russian/English and appearance. Approve visual quality or report concrete defects.

## O6 — Deployment and protected-local boundaries
- [ ] Verify authorized browser-to-BFF-to-backend access, revocation, anonymous denial, secure deployment and rollback in approved production environment; confirm credentials not exposed and no unrelated bots affected. Approve remaining protected local provisioning/administration exceptions, including proxy, extension, challenge, legacy game service and any manual task recreation.
- [ ] Approve exact coordinated release and cutover only after required engineering CI and remaining applicable owner tests pass; document any explicitly accepted limitations separately.

Detailed historical acceptance instructions: [LIVE-ACCEPTANCE.md](LIVE-ACCEPTANCE.md), [WAREHOUSE-E2E.md](WAREHOUSE-E2E.md), [AUTOMATIC-RECOVERY.md](AUTOMATIC-RECOVERY.md). The source proposals are indexed in [V010-RECONCILIATION.md](V010-RECONCILIATION.md).
