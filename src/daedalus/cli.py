"""Daedalus command line: offline inventory, local config and safe API startup."""

from __future__ import annotations

import argparse
import json
import os

from daedalus import __version__
from daedalus.accounts import AccountConfigError, load_accounts
from daedalus.engine_registry import (
    EngineNotFoundError,
    inspect_engine,
    supports_structured_cli,
)


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

    doctor = subcommands.add_parser(
        "doctor", help="Show truthful offline readiness and optional isolated demo smoke"
    )
    doctor.add_argument(
        "--smoke", action="store_true",
        help="Check the real API using an in-process synthetic demo; no game network",
    )
    doctor.add_argument(
        "--deployment-check", action="store_true",
        help="Read-only local ledger/keyring metadata preflight; never authorizes production",
    )
    doctor.add_argument("--task-ledger", help="Private task-ledger path for deployment check")
    doctor.add_argument("--keyring-directory", help="Keyring metadata directory for deployment check")
    doctor.add_argument("--protected-store-directory", help="Encrypted daemon store directory for deployment metadata check")

    engine = subcommands.add_parser("engine", help="Inspect public IkaBot engine source")
    engine.add_argument("action", choices=["inventory"], help="Inspect available engine operations")
    engine.add_argument("--source", help="Source distribution or ikabot package directory")

    accounts = subcommands.add_parser("accounts", help="Inspect local account metadata")
    accounts.add_argument("action", choices=["list"], help="List configured accounts")
    accounts.add_argument("--config", help="TOML metadata configuration (no credentials)")

    sessions = subcommands.add_parser(
        "sessions", help="Manage a private saved-IkaBot account binding; no credentials in TOML"
    )
    sessions.add_argument("action", choices=[
        "bind-email", "forget-email", "probe-saved-cookies",
        "bind-world-cookie", "forget-world-cookie", "assist-browser-login",
        "assist-playwright-login", "stage-world-cookie", "stage-playwright-login",
        "discard-staged-cookie",
    ])
    sessions.add_argument("account_id", help="Configured secret-free account ID")
    sessions.add_argument("--config", help="TOML account metadata path outside repository")
    sessions.add_argument(
        "--confirm-read-only-network", action="store_true",
        help="Required for cookie-only Gameforge GET validation; never requests new login",
    )

    serve = subcommands.add_parser("serve", help="Run the authenticated read-only local API")
    serve.add_argument("--host", default="127.0.0.1", help="Loopback only; use a secure tunnel remotely")
    serve.add_argument("--port", type=_port, default=8765, help="TCP port (default 8765)")
    serve.add_argument("--accounts-file", help="Local TOML metadata configuration")
    serve.add_argument(
        "--connect-existing-ipc", action="store_true",
        help="Read only from an existing authenticated IkaBot IPC worker; never start a login",
    )
    serve.add_argument("--ipc-descriptor", help="Owner-only IkaBot IPC discovery file")
    serve.add_argument(
        "--restore-saved-account", metavar="ACCOUNT_ID",
        help="Explicitly start one verified cookie-only IkaBot worker (no lobby login)",
    )
    serve.add_argument(
        "--confirm-read-only-network", action="store_true",
        help="Required for restore: allow one read-only Gameforge world validation",
    )
    serve.add_argument(
        "--enable-task-control", action="store_true",
        help="Opt in to authorized start/list/stop of existing-session IkaBot tasks",
    )
    serve.add_argument("--task-ledger", help="Private SQLite idempotency ledger outside checkout")
    serve.add_argument(
        "--enable-auto-recovery", action="store_true",
        help="Enable host-only opt-in 5-minute session recovery supervisor; account policies default off",
    )
    serve.add_argument(
        "--monitor-existing-sessions", action="store_true",
        help="Opt in to read-only validation of managed existing engine sessions (no new login)",
    )
    serve.add_argument(
        "--demo", action="store_true",
        help="Run a clearly labeled synthetic read-only desktop demo; no game connection",
    )
    serve.add_argument(
        "--enable-native-browser-login", action="store_true",
        help="Opt in to one-time encrypted Mac browser login with server verification",
    )
    serve.add_argument(
        "--enable-account-editing", action="store_true",
        help="Opt in to protected metadata-only account editing (not task control)",
    )

    args = parser.parse_args(argv)

    if args.command == "doctor":
        from daedalus.readiness import OfflineSmokeError, offline_readiness, synthetic_smoke

        report = offline_readiness()
        if (args.task_ledger or args.keyring_directory or args.protected_store_directory) and not args.deployment_check:
            parser.error("Deployment metadata paths require --deployment-check")
        if args.deployment_check:
            from daedalus.deployment_readiness import deployment_preflight

            report["deployment_preflight"] = deployment_preflight(
                ledger_path=args.task_ledger,
                keyring_directory=args.keyring_directory,
                protected_store_directory=args.protected_store_directory,
            )
        if args.smoke:
            try:
                report["offline_smoke"] = synthetic_smoke()
            except OfflineSmokeError as exc:
                report["offline_smoke"] = {"status": "failed", "reason": str(exc)}
                print(json.dumps(report, sort_keys=True))
                return 1
        print(json.dumps(report, sort_keys=True))
    elif args.command == "engine":
        try:
            capabilities = inspect_engine(args.source)
        except (EngineNotFoundError, OSError, SyntaxError) as exc:
            parser.error(str(exc))
        print(
            json.dumps(
                {
                    "source": "public-ikabot",
                    "structured_cli_available": supports_structured_cli(args.source),
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
    elif args.command == "sessions":
        from daedalus.saved_session_recovery import (
            SavedSessionUnavailable,
            assisted_browser_cookie_login,
            bind_saved_email,
            bind_world_cookie,
            discard_staged_world_cookie,
            probe_saved_cookies,
            stage_world_cookie,
            unbind_saved_email,
            unbind_world_cookie,
        )

        try:
            configured = load_accounts(args.config)
            account = next((row for row in configured if row.id == args.account_id), None)
            if account is None:
                raise SavedSessionUnavailable("Configured account ID not found")
            if args.action == "bind-email":
                import getpass
                import sys

                if not sys.stdin.isatty():
                    parser.error("Protected account binding requires an interactive terminal")
                # Never put this email in CLI args, logs, Git, TOML or API payloads.
                email = getpass.getpass("Existing saved IkaBot login email (hidden): ")
                bind_saved_email(account, email)
                print(json.dumps({"account_id": account.id, "status": "saved_account_bound"}))
            elif args.action == "forget-email":
                unbind_saved_email(account)
                print(json.dumps({"account_id": account.id, "status": "binding_removed"}))
            elif args.action == "forget-world-cookie":
                unbind_world_cookie(account)
                print(json.dumps({"account_id": account.id, "status": "world_cookie_removed"}))
            elif args.action == "bind-world-cookie":
                import getpass
                import sys

                if not args.confirm_read_only_network:
                    parser.error("Import requires --confirm-read-only-network")
                if not sys.stdin.isatty():
                    parser.error("World cookie import requires an interactive terminal")
                from daedalus.account_sessions import AccountSessionCoordinator

                # Only accept the secret through an echo-free local TTY, never
                # as a CLI flag, HTTP argument, logfile or environment variable.
                cookie = getpass.getpass("Existing browser ikariam cookie (hidden): ")
                result = bind_world_cookie(
                    account, AccountSessionCoordinator(configured), cookie,
                    confirmed=True,
                )
                print(json.dumps(result))
            elif args.action == "assist-browser-login":
                import sys

                if not args.confirm_read_only_network:
                    parser.error("Browser assistance requires --confirm-read-only-network")
                if not sys.stdin.isatty():
                    parser.error("Browser assistance requires an interactive local terminal")
                from daedalus.account_sessions import AccountSessionCoordinator

                print(
                    "Complete login and any CAPTCHA yourself in the official browser. "
                    "Then supply only the world ikariam cookie in the hidden prompt. "
                    "No password or lobby token is requested."
                )
                result = assisted_browser_cookie_login(
                    account, AccountSessionCoordinator(configured), confirmed=True,
                )
                print(json.dumps(result))
            elif args.action == "assist-playwright-login":
                import sys

                from daedalus.account_sessions import AccountSessionCoordinator
                from daedalus.browser_recovery import recover_with_human_browser

                if not args.confirm_read_only_network:
                    parser.error("Browser recovery requires --confirm-read-only-network")
                if not sys.stdin.isatty():
                    parser.error("Browser recovery requires an interactive local terminal")

                def operator_confirm() -> bool:
                    print("Complete login and any CAPTCHA in the visible browser yourself.")
                    return input("Type YES after opening the selected game world: ") == "YES"

                result = recover_with_human_browser(
                    account, AccountSessionCoordinator(configured), confirmed=True,
                    human_confirm=operator_confirm,
                )
                print(json.dumps(result))
            elif args.action == "stage-world-cookie":
                import getpass
                import sys

                if not args.confirm_read_only_network:
                    parser.error("Staging requires explicit --confirm-read-only-network consent")
                if not sys.stdin.isatty():
                    parser.error("Cookie staging must happen on the authorized host's terminal")
                cookie = getpass.getpass(
                    "Unverified world ikariam cookie for existing worker (hidden): "
                )
                result = stage_world_cookie(account, cookie, confirmed=True)
                print(json.dumps(result))
            elif args.action == "stage-playwright-login":
                import sys

                from daedalus.browser_recovery import stage_with_human_browser

                if not args.confirm_read_only_network:
                    parser.error("Browser staging requires --confirm-read-only-network")
                if not sys.stdin.isatty():
                    parser.error("Browser staging requires a graphical terminal on the worker host")

                def stage_confirm() -> bool:
                    print(
                        "Complete the official browser login/CAPTCHA on THIS worker host; "
                        "the cookie will be staged UNVERIFIED until the worker confirms it."
                    )
                    return input("Type YES after opening your exact game world: ") == "YES"

                result = stage_with_human_browser(
                    account, confirmed=True, human_confirm=stage_confirm,
                )
                print(json.dumps(result))
            elif args.action == "discard-staged-cookie":
                result = discard_staged_world_cookie(account)
                print(json.dumps(result))
            elif args.action == "probe-saved-cookies":
                if not args.confirm_read_only_network:
                    parser.error("Probe requires --confirm-read-only-network")
                from daedalus.account_sessions import AccountSessionCoordinator

                result = probe_saved_cookies(
                    account, AccountSessionCoordinator(configured), confirmed=True,
                )
                print(json.dumps(result))
        except (AccountConfigError, SavedSessionUnavailable) as exc:
            parser.error(str(exc))
    elif args.command == "serve":
        if args.host not in {"127.0.0.1", "::1"}:
            parser.error("Only loopback binding is supported; use authenticated HTTPS for remote access")
        try:
            from daedalus.account_editor import AccountEditUnavailable
            from daedalus.account_sessions import AccountSessionCoordinator, SessionBusyError
            from daedalus.api import create_app
            from daedalus.saved_worker import SavedCookieWorker, SavedWorkerUnavailable
            from daedalus.task_control import TaskUnavailable

            if args.ipc_descriptor and not args.connect_existing_ipc:
                parser.error("--ipc-descriptor requires --connect-existing-ipc")
            if args.enable_task_control and not args.connect_existing_ipc:
                parser.error("--enable-task-control requires --connect-existing-ipc")
            if args.task_ledger and not args.enable_task_control:
                parser.error("--task-ledger requires --enable-task-control")
            if args.monitor_existing_sessions and not args.enable_task_control:
                parser.error("--monitor-existing-sessions requires --enable-task-control")
            if args.enable_auto_recovery and not (
                args.accounts_file and args.connect_existing_ipc and
                args.enable_task_control and args.monitor_existing_sessions
            ):
                parser.error("Automatic recovery needs fixed accounts, monitored task control and IPC")
            if args.enable_account_editing and args.enable_task_control:
                parser.error("--enable-account-editing is incompatible with --enable-task-control")
            if args.restore_saved_account and (
                not args.accounts_file or not args.connect_existing_ipc
                or not args.confirm_read_only_network
            ):
                parser.error(
                    "Cookie-only worker requires --accounts-file, --connect-existing-ipc "
                    "and --confirm-read-only-network"
                )
            if args.enable_native_browser_login and (
                not args.accounts_file or args.demo or args.enable_account_editing
            ):
                parser.error("Native Mac browser login needs fixed accounts, not demo/editor")
            if args.restore_saved_account and (
                args.ipc_descriptor or args.enable_account_editing or args.demo
            ):
                parser.error(
                    "Cookie-only worker cannot use external IPC, metadata editing or demo mode"
                )
            if args.demo and (
                args.accounts_file or args.connect_existing_ipc or args.ipc_descriptor
                or args.enable_task_control or args.task_ledger or args.enable_account_editing
                or args.monitor_existing_sessions or args.restore_saved_account
                or args.enable_native_browser_login or args.enable_auto_recovery
            ):
                parser.error("--demo cannot access real accounts, IPC, task controls or editing")
            ipc = None
            task_controller = None
            owner = None
            broker = None
            monitor = None
            worker = None
            if args.connect_existing_ipc:
                from daedalus.engine_ipc import ControlledIPCClient, ExistingIPCClient

                ipc = (
                    ControlledIPCClient(args.ipc_descriptor)
                    if args.enable_task_control
                    else ExistingIPCClient(args.ipc_descriptor)
                )
                if args.enable_auto_recovery:
                    from daedalus.recovery_runtime import RoutedAccountIPC
                    ipc = RoutedAccountIPC(ipc)
            if (args.enable_task_control or args.restore_saved_account
                    or args.enable_native_browser_login):
                configured = load_accounts(args.accounts_file)
                owner = AccountSessionCoordinator(configured)
            recovery_credentials = None
            recovery_supervisor = None
            if args.enable_task_control:
                from daedalus.recovery_credentials import RecoveryCredentials
                from daedalus.recovery_state import RecoveryStore

                recovery_credentials = RecoveryCredentials()
                from daedalus.task_control import TaskController

                recovery_store = RecoveryStore()
                # Dedicated IkaBot children inherit the exact same private
                # SQLite checkpoint, without a user-writable task-config path.
                os.environ["DAEDALUS_FIXED_TRANSFER_DB"] = str(recovery_store.path)
                task_controller = TaskController(
                    configured, owner, ipc, ledger_path=args.task_ledger,
                    active_validation=args.monitor_existing_sessions,
                    recovery_store=recovery_store,
                )
                if args.monitor_existing_sessions:
                    from daedalus.auth_assistance import AssistanceBroker
                    from daedalus.session_monitor import ExistingSessionRecoveryMonitor

                    broker = AssistanceBroker(owner)
                    monitor = ExistingSessionRecoveryMonitor(task_controller, broker)
            if args.restore_saved_account:
                account = next(
                    (row for row in configured if row.id == args.restore_saved_account), None
                )
                if account is None:
                    parser.error("The requested saved worker account was not configured")
                worker = SavedCookieWorker(account, owner)
                worker.start(confirmed=True)
                if task_controller is not None:
                    task_controller.adopt_verified_saved_worker(account.id, worker.lease)
                if monitor is not None:
                    # NativeBrowserHandoff validates monitor ownership at
                    # construction, so attach before creating the handoff.
                    monitor.attach_dedicated_worker(worker)
            native_handoff = None
            if args.enable_native_browser_login:
                from daedalus.native_browser_handoff import NativeBrowserHandoff

                native_handoff = NativeBrowserHandoff(
                    configured, owner, monitor=monitor if worker is not None else None,
                    dedicated_worker=worker,
                )
            if args.enable_auto_recovery:
                from daedalus.recovery_runtime import RecoverySupervisor, RecoveryWorkers

                workers = RecoveryWorkers(
                    owner, task_controller, ipc, recovery_credentials, broker,
                )
                recovery_supervisor = RecoverySupervisor(
                    configured, recovery_store, workers, task_controller,
                    recovery_credentials,
                )
            app = create_app(
                accounts_path=args.accounts_file, ipc_client=ipc,
                session_coordinator=owner, task_controller=task_controller,
                enable_account_editing=args.enable_account_editing,
                assistance_broker=broker, recovery_monitor=monitor,
                saved_worker=worker, native_browser_handoff=native_handoff,
                recovery_store=recovery_store if args.enable_task_control else None,
                recovery_credentials=recovery_credentials,
                recovery_supervisor=recovery_supervisor,
                demo_mode=args.demo,
            )
        except (
            AccountConfigError, AccountEditUnavailable, SessionBusyError,
            SavedWorkerUnavailable, TaskUnavailable, ValueError, ImportError,
        ) as exc:
            if worker is not None:
                worker.close()
            if task_controller is not None:
                task_controller.close()
            parser.error(str(exc))
        try:
            try:
                import uvicorn
            except ImportError:
                parser.error("Install daedalus[server] to run the API")
            uvicorn.run(app, host=args.host, port=args.port, access_log=False)
        finally:
            # Stop the engine-owned IPC before releasing the shared identity
            # lease. Otherwise a competing owner could start during shutdown.
            if worker is not None:
                worker.close()
            if task_controller is not None:
                task_controller.close()
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
