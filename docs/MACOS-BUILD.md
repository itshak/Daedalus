# Native macOS Daedalus.app — CI-first packaging

This is a **development preview** of the native Fluent desktop GUI. It does not embed the server, an IkaBot game session, saved credentials, browser profiles, or existing scraper settings. The built-in login and task controls depend on the separate backend and still require owner-supervised live acceptance.

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

## macOS drag-and-drop DMG — preferred installation

Daedalus follows BlindBase's **GitHub Releases** distribution model: a verified
`Daedalus-macos-preview.dmg` is attached directly to a public prerelease,
**not wrapped in an Actions ZIP**.

1. Open [Daedalus Releases](https://github.com/itshak/Daedalus/releases)
   and select the latest **Desktop Preview** prerelease.
2. Click `Daedalus-macos-preview.dmg` under **Assets**. Your browser downloads
   the **DMG itself**, without another ZIP extraction step.
3. Double-click the DMG and drag **Daedalus.app** onto **Applications**.

Each successful `main` build publishes a separate preview tagged
`desktop-preview-<12-character commit SHA>`, alongside
`Daedalus-macos-preview.dmg.sha256` for file integrity checks. Pull-request
builds never publish public releases. GitHub Actions may still retain
ZIP-wrapped artifacts for CI debugging; those are **not** the primary download.


**No install script or Terminal command is required for the drag-and-drop step.** The DMG includes only the app and Applications link; it cannot automatically execute a script.

**Gatekeeper limitation:** like BlindBase's first-install DMG, this build remains ad-hoc signed and **not Apple notarized**. Installing from a DMG is convenient, but macOS may still block the app on first launch. This packaging change does **not** promise a warning-free first launch. BlindBase automatically uses `xattr -cr` only **after an in-app update**, once its original app is already running; its first-install documentation still describes manual approval/quarantine removal. Shipping a DMG cannot silently override macOS security checks. For guaranteed standard first-launch behavior on typical Macs, distribute a Developer ID-signed and Apple-notarized build.

The older **Daedalus-macos-app-preview** ZIP artifact and optional `Install Daedalus.command` remain as an alternative for explicitly trusted local preview installs, but are **not part of the DMG**. The new primary workflow does not ask users to run them. Never globally disable Gatekeeper.

## Local macOS DMG build

After building the signed local preview app as above, run:

```bash
python packaging/build_macos_dmg.py --app dist/Daedalus.app --output dist/Daedalus-macos-preview.dmg
```

This verifies the ad-hoc code signature and bundle identifier, uses `ditto` to stage the app, creates an `/Applications` link, builds a compressed UDZO DMG with `hdiutil`, and verifies the disk image. No Finder Automation permission or desktop session is required for packaging.

## GitHub CI

The `macos-app.yml` workflow builds a DMG, mounts it on the macOS runner,
checks the app and Applications symlink, verifies the code signature, and
runs a synthetic ZIP installer check. **Only after this succeeds**, a separate
`main`-only job with scoped `contents: write` permission publishes the
exact DMG as a **GitHub prerelease asset** with a SHA-256 checksum.
Pull-request jobs have read-only repository permissions; they cannot
publish releases. The workflow does not notarize the app, install it in
the runner's system Applications directory, or publish an automatic update feed.

## Native browser requirements

The ad-hoc signed preview now bundles `PySide6.QtWebEngineCore`, `PySide6.QtWebEngineWidgets`, `QtWebEngineProcess`, resource files, and the `cryptography` implementation used for one-use encrypted session handoff. The macOS CI build verifies the modules and helper process are present. Native Qt tests use synthetic Gameforge accounts and no live login; macOS real CAPTCHA and binary execution still require owner acceptance. Browser profile data is off-the-record and not packed into the application artifact.


## Automatic Gameforge Selenium support (headless default)

The macOS preview now includes `selenium`, `undetected-chromedriver`
and `webdriver-manager` in `daedalus[desktop]` and the PyInstaller bundle.
Google Chrome or a compatible ChromeDriver is still needed on the Mac,
and first-use driver provisioning may require access to its official
distribution endpoints. The app uses headless Chrome for normal login and
opens visible Chrome when a CAPTCHA is detected or headless login fails.
The original warehouse bot's legacy config/session files are read only
for explicitly selected accounts and never bundled into the installer.
The app passes only an encrypted world-cookie handoff to the backend;
no automated CAPTCHA solving is implemented. macOS packaging CI is
synthetic and does not log into Gameforge.
