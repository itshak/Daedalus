#!/usr/bin/env python3
"""Create a self-contained Daedalus.app from the current checked-out source.

This is an *artifact builder*, not an installer. It does not read users'
accounts.toml, browser cookies, cached sessions, or production secrets, and
never writes to /Applications or ~/.ikabot.

Usage:
    python packaging/build_macos_app.py --output-dir dist
    python packaging/build_macos_app.py --dry-run --output-dir /tmp/daedalus-preview
"""

from __future__ import annotations

import argparse
import importlib.util
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Daedalus"
BUNDLE_IDENTIFIER = "io.github.itshak.daedalus"


def build_command(
    launcher: Path, *, output_dir: Path, work_dir: Path, spec_dir: Path
) -> list[str]:
    """Generate a deterministic PyInstaller argument vector, no shell involved."""
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--osx-bundle-identifier",
        BUNDLE_IDENTIFIER,
        "--distpath",
        str(output_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        "--collect-all",
        "qfluentwidgets",
        "--collect-all",
        "keyring",
        "--collect-submodules",
        "qframelesswindow",
        "--hidden-import",
        "daedalus.desktop.app",
        "--hidden-import",
        "daedalus.desktop.task_page",
        "--hidden-import",
        "daedalus.desktop.pages",
        "--hidden-import",
        "daedalus.desktop.log_page",
        "--hidden-import",
        "daedalus.desktop.theme",
        str(launcher),
    ]


def launcher_source() -> str:
    """The package entrypoint is all that is needed in the frozen GUI."""
    return (
        "from __future__ import annotations\n"
        "import multiprocessing\n"
        "import sys\n"
        "if __name__ == '__main__':\n"
        "    multiprocessing.freeze_support()\n"
        "    from daedalus.desktop import main\n"
        "    sys.exit(main())\n"
    )


def build(
    *,
    output_dir: Path,
    dry_run: bool = False,
    adhoc_sign: bool = False,
) -> Path:
    """Build one .app without installing it, and optionally ad-hoc sign on macOS."""
    output_dir = output_dir.resolve()
    bundle = output_dir / f"{APP_NAME}.app"

    # Dry-run is portable, to let Linux/Windows CI test command generation.
    if not dry_run and sys.platform != "darwin":
        raise RuntimeError("macOS .app builds require macOS; use --dry-run on other platforms")
    if not dry_run and importlib.util.find_spec("PyInstaller") is None:
        raise RuntimeError('Install packaging dependencies with pip install "daedalus[macos-build]"')
    if not dry_run and importlib.util.find_spec("qfluentwidgets") is None:
        raise RuntimeError('Install GUI dependencies with pip install "daedalus[desktop]"')

    with tempfile.TemporaryDirectory(prefix="daedalus-packaging-") as temporary:
        workspace = Path(temporary)
        launcher = workspace / "launcher.py"
        launcher.write_text(launcher_source(), encoding="utf-8")
        command = build_command(
            launcher,
            output_dir=output_dir,
            work_dir=workspace / "build",
            spec_dir=workspace / "spec",
        )
        if dry_run:
            print("Dry-run build: " + " ".join(command))
            return bundle
        output_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(command, check=True, cwd=ROOT)
        if not bundle.is_dir() or not (bundle / "Contents" / "MacOS" / APP_NAME).is_file():
            raise RuntimeError("PyInstaller did not produce a complete Daedalus.app")

        if adhoc_sign:
            subprocess.run(
                ["codesign", "--force", "--deep", "--sign", "-", str(bundle)],
                check=True,
            )
    print(f"Bundle created: {bundle}")
    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "dist",
        help="Output directory (never /Applications by default)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate command without building")
    parser.add_argument(
        "--adhoc-sign",
        action="store_true",
        help="Ad-hoc code-sign for local testing, not for notarized distribution",
    )
    args = parser.parse_args(argv)

    if args.adhoc_sign and args.dry_run:
        parser.error("--adhoc-sign and --dry-run cannot be combined")
    if args.adhoc_sign and platform.system() != "Darwin":
        parser.error("--adhoc-sign requires macOS")
    try:
        build(output_dir=args.output_dir, dry_run=args.dry_run, adhoc_sign=args.adhoc_sign)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
