# Synthetic offline desktop demo — zero live game dependencies

## Why
The native Mac GUI can run, but without a configured backend and pre-existing authenticated IkaBot session most reports show unavailable. A visibly fake, isolated demo lets users test the entire basic GUI/API/reporting path without credentials or production sessions.

## What changes
- Add explicit `daedalus serve --demo` with synthetic accounts, warehouses and cities, and the normal bearer-authenticated local HTTP service.
- Reject real account files, IPC descriptors, task controls and metadata editing when demo mode is active.
- Label the backend's health, accounts, capabilities and reporting responses as synthetic; label the native GUI's window, connection and warehouses.
- Add API/CLI/client/Qt tests for no game calls, no credential/IPC dependencies and no executable game mutations.

## Modified capabilities
- `controller-api`: synthetic demo representation.
- `desktop-client`: unmissable synthetic UI labels.
- `security-boundaries`: demo/data isolation.

## Non-goals
No actual Gameforge accounts, authenticated workers, login, task execution, external service access or production data. This supplements but does not complete the active worker/authentication proposals.
