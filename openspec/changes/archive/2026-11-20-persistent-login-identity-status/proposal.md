# Persistent encrypted logins and compact account identity

## Why
Existing migrated IkaBot accounts retain generic labels, and Mac Selenium asks
for passwords when its local Keychain lacks a record. The account table also
shows technical states and unresolved Russian server codes.

## What changes
Return protected email bindings over bearer-authenticated metadata, prefer
emails in the account table, show world flags and accessible status icons,
and enable an encrypted server-backed login vault. Reuse macOS Keychain for
the sole decryption key and support explicit opt-in background migration.

## Impact
Native GUI, authenticated controller, encrypted secret storage and tests.
Existing live account records, tasks and cookies are never rewritten or
restarted by source changes. Missing legacy passwords require user entry.
