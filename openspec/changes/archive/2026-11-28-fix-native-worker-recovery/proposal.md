# Fix native worker recovery and status reporting

## Why

A native browser-cookie worker can remain alive after the game invalidates its session. The saved-cookie manager was independent of the automatic recovery supervisor, while the desktop poll refreshed assistance tickets only. A live process therefore appeared authenticated even when actual game reads failed.

## What Changes

- Transfer independently verified native workers into the existing recovery owner and monitor, retaining one account lease and the original upstream IPC attestation.
- Respect durable recovery grace, policy and pause; do not let periodic cookie retries bypass these gates.
- Make monitored invalid session and worker indicators agree; refresh both in the desktop poll and show unknown on polling failure.
- Permit explicit browser recovery after a confirmed stopped owner exhausts unattended recovery. Preserve job reconciliation and protected lobby-token requirements.
- Keep legacy one-shot warehouse-fill jobs manual-only until their accepted cargo can be durably reconciled.

## Impact

- Affected specifications: account-sessions, automation-controller, desktop-client.
- Affected code: cookie worker lifecycle, recovery supervisor, account API and desktop status refresh.
- No game-operation request or authentication secret format changes.
