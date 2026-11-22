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

## Download and install the preview without Privacy & Security approval

1. Download the latest **Daedalus-macos-app-preview** artifact from [macOS Actions](https://github.com/itshak/Daedalus/actions/workflows/macos-app.yml).
2. Extract the GitHub Actions artifact ZIP, then extract **Daedalus-macos-preview.zip** inside it. The resulting folder contains **Daedalus.app** and **Install Daedalus.command**.
3. Open Terminal in that extracted folder and run:

   ```bash
   bash "Install Daedalus.command"
   ```

   Depending on the Mac's policies, you may also be able to double-click **Install Daedalus.command** directly in Finder. The Terminal command is the reliable fallback when Finder blocks an untrusted script.

4. The installer verifies the bundle identifier and the ad-hoc code-signature integrity, copies the app to **~/Applications/Daedalus.app**, then removes **only** the `com.apple.quarantine` extended attribute from this installed app. Launch it normally from your Applications folder.

This avoids the manual **System Settings → Privacy & Security → Open Anyway** step for the preview *when the installer runs successfully*. It does **not** disable Gatekeeper globally, modify system settings, require `sudo`, or send credentials anywhere. It may not bypass organization-managed macOS restrictions. Install only artifacts you trust.

**Why this must run on your Mac:** macOS adds quarantine as a download/extraction attribute on the receiving Mac, so an `xattr` command during the GitHub build does not solve first-launch blocking. An ad-hoc signature is not an Apple Developer ID signature or a notarization ticket. The proper public-distribution route remains Developer ID signing plus Apple notarization.

To install a newer preview, run the new installer again. It replaces only an existing app with the expected Daedalus bundle identifier. Your Keychain and application settings are not part of the .app and are not touched.

## GitHub CI

The `macos-app.yml` workflow builds the preview app on macOS, verifies its bundle and ad-hoc signature, archives the app **alongside the local install command**, and tests installing a quarantined extract into a temporary user-owned directory. Artifacts are built only from the current source checkout, with unprivileged read-only GitHub permissions. There are no game-account secrets, deployment tokens or PyPI credentials.

The workflow intentionally does **not** release automatically, notarize, attach an update feed or install an app in the runner's system Applications folder.

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
