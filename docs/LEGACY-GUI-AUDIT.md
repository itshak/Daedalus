# Legacy Mac GUI source and license audit

Reviewed on **2026-11-18** against the owner's private `itshak/ikabot` source tree (main), the Daedalus desktop source and the declared Python package dependencies. This is a **source and dependency audit**, not certification that every legacy behavior is ported or ready for binary distribution. No private settings, account files, tokens, cookies, browser profiles or production data were copied.

## Source-to-feature reconciliation

| Legacy source | Intended behavior | Daedalus replacement | Remaining boundary |
| --- | --- | --- | --- |
| `src/ikabot/gui/main_window.py` | Fluent navigation, macOS traffic lights, log bridge, cancelable run | `desktop/app.py`, standalone backend client and worker thread | Legacy Selenium runner intentionally not imported |
| `gui/accounts_page.py`, `gui/dialogs.py` | User selection and account editor | `desktop/pages.py` Accounts, protected metadata CRUD and report inclusion/select-all | Password fields excluded; assisted login separate |
| `gui/run_page.py`, `report.py`, `models.py` | Warehouse table, 220K filter, CSV/JSON/TXT and island export | `desktop/pages.py`, `reporting.py`, read-only API, multi-account reports and island clipboard | Live reports require verified sessions; no Selenium scraping |
| `gui/log_page.py`, `gui/theme.py`, `gui/widgets.py` | Buffered logs, Fluent styling and scrolling tables | Matching `desktop/` modules and local `appearance_page.py` | Theme persisted privately; no credential settings |
| `gui/settings_page.py`, `settings.py` | Browser options, debug, credentials and theme | `Connection` and local-only `Appearance` pages, versioned GUI preferences | Password and browser settings excluded pending security review |
| `gui/worker.py`, `browser.py`, `login.py`, `runner.py` | Local Selenium/browser-backed game login, scraping and manual steps | Lease/state protocol, saved-cookie validation, explicit existing-session task worker | Real browser assistance, protected remote handoff and validated task resume are still incomplete |

The Daedalus Tasks page and dedicated Wine/Construction workflow pages offer managed IkaBot task controls and reviewed typed task parameters absent from the legacy GUI. Only backend-registered background tasks can launch, with explicit operator confirmation.

## Ownership and license findings

- The legacy private source checkout has **no tracked LICENSE or NOTICE file**. Treat it as private, author-owned source and **do not copy it wholesale** into Daedalus or assume it carries a public license. The existing UI adaptations are attributed to the project owner's original implementation in `docs/GUI-MIGRATION.md`. Any future code port must be separately reviewed for ownership and redistribution rights.
- Daedalus declares **GPL-3.0-only**, and its vendored upstream IkaBot engine retains separate MIT provenance and notices (see `engine/UPSTREAM.md`).
- Installed metadata inspected for the GUI audit: `PySide6 6.12.0` advertises **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only**; `PySide6-Fluent-Widgets 1.11.3` declares **GPLv3**. The current GPL-3.0-only source direction is consistent with these metadata labels, but any distributed executable must also satisfy applicable Qt/PySide6 notices, dynamic linking/replacement obligations, third-party licenses and packaging requirements.
- The private legacy application declares Selenium, webdriver-manager, undetected-chromedriver, PySide6 and PySide6-Fluent-Widgets. Selenium browser orchestration and its dependencies were **not** carried into the currently shipping Daedalus desktop extras. Re-evaluate browser-driver terms and maintenance status before adding any optional login assistant.
- Bearer tokens, account cookies and browser sessions are not part of the public source or docs. **Never** use real account credentials or an active production profile for CI, demos or compatibility tests.

## Audit conclusion and remaining release/authentication gates

The audited nonsecret GUI features (account report inclusion, metadata editing,
grouped warehouse exports, theme and display preferences) are now implemented
with synthetic native regressions and local-only secure settings tests. They
close `migrate-native-desktop`; no private credentials or Selenium code
were copied.

Secure browser login/manual CAPTCHA assistance, host-only remote recovery,
independent server-side player identity attestation and real-account acceptance
are **not** part of GUI migration; they remain active in
`validate-live-authentication`. The project must separately pass supervised
Mac integration testing and complete Qt/PySide6 binary redistribution notice
and notarization review before any production release.
