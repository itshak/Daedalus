# Protected administration

Daedalus Settings exposes nonsecret account-scoped status, worker-global notification defaults, host-approved extensions, and public release discovery. The browser requires an authenticated owner for settings mutations; native desktop uses the authenticated controller bearer. Game credentials and raw game service endpoints are not exposed. Account-specific proxy profile selection and fixed HTTPS connectivity testing require host-approved local profiles. Raw endpoint and authentication provisioning remain host-local.

## Locally approved extensions

The worker administrator, not the browser, reviews and installs extension code. Put approved source files in the worker user's `~/.ikabot/approved-extensions/` directory. Use a private directory (0700 on POSIX) and files owned by the worker user without group/world write access. Symlinks are not accepted. Each source file must be named `<id>.py`, no larger than 1 MiB. The local `manifest.json` is bounded to 32 entries and 64 KiB. For example, a manifest has version 1 and an extensions array containing objects with id, name and sha256 fields. The digest must be the actual SHA-256 of the reviewed file; a placeholder will fail verification.

In Settings, select an enabled account on the intended worker, read approved extensions, select the verified item and review its ID/hash and desired registration. Registering makes it available in the upstream shared default menu. Unregistering removes only its registration, not the file. The worker rejects stale state or an unapproved hash. Existing unreviewed registrations are counted but their paths are never returned; a per-user override requires local reconciliation before changing shared defaults.

These controls never run arbitrary code. Upstream local custom modules execute with the worker's privileges; only a trusted host administrator should inspect and run them locally. Re-review a changed module before use. The remote registration guard is not a sandbox or runtime signature enforcement for the legacy CLI.

## Releases

Settings can check the fixed public Daedalus GitHub release catalog for a published Mac preview containing both the DMG and its SHA-256 checksum. It never installs an update. The published preview is ad-hoc signed, not notarized. Follow [MACOS-BUILD.md](MACOS-BUILD.md) and the host rollout and rollback procedure in [LIVE-ACCEPTANCE.md](LIVE-ACCEPTANCE.md). Synthetic demo stays offline.

### Human challenge handling

Managed piracy stops at a game challenge. Set the selected account's policy to stop (default) or notify-and-stop in Settings. The latter requires a configured supported notification destination and sends one fixed notice without challenge contents. Complete the challenge manually before starting a new reviewed task. Legacy automated solver configuration is not available through either remote client.


## Aggregate world map reports

Run a managed world scan from Automations. For completed scans, select the appropriate account in desktop Settings → Aggregate world map reports or web Activity → Aggregate world map reports. Refresh the report inventory, choose a completed report, and export the validated CSV. The data contains only numeric island observations, not upstream raw world-dump files or player/alliance names. A detailed scan also reports luxury-resource level; a shallow scan leaves it blank. Reports are kept privately per worker identity, with a maximum of twenty completed reports; host-local reconciliation is required to free a full report store. Legacy raw dump files and name-based searches remain local.


## Approved proxy profiles

The host administrator must provision each account's approved network profiles before the desktop or web can select them. Use the worker OS account's private IkaBot directory, with a private `approved-proxies` subdirectory. Each manifest filename is the SHA-256 hex digest of the case-folded world identifier, a NUL separator, and the case-folded player name, followed by `.json`. On POSIX use directory mode 0700 and file mode 0600. The manifest contains version 1, an explicit boolean `allow_direct`, and up to sixteen entries with unique `id`, nonsecret display `label`, and locally approved `url`. The profile URL must use http, https, socks4, socks5 or socks5h and an explicit port, with no inline authentication, path, query or fragment. For authenticated network infrastructure the host administrator provisions a local approved forwarding endpoint instead of transferring credentials through Daedalus. Keep labels free of private connection details.

In desktop or web Settings, choose the account, read approved profiles, choose a profile, then explicitly test or test and save. Stop active tasks before making any profile change. The single TLS-verified connectivity check contacts a fixed public HTTPS endpoint, without using the game session or credentials; it is not a game-login or game-connectivity acceptance test. Direct connection is selectable only when locally approved. Changing a profile updates the existing account preference for subsequent upstream requests without forcing a reconnect. If testing fails, state changes, or the outcome is uncertain, refresh before retrying. Legacy unapproved endpoints and authentication remain local. No automatic switching or challenge bypass is provided.
