# Changelog

## 0.1.0 — first public prerelease

Python, web and macOS application version: `0.1.0`. This is a beta-quality first release, not stable certification. The publication status is authoritative on GitHub Releases.

### Added
- Shared multi-account Python controller, native macOS Fluent application and private Next.js web control center.
- Account-scoped warehouse and military reports, filtering, sorting, exports and printing, with an online-only two-minute warehouse cache.
- Typed reviewed automation editors, independent batch scopes, activity receipts, managed stop, protected administrative views and localization.
- Warehouse account selectors, table, search, and reports display game player names instead of login emails; duplicate names retain world/account disambiguation.
- Compact desktop workspace, six settings sections, improved account/military tables and 142 automated synthetic screenshots covering all 33 operation editors.
- Server-side operator-allowlisted sign-in, bounded gateway bodies and redacted audit metadata.
- Headless-first Mac login, encrypted verified session handoff, default-on delayed recovery and durable safe-job reconciliation including confirmed owned-city fixed cargo.

### Release engineering
- Version-gated Vercel builds: ordinary pushes skip deployment; version increments and explicit manual deployments remain supported.
- Reproducible release staging with exact CI, Mac package provenance and SHA-256 verification; server-only wheel smoke testing.

### Safety and compatibility
- Upstream-first IkaBot request, parser, shipment and fleet-wait reuse.
- Explicit account ownership, reviewed game mutations and no replay of uncertain requests.
- Public synthetic CI; no live credentials or game effects in automated tests.

### Known limitations
- No full upstream option-level or live-game certification; protected local operations remain local. See [beta operation scope](docs/BETA-OPERATION-SCOPE.md) for experimental protected-session paths.
- Hosted Supabase Free does not include leaked-password protection; no plan change is made.
- Preview macOS DMGs are not notarized. Real task effects, game takeover/restoration and physical host reboot await owner acceptance.
- See [engineering status](docs/PROJECT-STATUS.md) and [owner acceptance](docs/V010-OWNER-ACCEPTANCE.md).
