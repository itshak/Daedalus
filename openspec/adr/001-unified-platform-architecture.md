# ADR-001: One engine, one product, two execution locations

**Status:** Accepted (design baseline)

## Context
Public IkaBot offers mature game operations. A separate local PySide6 application provides warehouse reporting, a preferred GUI and useful Selenium-assisted login. The current server runs bot sessions independently.

## Decision
Daedalus will be a self-contained monorepo with an upstream-tracked IkaBot engine, a Python backend and a complete native PySide6 client. A versioned backend API serves desktop clients on the same device or a remote server. Engine operations run locally to the backend through a validated adapter, not via GUI keystrokes.

## Consequences
No rewritten game protocol client, no desktop-to-game direct login for routine snapshots, no dependency on tmux as task state. Local and remote deployments share API schemas and behavioral tests.
