# Consolidation disposition — 2026-11-26

Archived as superseded by the single engineering successor `finish-v010-engineering`, not as proof that unchecked tasks passed. Original task checkboxes remain unchanged. Codes are defined in [the reconciliation index](../../../../docs/V010-RECONCILIATION.md). V codes identify implementation or evidence already present for part/all of a historical task; where E or O also appears, the remaining portion is explicitly transferred. S identifies an obsolete sequencing requirement. No live acceptance is inferred.

| Original unchecked task (in order) | Disposition |
| --- | --- |
| 1. 0.1 Capture current light/dark screenshots and widget-tree inventory for every current route at 900x650 and 1200x800; document UI defects and separately mark legacy warehouse features to preserve. | E5 |
| 2. 0.2 Map every current account, recovery, operation, report, connection, settings and diagnostic action to the target blueprint; flag missing API metadata, conflicts with ADRs, risk and screen-level acceptance ownership. | V4; E5 |
| 3. 0.3 Define approved Mac design tokens, responsive layout grid, type scale, colors, density, icon semantics and accessible states; obtain a visual style baseline approval before widespread refactoring. | V4; E5; O5 |
| 4. 0.4 Evaluate the installed PySide6-Fluent-Widgets version for all proposed widgets (navigation, searchable inputs, switches, cards, dialogs, progress, badge/status, table and segmented controls); record verified imports and fallback wrappers. | V4; E5 |
| 5. 1.1 Introduce a centralized theme/token system with Mac system light/dark following and local overrides; preserve legacy OpaqueCardWidget and scroll table behavior. | V4; E5 |
| 6. 1.3 Build reusable accessible page headers, section cards, account/backend pickers, status chips, inline helper/error, safe confirmation, empty/loading/partial state and toast components. | V4; E5 |
| 7. 1.5 Implement semantic route/deep-link handling so prior Home, Wine, Construction, catalog and task shortcuts reach unified contexts without stale or cross-account selections. | V4; E5 |
| 8. 1.6 Introduce typed, nonsecret per-backend/account Qt view state and async request generation guards; discard stale responses and test rapid account/backend changes. | V4; E3 |
| 9. 1.7 Add shared accessible page-shell layouts and narrow-window overflow/scroll behavior; verify minimum-size layout does not clip controls or Mac traffic lights. | V4; E5 |
| 10. 2.1 Redesign first-run onboarding with HTTPS URL/token validation, demo choice, progress and exact-origin Keychain opt-in/out states; preserve automatic read-only reconnect and ephemeral fallback. | V4; O1 |
| 11. 2.2 Redesign the connected Connection screen as status/details/reconnect/forget plus Advanced SSH fallback; test missing/untrusted TLS, unauthorized token, unavailable keyring and trusted SSH fail-closed handling. | V4; E3 |
| 12. 2.3 Replace simple Home action grid with an account-scoped Overview showing truthful backend/worker health, quick actions, summaries and source/refresh/empty/partial states. | V4 |
| 13. 2.4 Redesign Accounts as an accessible master/detail workspace with clear account identity, session status and contextual primary action while preserving account create/edit/enable/disable/remove rules and confirmations. | V4; E5 |
| 14. 2.6 Move manual assistance, monitoring and host-side recovery into separated permission-gated secondary flows with verified lease/status handling, stale-ticket guards and no implicit worker authentication. | V4; E4 |
| 15. 2.7 Add offscreen synthetic UI coverage for disconnected, read-only, demo, unverified, paused, needs assistance, worker-busy and multiactive account states; ensure zero accidental game requests. | V6; E5 |
| 16. Owner tests current Gameforge login, real CAPTCHA and macOS Keychain persistence, reviews screenshot/VoiceOver and accepts release (separate issue #60; not claimed complete). | O1; O5 |
| 17. 3.2 Build a capability-aware searchable task gallery with understandable titles, icons, explanatory descriptions, permission/readiness labels and honest interactive-only entries. | V4 |
| 18. 3.3 Create a typed schema-aware field rendering library (boolean, integer, decimal, time/unit, validated enum, optional, conditional/group and expert JSON fallback); never infer IDs/options absent backend metadata. | V5; E1 |
| 19. 3.4 Build dedicated Wine controls for tavernManager/alertLowWine and accurate Construction controls for constructionList/research, with backend-supported defaults, examples and focused synthetic form tests. | V5; E1 |
| 20. 3.5 Build dedicated Alerts/Monitoring and Resources/Trade forms for the supported registered tasks, including field help, units, validation and safe fallback for nested/unsupported schemas. | V5; E1 |
| 21. 3.6 Cover military, miracle, daily, piracy and all remaining registered operations with reviewed typed presentation or prominently explained expert/unsupported paths; verify catalog coverage against registry. | V5; E1 |
| 22. 3.7 Implement a one-screen review summary and separate explicit start authorization bound to account/world/task/config revision and fresh preflight; preserve backend UUID/idempotency and dispatch permission checks. | V5; E1 |
| 23. 3.9 Add safe history and uncertain-request reconciliation detail flow: no automatic retry, authoritative state guidance and expert-only acknowledgement; ensure sanitized copy and no false Running/Success. | V4; E3 |
| 24. 3.10 Test complete automation flows using synthetic capability registry changes, disabled backend, dirty drafts, stale replies, preflight rejection, double click, task start timeout and receipt ambiguity. | V6; E3 |
| 25. 4.5 Unify all screen-level loading/empty/error/offline/permission/demo/partial/uncertain messaging, consistency of terminology and localization-ready string sourcing. | E5 |
| 26. Review the multi-account mutation consent screen on real macOS and verify account names, scope labels, choice persistence and accessibility with synthetic fixtures. | E5; O5 |
| 27. 5.1 Verify keyboard-only navigation, macOS accessibility names/roles, screen-reader focus, dynamic/high-contrast text, visual focus and icon-independent status across every critical workflow. | E5; O5 |
| 28. 5.2 Review screenshots of all screens, overlays and state variants on macOS in System/Light/Dark at 900x650, 1200x800 and maximized; approve typography, spacing, density, contrast and distinct icons. | E5; O5 |
| 29. 5.3 Extend macOS CI packaged Daedalus.app offscreen/on-screen smoke with genuine Fluent imports, safe synthetic data and window resize; confirm no new signing/packaging regressions. | V3; E5 |
| 30. 5.4 Run offline pytest, ruff, OpenSpec strict validation, secret scanning, desktop parity, regression and export tests; record outcomes and repair failures before claiming tasks complete. | V3; E6 |
| 31. 5.5 Update GUI user guide, screenshots, first-run/setup, shortcuts, advanced controls and support docs; include explicit distinction between secure API connection and Gameforge login and no-SSH primary workflow. | V4; E6 |
| 32. 5.6 Perform owner-approved *synthetic* end-to-end usability walkthroughs of the seven ux-blueprint.md journeys and capture action counts, defects and visual signoff; leave live-account acceptance to validate-live-authentication. | E5; O5 |
| 33. 5.7 Merge reviewed implementation PRs under itshak identity; reconcile delta specs into canonical desktop-client, archive this change via OpenSpec, update PROJECT-STATUS and verify archive/test hygiene only after all checked gates. | V7; E6 |
