# Design — reproducible Mac GUI artifact

Use the checked-out `daedalus.desktop:main` entry point and PyInstaller. Collect Fluent Widgets and frameless-window helper modules; do not package the old Selenium worker, private configuration or runtime browser state.

The build generates a temporary launcher in an OS-managed temporary directory, uses explicit argv list for subprocess execution (no shell), and outputs only to a specified directory. Optional ad-hoc codesign can be used on Apple Silicon, but this is not a notarized or developer-signed release.

The build script supports a dry-run on Linux/Windows to validate options and prove it does not run external commands. The macOS CI workflow uses read-only permissions, creates a verifiable bundle and uploads a short-lived artifact; it does not publish a release or write to /Applications.

The UI retains the source license/provenance obligations. Binary license checks and distribution terms remain a separate release gate.
