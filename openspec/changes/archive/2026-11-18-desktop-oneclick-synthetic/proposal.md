# One-click isolated synthetic demo in the native Mac desktop

## Why
Even though Daedalus has a working native GUI and synthetic backend, testing currently requires two separate terminal commands, generating a bearer token and pasting it into the app. This creates avoidable friction when the user wants to test the actual Mac preview without real accounts.

## What changes
- Add an explicitly labeled Try offline demo action to the native Connection page.
- Start a private ephemeral synthetic FastAPI backend on an OS-selected loopback port only after the user clicks the action; generate a strong in-memory bearer token, connect the existing desktop API client automatically, and never save the token to keyring or preferences.
- Reuse a running demo when requested again, and stop it when the desktop closes.
- Keep demo_mode isolation: no accounts.toml, IkaBot IPC, Gameforge login, browser cookies, task dispatch or account mutation.
- Add server extras to the native desktop distribution and collect required Uvicorn modules in the macOS preview bundle.
- Test actual loopback API bearer isolation, synthetic snapshots, launch/relaunch/cleanup, UI action, and packaging arguments offline.

## Modified capabilities
- `desktop-client`: one-click synthetic backend lifecycle and connection.
- `security-boundaries`: ephemeral local token and demo isolation without account access.

## Non-goals
No real game login, worker bootstrap, automatic task resume or packaged production release. Native app remains an ad-hoc signed preview.
