# Legacy Mac GUI source and license audit

Reviewed on **2026-11-18** against the owner's private `itshak/ikabot` source tree (main), the Daedalus desktop source and the declared Python package dependencies. This is a **source and dependency audit**, not certification that every legacy behavior is ported or ready for binary distribution. No private settings, account files, tokens, cookies, browser profiles or production data were copied.

## Source-to-feature reconciliation

| Legacy source | Intended behavior | Daedalus replacement | Remaining boundary |
| --- | --- | --- | --- |
| `src/ikabot/gui/main_window.py` | Fluent navigation, macOS traffic lights, log bridge, cancelable run | `desktop/app.py`, standalone backend client and worker thread | Legacy Selenium runner intentionally not imported |
| `gui/accounts_page.py`, `gui/dialogs.py` | User selection and account editor | `desktop/pages.py` Accounts, API-protected nonsecret metadata CRUD | Secrets and cross-account batch selection are intentionally excluded; assisted login requires a separate design |
| `gui/run_page.py`, `report.py`, `models.py` | Warehouse rows, 220K filter, CSV/JSON/TXT and island export | `desktop/pages.py`, `reporting.py`, read-only snapshot API | Live reports require an already verified engine session; no Selenium scraping fallback |
| `gui/log_page.py`, `gui/theme.py`, `gui/widgets.py` | Buffered logs, Fluent styling and scrolling tables | Corresponding `desktop/` modules | Theme selection and additional local preferences are not yet parity-complete |
| `gui/settings_page.py`, `settings.py` | Browser choices, retries, debug, credentials and theme | Secure `Connection` page, optional OS-keyring-backed connection preferences | No password fields or unsafe legacy config import; browser recovery preferences require a separate security review |
| `gui/worker.py`, `browser.py`, `login.py`, `runner.py` | Local Selenium/browser-backed game login, scraping and manual steps | Lease/state protocol, saved-cookie validation, explicit existing-session task worker | Real browser assistance, protected remote handoff and validated task resume are still incomplete |

The current Daedalus Tasks page also offers managed IkaBot task controls and reviewed typed task parameters absent from the legacy GUI.

## Ownership and license findings

- The legacy private source checkout has **no tracked LICENSE or NOTICE file**. Treat it as private, author-owned source and **do not copy it wholesale** into Daedalus or assume it carries a public license. The existing UI adaptations are attributed to the project owner's original implementation in `docs/GUI-MIGRATION.md`. Any future code port must be separately reviewed for ownership and redistribution rights.
- Daedalus declares **GPL-3.0-only**, and its vendored upstream IkaBot engine retains separate MIT provenance and notices (see `engine/UPSTREAM.md`).
- Installed metadata inspected for the GUI audit: `PySide6 6.12.0` advertises **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only**; `PySide6-Fluent-Widgets 1.11.3` declares **GPLv3**. The current GPL-3.0-only source direction is consistent with these metadata labels, but any distributed executable must also satisfy applicable Qt/PySide6 notices, dynamic linking/replacement obligations, third-party licenses and packaging requirements.
- The private legacy application declares Selenium, webdriver-manager, undetected-chromedriver, PySide6 and PySide6-Fluent-Widgets. Selenium browser orchestration and its dependencies were **not** carried into the currently shipping Daedalus desktop extras. Re-evaluate browser-driver terms and maintenance status before adding any optional login assistant.
- Bearer tokens, account cookies and browser sessions are not part of the public source or docs. **Never** use real account credentials or an active production profile for CI, demos or compatibility tests.

## Remaining acceptance gates

1. Complete any requested nonsecret legacy account selection/preferences UX with native UI tests, while maintaining backend ownership of all game sessions.
2. Add an opt-in audited browser login/manual CAPTCHA path, using only authorized operator interaction and worker verification, without independent competing logins.
3. Implement a protected same-owner remote handoff or authorized remote-browser fallback, then explicitly approved recovery and task resume.
4. Run mocked failure-path tests, static secret scanning, strict OpenSpec validation and an isolated non-production Mac end-to-end run. Verify third-party redistribution notices before public binary release.

This closes the **review/license-audit task only** in `migrate-native-desktop`. It is not evidence that the remaining UI parity, authentication recovery or app release requirements are complete.
