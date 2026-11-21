# Apple-style Daedalus web design system and review rubric

## Product goal

A calm, unmistakably Daedalus productivity app. The interface should feel simple because work is well grouped, **not** because capabilities are hidden. Each view answers: Where am I? Which accounts? What is available? What will this do? What happened? How do I recover?

## Visual and interaction tokens

- **Type:** native system font stack; type sizes and weights with intentionally tuned letter spacing and leading, tabular numerals for resources; rem-based density and 200% zoom support. Do not bundle proprietary Apple fonts.
- **Color/material:** neutral reading canvas; Daedalus brand gold accent sparingly; meaningful error/warning/success status with icon+text, never color alone. Light/dark modes. At most one useful translucent toolbar/sidebar layer; opaque contrast/reduced-transparency fallback. Avoid a stacked-glass look.
- **Layout:** measured spacing tokens, aligned columns, context before controls, one major action per focus area, dense readable data tables without decorative dashboard KPI clutter. Navigation sidebar plus optional inspector on desktop; collapsible navigation/tablet; stacked list/detail and sticky non-obscuring actions/mobile.
- **Motion:** instant press/focus response; interactions start from triggering controls, enter/exit same path; touch drag follows pointer with offset, momentum and interruptible/retargetable springs where appropriate. Prefer critically damped response without default bounce. No delayed input, looping decorative movement, janky full-page transitions or automatic success celebrations. Reduced motion switches to short opacity/static feedback.
- **Accessibility:** WCAG 2.2 AA target, visible focus, tab order, ARIA semantic controls/tabs, Escape dismiss, logical Cmd/Ctrl+K search, 200% zoom, text labels for every status, VoiceOver/Safari and NVDA/Chrome testing, reduced-transparency/high-contrast variants. No shortcut silently performs mutations.

## Page information architecture

1. **Overview:** connection and session readiness, all/selected/one account scope, observed time, uncertain tasks and direct safe actions. Missing data is unknown, never zero.
2. **Accounts:** searchable master/detail with real permitted email/world flags and explicit session states; backend revision-gated edits only where enabled. Desktop-only Selenium login guidance in account detail; no web Gameforge password fields.
3. **Warehouses:** all accounts first-class by default; Selected(n)/Single, grouped islands, original 220K unsecured filter and semantics, table sorting, accurate resource totals and unavailable rows, print-friendly combined report and TXT/CSV/JSON exports.
4. **Automations:** category tabs All / City & research / Resources & trade / Military & missions / Alerts & exploration / System & advanced; searchable list plus contextual inspector. Real city/building/route/research/units/market/scheduling inputs; visible preflight, authoritative preview, review, explicit confirmation. Advanced JSON import is hidden and validated—not ordinary UI.
5. **Military:** read-only Troops/Fleet/Movements, one/selected/all accounts, freshness, separate errors for unavailable workers.
6. **Activity:** Running, History, Uncertain request views; per-account provenance and timestamps, managed-only Stop after impact review and independent reconciliation. Never claim game success on request submission.
7. **Settings:** appearance, density, accessibility, web session status/logout, safe backend capabilities/connection health. Never show or edit backend bearer/SSH credentials in the browser.

## Acceptance artifacts

Before feature implementation: two **interactive** light/dark prototype journeys using actual Daedalus branding. Final: screen-by-screen visual baselines for all pages at desktop/tablet/mobile and light/dark, plus loading/empty/error/expired-session states. Test slow network, account isolation, long city names, right-to-left labels, huge resource counts and mismatched world status. A passing TypeScript build does not equal Apple-quality experience approval. Reference the `apple-design` skill explicitly in UI review notes.
