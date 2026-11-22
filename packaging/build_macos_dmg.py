#!/usr/bin/env python3
"""Build a simple drag-to-Applications DMG from an already-built Daedalus.app.

Modelled on BlindBase's custom macOS DMG packaging: the disk image contains
only Daedalus.app and an Applications shortcut, so users do not run scripts.
It does NOT sign/notarize the app or bypass macOS Gatekeeper.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_BUNDLE_ID = "io.github.itshak.daedalus"


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
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="daedalus-dmg-") as temp:
        stage = Path(temp) / "staging"
        stage.mkdir()
        copied = stage / "Daedalus.app"
        # ditto copies the full app including its code signatures and symlinks.
        subprocess.run(["ditto", str(app), str(copied)], check=True)
        check_app(copied)
        os.symlink("/Applications", stage / "Applications")

        # hdiutil does not invoke Finder/AppleScript, so CI does not need
        # Finder Automation permission or a live desktop session.
        subprocess.run(
            ["hdiutil", "create", "-ov", "-volname", "Daedalus",
             "-srcfolder", str(stage), "-format", "UDZO", str(output)],
            check=True,
        )
        subprocess.run(["hdiutil", "verify", str(output)], check=True)
    print(f"Drag-and-drop DMG ready: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=Path("dist/Daedalus.app"))
    parser.add_argument("--output", type=Path,
                        default=Path("dist/Daedalus-macos-preview.dmg"))
    args = parser.parse_args()
    try:
        make_dmg(args.app, args.output)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
