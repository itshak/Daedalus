# Design — first native GUI integration

The GUI runs as a distinct `daedalus-desktop` script using optional `daedalus[desktop]` dependencies. Retain FluentWindow sidebar, Mac titlebar adaptation, palette, scroll table and signal-driven log handling from the legacy project. Do not import the old `ikabot` GUI Python namespace.

A small `DaedalusClient` wraps versioned read-only FastAPI endpoints using httpx. It requires a bearer token, rejects HTTP outside loopback, disallows URLs with embedded credentials, sends no task-changing requests and excludes response bodies from exceptions. A QRunnable/QThread-style worker isolates HTTP calls from the Qt event loop.

The connection form masks the token, does not persist it, and clears it after a successful connection. A user may run the backend on the same Mac or connect through an authorized SSH loopback tunnel or HTTPS endpoint.

UI pages are read-only. Operations renders the engine registry without pretending all modules can launch. Accounts renders backend metadata and session state without email/password editing. Warehouses renders available snapshots, unknown resources as empty/unknown, preserves 220K filtering, and permits copy/CSV/JSON export. Empty/unavailable warehouse data is not fabricated.

Tests include synthetic mock transport, secret-redaction assertions and headless native UI smoke tests. The standard matrix remains lightweight; macOS CI installs Qt and Fluent Widgets to exercise the real interface. No game network traffic is executed.
