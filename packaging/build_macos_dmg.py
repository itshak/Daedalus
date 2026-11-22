#!/usr/bin/env python3
"""Build a BlindBase-style HFS+ DMG with a user-initiated preview installer.

BlindBase includes a readme_first.txt with an xattr -cr instruction because
its first-run DMG is not Apple-notarized. This package keeps that instruction,
the drag-to-Applications shortcut, and an optional *explicitly run* helper that
copies the signature-verified app and removes quarantine only on that copy.

Neither a DMG nor a shell installer automatically bypasses macOS Gatekeeper.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_BUNDLE_ID = "io.github.itshak.daedalus"
INSTALLER_NAME = "Install Daedalus.command"
README_NAME = "readme_first.txt"
INSTALLER_SOURCE = Path(__file__).resolve().parent / INSTALLER_NAME

README_TEXT = """Daedalus macOS Installation Instructions
=========================================

Daedalus is a development preview without an Apple Developer ID signature.
Like BlindBase, macOS may block a first launch from a normal drag-and-drop
install. The two installation choices are:

OPTION 1 - Easier preview installation (user-initiated):
  Run "Install Daedalus.command" from this volume. This copies the verified
  Daedalus.app to ~/Applications and removes only the copied app's
  com.apple.quarantine extended attribute. It does not alter global Gatekeeper
  settings. Depending on your Mac's policy, Finder may require you to open
  Terminal and run the command explicitly instead.

OPTION 2 - Exact BlindBase drag-and-drop procedure:
  Drag Daedalus.app to Applications, then in Terminal run:

    xattr -cr /Applications/Daedalus.app

  Launch Daedalus from Applications. The command is the same app-specific
  quarantine-clearing step documented by BlindBase, not a global policy change.

These instructions apply only if you trust the source of this exact build.
To avoid a first-launch override altogether, the publisher needs an Apple
Developer ID signature and Apple notarization.
"""


def check_app(app: Path) -> None:
    if not app.is_dir() or not (app / "Contents/MacOS/Daedalus").is_file():
        raise RuntimeError(f"Missing or incomplete Daedalus.app: {app}")
    identity = subprocess.check_output(
        ["/usr/libexec/PlistBuddy", "-c", "Print :CFBundleIdentifier",
         str(app / "Contents/Info.plist")],
        text=True,
    ).strip()
    if identity != EXPECTED_BUNDLE_ID:
        raise RuntimeError(f"Unexpected bundle identifier: {identity}")
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)


def make_dmg(app: Path, output: Path) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("macOS disk images must be created on a Mac")
    app = app.expanduser().resolve()
    output = output.expanduser().resolve()
    check_app(app)
    if output.suffix.lower() != ".dmg":
        raise RuntimeError("Output must be a .dmg file")
    if not INSTALLER_SOURCE.is_file():
        raise RuntimeError("Missing reviewed Daedalus installer")
    subprocess.run(["bash", "-n", str(INSTALLER_SOURCE)], check=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    # BlindBase's DMG uses an HFS+ read/write image, then UDZO conversion.
    # Preserve that disk format and no-Finder-automation build process.
    app_kib = int(
        subprocess.check_output(["du", "-sk", str(app)], text=True).split()[0]
    )
    size_mb = max(200, int(app_kib * 1.5 / 1024) + 60)
    with tempfile.TemporaryDirectory(prefix="daedalus-dmg-") as temp:
        root = Path(temp)
        rw_image = root / "Daedalus-rw.dmg"
        volume = root / "volume"
        volume.mkdir()
        subprocess.run(
            ["hdiutil", "create", "-size", f"{size_mb}m",
             "-fs", "HFS+", "-volname", "Daedalus", str(rw_image)],
            check=True,
        )
        attached = False
        try:
            subprocess.run(
                ["hdiutil", "attach", "-nobrowse", "-mountpoint",
                 str(volume), str(rw_image)],
                check=True,
            )
            attached = True
            copied = volume / "Daedalus.app"
            subprocess.run(["ditto", str(app), str(copied)], check=True)
            check_app(copied)
            os.symlink("/Applications", volume / "Applications")
            (volume / README_NAME).write_text(README_TEXT, encoding="utf-8")
            shutil.copy2(INSTALLER_SOURCE, volume / INSTALLER_NAME)
            (volume / INSTALLER_NAME).chmod(0o755)
        finally:
            if attached:
                subprocess.run(["hdiutil", "detach", str(volume)], check=True)

        subprocess.run(
            ["hdiutil", "convert", str(rw_image), "-format", "UDZO",
             "-imagekey", "zlib-level=9", "-o", str(output), "-ov"],
            check=True,
        )
        subprocess.run(["hdiutil", "verify", str(output)], check=True)
    print(f"BlindBase-style DMG ready: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=Path("dist/Daedalus.app"))
    parser.add_argument("--output", type=Path,
                        default=Path("dist/Daedalus-macos-preview.dmg"))
    args = parser.parse_args()
    try:
        make_dmg(args.app, args.output)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
