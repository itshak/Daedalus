"""Offline bootstrap CLI. No Gameforge/network access is performed."""

import argparse
import json

from daedalus import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="daedalus",
        description="Daedalus for Ikariam — public project foundation",
    )
    parser.add_argument("--version", action="version", version=f"Daedalus {__version__}")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("doctor", help="Show offline bootstrap diagnostics")
    args = parser.parse_args(argv)

    if args.command == "doctor":
        print(
            json.dumps(
                {
                    "project": "Daedalus",
                    "version": __version__,
                    "stage": "bootstrap",
                    "engine_integrated": False,
                    "server_implemented": False,
                    "desktop_implemented": False,
                    "live_accounts_configured": False,
                },
                sort_keys=True,
            )
        )
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
