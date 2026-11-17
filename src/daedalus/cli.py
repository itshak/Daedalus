"""Daedalus command line: offline inventory, local config and safe API startup."""

from __future__ import annotations

import argparse
import json

from daedalus import __version__
from daedalus.accounts import AccountConfigError, load_accounts
from daedalus.engine_registry import EngineNotFoundError, inspect_engine


def _port(text: str) -> int:
    try:
        port = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535")
    return port


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="daedalus", description="Daedalus for Ikariam")
    parser.add_argument("--version", action="version", version=f"Daedalus {__version__}")
    subcommands = parser.add_subparsers(dest="command")

    subcommands.add_parser("doctor", help="Show offline integration diagnostics")

    engine = subcommands.add_parser("engine", help="Inspect public IkaBot engine source")
    engine.add_argument("action", choices=["inventory"], help="Inspect available engine operations")
    engine.add_argument("--source", help="Source distribution or ikabot package directory")

    accounts = subcommands.add_parser("accounts", help="Inspect local account metadata")
    accounts.add_argument("action", choices=["list"], help="List configured accounts")
    accounts.add_argument("--config", help="TOML metadata configuration (no credentials)")

    serve = subcommands.add_parser("serve", help="Run the authenticated read-only local API")
    serve.add_argument("--host", default="127.0.0.1", help="Loopback only; use a secure tunnel remotely")
    serve.add_argument("--port", type=_port, default=8765, help="TCP port (default 8765)")
    serve.add_argument("--accounts-file", help="Local TOML metadata configuration")

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
                    "stage": "read-only-controller",
                    "engine_source_available": available,
                    "engine_capabilities_found": count,
                    "engine_integrated": False,
                    "server_implemented": True,
                    "server_mode": "read_only",
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
    elif args.command == "accounts":
        try:
            configured = load_accounts(args.config)
        except AccountConfigError as exc:
            parser.error(str(exc))
        print(json.dumps({"accounts": [account.to_dict() for account in configured]}, ensure_ascii=False))
    elif args.command == "serve":
        if args.host not in {"127.0.0.1", "::1"}:
            parser.error("Only loopback binding is supported; use SSH/Tailscale tunnel for remote use")
        try:
            from daedalus.api import create_app

            app = create_app(accounts_path=args.accounts_file)
        except (AccountConfigError, ValueError, ImportError) as exc:
            parser.error(str(exc))
        try:
            import uvicorn
        except ImportError:
            parser.error("Install daedalus[server] to run the API")
        uvicorn.run(app, host=args.host, port=args.port, access_log=False)
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
