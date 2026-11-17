# Migrate and expand the native PySide6 GUI

## Why
The existing Mac GUI has a valued Fluent UI, warehouse reports, exports and login assistance. Rewriting it as a web application adds unnecessary risk.

## What Changes
- Port audited PySide6 views and report models to a renamed Daedalus namespace.
- Use one backend API client for local and remote execution.
- Support all registered public IkaBot tasks with typed forms and dedicated key workflow screens.
- Preserve existing warehouse layout and exports; replace routine Selenium scraping with engine session snapshots.

## Capabilities
### Modified Capabilities
- `desktop-client`: full engine UI coverage.
- `warehouse-monitoring`: preserve familiar reports over backend data.

## Non-goals
No web UI rewrite or import of private account files and tokens.

## Impact
A native Mac client with a persistent remote server. See ADR-001, ADR-004 and ADR-005.
