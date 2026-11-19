# Change: Compact native desktop UI

## Why
The recently expanded macOS UI overwhelms its tables with long descriptions, large action cards and a persistent account detail/action panel. The original local Ecobot GUI favored a small account toolbar, row selection, and only the controls needed for the immediate workflow.

## What changes
- Return Accounts to one full-width table; present Add as a small toolbar button and keep Sign in / Sign in all visible.
- Move account-specific and expert recovery actions into an accessible overflow menu.
- Keep all-account warehouse collection, selected-account scope and familiar resource table, with a compact print/export toolbar.
- Reduce card heights, repeated explanatory copy, and always-expanded automation discovery.
- Harmonize macOS-like neutral colors, compact headings, and table row density across pages.
- Preserve original API contract, side-effect confirmations, report output and test interfaces.

## Scope
Native PySide6 presentation only; no changes to authentication, task dispatch, backend or secrets.
