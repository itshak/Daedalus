# Restore island-grouped native warehouse reports

## Why
The native Daedalus warehouse page supports numeric snapshots and CSV/JSON, but the legacy GUI also grouped cities by island and exported readable text summaries.

## What changes
- Add optional sanitized island coordinates to the existing authenticated IkaBot warehouse IPC response and typed API snapshot.
- Sort native warehouse rows by island on request, show island coordinates, and add human-readable grouped TXT export.
- Preserve unknown amounts as null rather than zero and apply the 220K filter before grouping.
- Keep the source restricted to the current engine-owned game session with no Selenium or competing network client.

## Modified capabilities
- `warehouse-monitoring`: island grouping and safe text export
- `desktop-client`: selectable island ordering and TXT action

## Non-goals
No new game login, second HTTP client, account settings editing, automatic transport actions, or fetching unknown island names.

## Impact
Improved report parity for the existing authenticated-session snapshot path. No production account migration.
