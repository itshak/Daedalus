# Web parity inventory (proposal)

**Controller remains authoritative.** Track each desktop capability and upstream operation through a live FastAPI capability check, account/session scope, web-specific UI and verification. Values are **Supported**, **Read-only**, **Needs backend adapter**, **Desktop-only** or **Unavailable**, not guesses inferred from catalog naming.

| Area | Existing FastAPI surface | Web requirement |
| --- | --- | --- |
| Overview | `GET /api/v1/health`, `accounts`, `capabilities`, `accounts/{id}/session` | Real readiness, freshness and capability gating |
| Accounts | `GET accounts`, sessions, optional `GET/PUT account-config` | Protected identity/world, one/selected/all, revision-safe edits only in editing mode |
| Warehouses | `GET warehouses/{id}` | Combined one/selected/all report, island grouping, 220K unsecured threshold, per-account failure, print/TXT/CSV/JSON |
| Cities/buildings | `accounts/{id}/cities`, `cities/{city_id}/buildings`, `construction-preview` | Real account-owned building table, engine preview and confirmation |
| Academy/tavern/faith | `academies`, `taverns`, `miracles`, `shrine-status` | Authenticated real-data selectors, safe task forms |
| Trade/training/piracy | `market-quotes`, `trainable-units`, `workshop-upgrades`, `pirate-fortresses` | Source-verified offer/unit/action tables, no guessed pricing |
| Military | `military`, `ship-movements` | Read-only troops, fleet, movements across account scope |
| Tasks | `task-control`, `tasks/preflight`, `GET/POST tasks` | Approved per-account requests, typed editors, state/outcome tracking |
| Activity | `tasks/{task_id}/stop`, `tasks/requests/{request_id}/acknowledge` | Managed-only stop and no-retry-uncertain reconciliation |
| Native login | `native-browser-login`, `login-vaults` and recovery routes | **Never browser-proxied**; status and Mac sign-in guidance only |
| Interactive-only menu actions | Not generic task API | **Needs backend adapter**; otherwise explanatory read-only/disabled state |

Reconcile the complete catalog and action-specific form requirements from `docs/AUTOMATION-UX-AUDIT.md`, including constructionList, research, tavernManager, loginDaily, activateMiracle, activateShrine, transport/consolidation/distribution, trading, donationBot, trainArmy, UpgradeUnits, autoPirate, alertAttacks/alertLowWine, searchForIslandSpaces, dumpWorld, viewArmy, shipMovements and interactive-only menu functions. A native GUI control does not imply a safe web controller endpoint. Also respect current optional controller modes that can forbid editing and task execution together.
