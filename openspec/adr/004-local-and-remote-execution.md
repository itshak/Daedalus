# ADR-004: One API for local and remote clients

**Status:** Accepted (design baseline)

## Decision
The same versioned, authenticated backend API serves a local GUI or securely connected remote GUI. The service is supervised independently of desktop lifetime. Task status, configuration, snapshots and notifications are backend-owned. Do not expose raw IkaBot proxy endpoints or IPC files to untrusted networks.

## Consequences
The Mac can close while the server continues. Users can deploy local-only installations; the desktop never requires a separate implementation of game operations.
