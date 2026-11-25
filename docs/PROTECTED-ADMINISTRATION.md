# Protected administration

Daedalus Settings exposes nonsecret account-scoped status, worker-global notification defaults, host-approved extensions, and public release discovery. The browser requires an authenticated owner for settings mutations; native desktop uses the authenticated controller bearer. Game credentials and raw game service endpoints are not exposed. Proxy changes and connectivity testing are deferred at the owner's request.

## Locally approved extensions

The worker administrator, not the browser, reviews and installs extension code. Put approved source files in the worker user's `~/.ikabot/approved-extensions/` directory. Use a private directory (0700 on POSIX) and files owned by the worker user without group/world write access. Symlinks are not accepted. Each source file must be named `<id>.py`, no larger than 1 MiB. The local `manifest.json` is bounded to 32 entries and 64 KiB. For example, a manifest has version 1 and an extensions array containing objects with id, name and sha256 fields. The digest must be the actual SHA-256 of the reviewed file; a placeholder will fail verification.

In Settings, select an enabled account on the intended worker, read approved extensions, select the verified item and review its ID/hash and desired registration. Registering makes it available in the upstream shared default menu. Unregistering removes only its registration, not the file. The worker rejects stale state or an unapproved hash. Existing unreviewed registrations are counted but their paths are never returned; a per-user override requires local reconciliation before changing shared defaults.

These controls never run arbitrary code. Upstream local custom modules execute with the worker's privileges; only a trusted host administrator should inspect and run them locally. Re-review a changed module before use. The remote registration guard is not a sandbox or runtime signature enforcement for the legacy CLI.

## Releases

Settings can check the fixed public Daedalus GitHub release catalog for a published Mac preview containing both the DMG and its SHA-256 checksum. It never installs an update. The published preview is ad-hoc signed, not notarized. Follow [MACOS-BUILD.md](MACOS-BUILD.md) and the host rollout and rollback procedure in [LIVE-ACCEPTANCE.md](LIVE-ACCEPTANCE.md). Synthetic demo stays offline.
