# Native macOS Daedalus.app — CI-first packaging

This is a **preview build** of the *read-only* native GUI. It does not embed the server, any IkaBot game session, users' saved credentials, browser profiles, or existing scraper settings. Game-task execution and assisted login are not yet implemented.

The build is adapted from the owner's earlier `packaging/build_macos_app.py` for the private PySide6 GUI. The previous tool installed IkaBot.app into `/Applications`, seeded a legacy configuration file, and bundled Selenium/undetected-chromedriver. **All three behaviors are intentionally absent here.**

## Local macOS build

Requires a Mac, Python 3.11+, and project dependencies:

```bash
python -m pip install -e ".[desktop,macos-build]"
python packaging/build_macos_app.py --output-dir dist --adhoc-sign
open dist/Daedalus.app
```

You can inspect the command on any platform without building:

```bash
python packaging/build_macos_app.py --dry-run
```

The bundle uses the committed `assets/brand/app-icons/macos/Daedalus.icns` as its Dock/Finder icon and ships the same brand as a Qt window icon via the package resources. Assets may be regenerated with `python packaging/generate_brand_assets.py` after installing `.[desktop]`.

The script creates the native PyInstaller `Daedalus.app` bundle from the **checked-out Daedalus source**. It never modifies `/Applications`. It does not seed `~/.ikabot` or `~/.config/daedalus`.

The `--adhoc-sign` option creates an **ad-hoc signature** suitable for local testing; it is not notarized and is not a Developer ID signature. Gatekeeper may prevent installation by other users, so do not represent this as a production-signed public release.

## GitHub CI

The `macos-app.yml` workflow builds the preview app on macOS, verifies its bundle and ad-hoc signature, and archives it as a short-lived GitHub Actions artifact. Artifacts are built only from the current source checkout, with unprivileged read-only GitHub permissions. There are no game-account secrets, deployment tokens or PyPI credentials.

The workflow intentionally does **not** release automatically, notarize, attach an update feed or install an app on a runner.

## Native browser requirements

The ad-hoc signed preview now bundles `PySide6.QtWebEngineCore`, `PySide6.QtWebEngineWidgets`, `QtWebEngineProcess`, resource files, and the `cryptography` implementation used for one-use encrypted session handoff. The macOS CI build verifies the modules and helper process are present. Native Qt tests use synthetic Gameforge accounts and no live login; macOS real CAPTCHA and binary execution still require owner acceptance. Browser profile data is off-the-record and not packed into the application artifact.


## Automatic Gameforge Selenium support (headless default)

The macOS preview now includes `selenium`, `undetected-chromedriver`
and `webdriver-manager` in `daedalus[desktop]` and the PyInstaller bundle.
Google Chrome or a compatible ChromeDriver is still needed on the Mac,
and first-use driver provisioning may require access to its official
distribution endpoints. The app uses headless Chrome for normal login and
opens visible Chrome **only** when a Gameforge CAPTCHA is detected.
The original warehouse bot's legacy config/session files are read only
for explicitly selected accounts and never bundled into the installer.
The app passes only an encrypted world-cookie handoff to the backend;
no automated CAPTCHA solving is implemented. macOS packaging CI is
synthetic and does not log into Gameforge.
