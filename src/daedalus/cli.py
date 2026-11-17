"""Daedalus foundation CLI: offline diagnostics and upstream task inventory."""

import argparse
import json

from daedalus import __version__
from daedalus.engine_registry import EngineNotFoundError, inspect_engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="daedalus",
        description="Daedalus for Ikariam — early engine integration tools",
    )
    parser.add_argument("--version", action="version", version=f"Daedalus {__version__}")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("doctor", help="Show offline integration diagnostics")
    engine = subcommands.add_parser("engine", help="Inspect public IkaBot engine source")
    engine.add_argument("action", choices=["inventory"], help="Inspect available engine operations")
    engine.add_argument("--source", help="Source distribution or ikabot package directory")
    args = parser.parse_args(argv)

    if args.command == "doctor":
        try:
            count = len(inspect_engine())
            available = True
        except (EngineNotFoundError, OSError, SyntaxError):
            count = 0
            available = False
        print(
            json.dumps(
                {
                    "project": "Daedalus",
                    "version": __version__,
                    "stage": "engine-import",
                    "engine_source_available": available,
                    "engine_capabilities_found": count,
                    "engine_integrated": False,
                    "server_implemented": False,
                    "desktop_implemented": False,
                    "live_accounts_configured": False,
                },
                sort_keys=True,
            )
        )
    elif args.command == "engine":
        try:
            capabilities = inspect_engine(args.source)
        except (EngineNotFoundError, OSError, SyntaxError) as exc:
            parser.error(str(exc))
        print(
            json.dumps(
                {
                    "source": "public-ikabot",
                    "structured_cli_available": False,
                    "capabilities": [item.to_dict() for item in capabilities],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
