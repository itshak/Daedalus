# Change: Native, account-aware IkaBot automation workflows

## Why
The existing Automations page still exposes the engine's raw decorator arguments as forms (for example, nine generic JSON fields for constructionList). It mixes task discovery, account scope, configuration and task monitoring into a dense screen. A user cannot safely choose actual buildings, routes, unit types or city resources because the current read API exposes city identities only, not the contextual game state needed for those choices.

## User-visible outcome
- Five approachable operation groups with contextual task cards, persistent search, concise summaries and separate Running / History.
- An actual purpose-built editor for **each supported IkaBot operation**, including background tasks and read-only/interactive-only legacy menu functions. An action is never made executable merely because it appears in the catalog.
- Live selectors and tables for cities, buildings, resources, transports, markets, armies, research and islands; data always comes from the selected authenticated account, not guessed IDs or stale local fixtures.
- Reviewable plans with friendly validation, resource/ship/ETA previews where the upstream engine can safely compute them, and explicit per-account consent. Advanced import is a fallback, not the normal input path.
- Multi-account viewing and policy batching for compatible operations, with account-specific values prepared and approved independently; no city-specific plan broadcast to different accounts.

## Scope / dependencies
- Desktop PySide6/qfluentwidgets operation workspace, domain form components, offline test fixtures and accessibility.
- Read-only, authenticated, account-scoped engine IPC descriptors with typed DTOs, validation and snapshot freshness.
- A reviewed prepare/preview path that reuses upstream IkaBot rules without submitting a game mutation.
- Audited native execution adapters that lower reviewed UI values to exactly the public IkaBot task parameters.
- Source-by-source interaction inventory in design.md and docs/AUTOMATION-UX-AUDIT.md.

## Constraints
Do not create a second game client, scrape live credentials, bypass CAPTCHA, make unreviewed menu functions dispatchable, or send arbitrary secrets in task configuration. Preserve existing idempotency, durable receipts, session ownership, no-retry-on-uncertain-result, and human-only acceptance gates. A missing authoritative read model must produce a clear disabled/needs-data state, not imaginary choices.

## Relationship to other changes
This is a domain-specific continuation of the active redesign-macos-desktop-experience change. Keep this change active until all operation-specific implementations, offline tests and canonical specs are complete; do not archive an unfinished capability or label a proposal as production-ready.
