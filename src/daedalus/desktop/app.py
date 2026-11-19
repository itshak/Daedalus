"""Native Fluent control center. Adapted from the user's original Mac main window.

The read-only views remain safe by default. An explicitly enabled backend can
accept user-confirmed task start/stop actions through existing-session IPC.
No Selenium login or new game worker is started from this desktop shell.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QMessageBox, QPlainTextEdit, QSizePolicy, QSpacerItem
from qfluentwidgets import (
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    NavigationItemPosition,
    Theme,
    setTheme,
)

from daedalus.accounts import Account
from daedalus.client import APIConnectionError, DaedalusClient
from daedalus.connection_prefs import (
    PreferenceError,
    forget_connection,
    remember_connection,
    saved_connection,
)
from daedalus.desktop.appearance_page import AppearancePage
from daedalus.desktop.branding import application_icon
from daedalus.desktop.design_system import NAV_ICONS
from daedalus.desktop.home_page import HomePage
from daedalus.desktop.log_page import LogPage
from daedalus.desktop.pages import AccountsPage, ConnectionPage, WarehousesPage
from daedalus.desktop.selenium_auth import GameforgeCredentials
from daedalus.desktop.selenium_credentials import (
    LoginCredentialError,
    get_saved_login,
    legacy_warehouse_login,
    remember_login,
)
from daedalus.desktop.selenium_credentials_dialog import SeleniumCredentialsDialog
from daedalus.desktop.selenium_vault import seal_login, unseal_login
from daedalus.desktop.selenium_worker import SeleniumLoginWorker
from daedalus.desktop.ssh_tunnel import (
    LocalSSHTunnel,
    SSHConnectionUnavailable,
    forget_ssh_destination,
    load_ssh_destination,
    save_ssh_destination,
    validate_ssh_destination,
)
from daedalus.desktop.task_page import TasksPage
from daedalus.gui_preferences import (
    GuiPreferenceError,
    GuiPreferences,
    load_gui_preferences,
    save_gui_preferences,
)
from daedalus.native_browser_handoff import (
    NativeHandoffUnavailable,
    encrypt_mac_world_session,
)

logger = logging.getLogger("daedalus.desktop")


def _known_ikabot_workers(client: object) -> list[str] | None:
    """Unknown must not be confused with the absence of an IkaBot worker."""
    try:
        if not callable(getattr(client, "connected_accounts", None)):
            return None
        ids = client.connected_accounts()
        return ids if isinstance(ids, list) else None
    except (APIConnectionError, ValueError):
        return None


class QtLogBridge(QObject):
    """Keep the legacy GUI's queued-signal logging to avoid cross-thread Qt crashes."""

    message = Signal(str)
    activity = Signal(str, str)

    def __init__(self, widget: QPlainTextEdit, parent=None) -> None:
        super().__init__(parent)
        self._widget = widget
        self.message.connect(self._append)

    def _append(self, value: str) -> None:
        try:
            self._widget.appendPlainText(value)
        except RuntimeError:
            pass  # window already destroyed


class QtLogHandler(logging.Handler):
    def __init__(self, widget: QPlainTextEdit, activity_page: LogPage | None = None) -> None:
        super().__init__()
        self.bridge = QtLogBridge(widget)
        if activity_page is not None:
            self.bridge.activity.connect(activity_page.add_event)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.bridge.message.emit(self.format(record))
            # The timeline uses a strict allowlist of generic messages and
            # never displays raw backend exception bodies or account IDs.
            if record.name == "daedalus.desktop":
                self.bridge.activity.emit(record.levelname, record.getMessage())
        except RuntimeError:
            pass


class APIWorker(QThread):
    """Perform HTTP calls off the main Qt thread; pass only nonsecret results."""

    completed = Signal(str, object)
    failed = Signal(str, str)

    def __init__(
        self,
        client: DaedalusClient,
        action: str,
        *,
        account_id: str | None = None,
        task_payload: dict[str, object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.client = client
        self.action = action
        self.account_id = account_id
        self.task_payload = task_payload

    def run(self) -> None:
        try:
            if self.action == "connect":
                result = {
                    "health": self.client.health(),
                    "accounts": self.client.accounts(),
                    "capabilities": self.client.capabilities(),
                    "account_config": self.client.account_config(),
                    "native_browser_login": (
                        self.client.native_browser_login_capabilities()
                        if callable(getattr(self.client, "native_browser_login_capabilities", None))
                        else {"enabled": False}
                    ),
                    "login_vaults": (
                        self.client.login_vaults()
                        if callable(getattr(self.client, "login_vaults", None)) else {}
                    ),
                    "connected_accounts": _known_ikabot_workers(self.client),
                }
            elif self.action == "accounts":
                result = self.client.accounts()
            elif self.action == "login_vault_sync" and self.task_payload:
                from daedalus.desktop.selenium_vault import seal_login

                rows = self.task_payload.get("accounts")
                origin = self.task_payload.get("origin")
                if not isinstance(rows, list) or not isinstance(origin, str):
                    raise ValueError("Invalid encrypted login backup selection")
                saved, missing, failed = 0, 0, 0
                for row in rows:
                    if not isinstance(row, dict) or row.get("enabled") is not True:
                        continue
                    aid, world = row.get("id"), row.get("world")
                    if not isinstance(aid, str) or not isinstance(world, str):
                        failed += 1
                        continue
                    try:
                        credentials = get_saved_login(origin, aid, world)
                        if credentials is None:
                            credentials = legacy_warehouse_login(row)
                        if credentials is None:
                            missing += 1
                            continue
                        sealed = seal_login(origin, aid, world, credentials)
                        if self.client.store_login_vault(aid, sealed):
                            saved += 1
                        else:
                            failed += 1
                    except (LoginCredentialError, APIConnectionError, ValueError):
                        failed += 1
                result = {"saved": saved, "missing": missing, "failed": failed}
            elif self.action == "account_config":
                result = self.client.account_config()
            elif self.action == "account_config_put" and self.task_payload:
                result = self.client.replace_account_config(
                    str(self.task_payload["revision"]),
                    self.task_payload["accounts"],
                    confirmed=True,
                )
            elif self.action == "monitor_attach" and self.account_id:
                result = self.client.monitor_existing_account(self.account_id, confirmed=True)
            elif self.action == "assistance_pending":
                result = self.client.pending_assistance()
            elif self.action == "auth_assistance" and self.account_id:
                result = self.client.auth_assistance(self.account_id)
            elif self.action == "native_login_start" and self.account_id:
                result = self.client.start_native_browser_login(
                    self.account_id, confirmed=True,
                )
            elif (self.action == "native_login_complete" and self.account_id
                  and self.task_payload):
                result = self.client.finish_native_browser_login(
                    self.account_id, str(self.task_payload["ticket_id"]),
                    self.task_payload["envelope"],
                )
                sealed = self.task_payload.get("vault")
                if (isinstance(sealed, dict)
                        and callable(getattr(self.client, "store_login_vault", None))):
                    try:
                        result["vault_saved"] = self.client.store_login_vault(
                            self.account_id, sealed,
                        )
                    except (APIConnectionError, ValueError):
                        # The verified session stays valid if backup fails.
                        result["vault_saved"] = False
            elif (self.action == "native_login_cancel" and self.account_id
                  and self.task_payload):
                result = self.client.cancel_native_browser_login(
                    self.account_id, str(self.task_payload["ticket_id"]),
                )
            elif self.action == "recovery_guide" and self.account_id:
                result = self.client.recovery_guide(self.account_id)
            elif self.action == "recovery_prepare" and self.account_id:
                result = self.client.prepare_dedicated_recovery(
                    self.account_id, confirmed=True,
                )
            elif (
                self.action == "worker_rebind"
                and self.account_id and self.task_payload
            ):
                result = self.client.rebind_dedicated_worker(
                    self.account_id, str(self.task_payload["ticket_id"]),
                    confirmed=True,
                )
            elif (
                self.action == "auth_assistance_approve"
                and self.account_id and self.task_payload
            ):
                result = self.client.approve_auth_assistance(
                    self.account_id, str(self.task_payload["ticket_id"]), confirmed=True,
                )
            elif self.action == "connected_accounts":
                result = self.client.connected_accounts()
            elif self.action == "capabilities":
                result = self.client.capabilities()
            elif self.action == "warehouses" and self.account_id:
                result = {
                    "account_id": self.account_id,
                    "cities": self.client.warehouses(self.account_id),
                }
            elif self.action in {"warehouses_batch", "warehouses_all"} and self.task_payload is not None:
                ids = self.task_payload.get("account_ids")
                limit = 32 if self.action == "warehouses_batch" else None
                if (
                    not isinstance(ids, list) or not ids
                    or (limit is not None and len(ids) > limit)
                    or any(not isinstance(aid, str) for aid in ids)
                    or len(set(ids)) != len(ids)
                ):
                    raise ValueError("Select nonempty, distinct report accounts"
                                     + (" (up to 32)" if limit is not None else ""))
                result = []
                for aid in ids:
                    try:
                        result.append({
                            "account_id": aid,
                            "cities": self.client.warehouses(aid),
                        })
                    except APIConnectionError:
                        # Never forward game backend bodies/credentials to a report.
                        result.append({"account_id": aid, "error": True})
            elif (
                self.action == "task_preflight" and self.account_id
                and self.task_payload and isinstance(self.task_payload.get("task"), str)
            ):
                result = self.client.task_preflight(
                    self.account_id, str(self.task_payload["task"])
                )
            elif self.action == "task_list" and self.account_id:
                result = self.client.tasks(self.account_id)
            elif self.action == "task_list_batch" and self.task_payload is not None:
                ids = self.task_payload.get("account_ids")
                if (
                    not isinstance(ids, list) or not ids
                    or any(not isinstance(aid, str) for aid in ids)
                    or len(set(ids)) != len(ids)
                ):
                    raise ValueError("Choose at least one distinct account")
                result = []
                for aid in ids:
                    try:
                        data = self.client.tasks(aid)
                        # The backend binds every task ledger to its account;
                        # never display another account's result under this name.
                        if data.get("account_id") not in {None, aid}:
                            raise ValueError("Task status account mismatch")
                        result.append({"account_id": aid,
                                       "engine_tasks": data.get("engine_tasks", []),
                                       "requests": data.get("requests", [])})
                    except (ValueError, APIConnectionError):
                        result.append({"account_id": aid, "error": True})
            elif self.action == "task_start_batch" and self.task_payload is not None:
                import uuid

                ids = self.task_payload.get("account_ids")
                task = self.task_payload.get("task")
                config = self.task_payload.get("config")
                if (
                    not isinstance(ids, list) or not 1 <= len(ids) <= 32
                    or any(not isinstance(aid, str) for aid in ids)
                    or len(set(ids)) != len(ids)
                    or not isinstance(task, str) or not isinstance(config, dict)
                ):
                    raise ValueError("Select up to 32 distinct authorized task accounts")
                # All preflights must succeed BEFORE the first game mutation.
                blocked = []
                for aid in ids:
                    try:
                        readiness = self.client.task_preflight(aid, task)
                        if (readiness.get("ready") is not True
                                or readiness.get("unresolved_request") is True):
                            blocked.append({
                                "account_id": aid,
                                "reason": str(readiness.get("reason") or "unavailable"),
                            })
                    except (ValueError, APIConnectionError):
                        blocked.append({"account_id": aid, "reason": "unavailable"})
                submitted = []
                halted = None
                if not blocked:
                    for aid in ids:
                        rid = str(uuid.uuid4())
                        try:
                            receipt = self.client.start_task(
                                aid, task, config, rid, confirmed=True,
                            )
                            # An HTTP 200 can still carry a durable
                            # "unconfirmed" or "dispatching" receipt.
                            # Treat everything except a verified started
                            # receipt as uncertain; never launch the next
                            # account or silently label it successful.
                            if (not isinstance(receipt, dict)
                                    or receipt.get("status") not in {"started", "running"}
                                    or receipt.get("account_id") not in {None, aid}):
                                halted = {"account_id": aid, "request_id": rid,
                                          "status": "unconfirmed"}
                                break
                            submitted.append({
                                "account_id": aid, "request_id": rid,
                                "status": str(receipt["status"]),
                            })
                        except (ValueError, APIConnectionError):
                            # Transport uncertainty MAY mean execution occurred.
                            # Stop subsequent launches, do not retry or reissue.
                            halted = {"account_id": aid, "request_id": rid,
                                      "status": "unconfirmed"}
                            break
                result = {"submitted": submitted, "blocked": blocked,
                          "halted": halted, "account_ids": ids}
            elif self.action == "task_start" and self.account_id and self.task_payload:
                payload = self.task_payload
                result = self.client.start_task(
                    self.account_id,
                    str(payload["task"]),
                    payload["config"],
                    str(payload["request_id"]),
                    confirmed=True,
                )
            elif self.action == "task_stop" and self.account_id and self.task_payload:
                result = self.client.stop_task(self.account_id, str(self.task_payload["task_id"]))
                result["account_id"] = self.account_id
            elif self.action == "task_reconcile" and self.account_id and self.task_payload:
                result = self.client.acknowledge_task(
                    self.account_id,
                    str(self.task_payload["request_id"]),
                    confirmed=True,
                )
            else:
                raise ValueError("Unsupported desktop API request")
            self.completed.emit(self.action, result)
        except (APIConnectionError, ValueError) as exc:
            self.failed.emit(self.action, str(exc))
        except Exception:  # noqa: BLE001 - catch worker faults without exposing private details
            # Never surface arbitrary transport or game-session exceptions to the UI.
            self.failed.emit(self.action, "Unexpected backend request error")


class SecureSSHConnectionWorker(QThread):
    """Open and verify SSH forwarding off the UI thread, without secret logs."""

    completed = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, destination: str, token: str, parent=None) -> None:
        super().__init__(parent)
        self.destination = destination
        self.token = token

    def run(self) -> None:
        tunnel = None
        client = None
        try:
            tunnel = LocalSSHTunnel(self.destination)
            address = tunnel.start()
            client = DaedalusClient(address, self.token)
            result = {
                "health": client.health(),
                "accounts": client.accounts(),
                "capabilities": client.capabilities(),
                "account_config": client.account_config(),
                "native_browser_login": (
                    client.native_browser_login_capabilities()
                    if callable(getattr(client, "native_browser_login_capabilities", None))
                    else {"enabled": False}
                ),
                "login_vaults": (
                    client.login_vaults()
                    if callable(getattr(client, "login_vaults", None)) else {}
                ),
                "connected_accounts": _known_ikabot_workers(client),
            }
            self.completed.emit("ssh_connect", {
                "result": result, "client": client, "tunnel": tunnel,
            })
        except (ValueError, APIConnectionError, SSHConnectionUnavailable) as exc:
            if client is not None:
                client.close()
            if tunnel is not None:
                tunnel.close()
            self.failed.emit("ssh_connect", str(exc))
        except Exception:  # noqa: BLE001 - sanitizes unforeseen SSH worker failures
            if client is not None:
                client.close()
            if tunnel is not None:
                tunnel.close()
            self.failed.emit("ssh_connect", "Could not establish a trusted SSH backend connection")


class MainWindow(FluentWindow):
    """Familiar Fluent navigation with all data fetched from Daedalus backend."""

    def __init__(self) -> None:
        super().__init__()
        self.client: DaedalusClient | None = None
        self._pending_client: DaedalusClient | None = None
        self._ssh_tunnel: LocalSSHTunnel | None = None
        self._pending_ssh_tunnel: LocalSSHTunnel | None = None
        self._pending_ssh_destination: str | None = None
        self._pending_ssh_token: str | None = None
        self._active_ssh_destination: str | None = None
        self._active_ssh_token: str | None = None
        self._pending_secret_saved = False
        self._pending_preferences: tuple[str, str] | None = None
        self._worker: APIWorker | None = None
        # Follow-up API reads run only after QThread.finished. A zero-delay
        # timer fired from completed may race with finished and be discarded.
        self._preflight_queue: list[tuple[str, str, int]] = []
        self._pending_task_refresh: str | None = None
        self._pending_batch_status: list[str] | None = None
        self._pending_native_login_challenge: dict[str, object] | None = None
        self._selenium_worker: SeleniumLoginWorker | None = None
        self._automatic_login_active = False
        self._automatic_login_cancelled = False
        self._automatic_login_queue: list[str] = []
        self._automatic_login_current: str | None = None
        self._automatic_login_credentials: GameforgeCredentials | None = None
        self._automatic_login_save_credentials = False
        self._automatic_login_challenge: dict[str, object] | None = None
        self._automatic_login_pending_advance = False
        self._automatic_login_successes = 0
        self._automatic_login_failures = 0
        self._automatic_login_report: tuple[str, list[str]] | None = None
        self._recovery_followup: tuple[str, str] | None = None
        self._embedded_demo = None
        self._seen_assistance_ids: set[str] = set()
        self._active_backend_url: str | None = None
        self._server_login_vaults: dict[str, dict[str, object]] = {}
        self._syncing_report_preferences = False
        try:
            self._gui_preferences = load_gui_preferences()
        except GuiPreferenceError:
            self._gui_preferences = GuiPreferences()
            logger.warning("Unsafe or invalid local GUI settings; using safe defaults")
        self._assistance_poll = QTimer(self)
        self._assistance_poll.setInterval(30_000)
        self._assistance_poll.timeout.connect(self._poll_pending_assistance)

        self.home_page = HomePage(self)
        self.accounts_page = AccountsPage(self)
        self.warehouses_page = WarehousesPage(self)
        # One authoritative automation workspace and one catalog instance.
        # Preserve the public operations_page alias for legacy navigation
        # callers without constructing a disconnected second catalog.
        self.tasks_page = TasksPage(self)
        self.operations_page = self.tasks_page.catalog_panel
        self._task_views = (self.tasks_page,)
        self.log_page = LogPage(self)
        self.connection_page = ConnectionPage(self)
        self.appearance_page = AppearancePage(self)
        self.appearance_page.set_preferences(self._gui_preferences)
        self.warehouses_page.set_display_preferences(
            only_220k=self._gui_preferences.only_220k,
            group_by_island=self._gui_preferences.group_by_island,
        )

        # Five daily destinations. Wine, Construction and the read-only
        # operation catalog live inside Automations rather than duplicating
        # entire navigable task editors.
        self.addSubInterface(self.home_page, NAV_ICONS["overview"], "Overview")
        self.addSubInterface(self.accounts_page, NAV_ICONS["accounts"], "Accounts")
        self.addSubInterface(self.warehouses_page, NAV_ICONS["warehouses"], "Warehouses")
        self.addSubInterface(self.tasks_page, NAV_ICONS["automations"], "Automations")
        self.addSubInterface(self.log_page, NAV_ICONS["activity"], "Activity")
        self.addSubInterface(
            self.connection_page, NAV_ICONS["connection"], "Connection",
            NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(
            self.appearance_page, NAV_ICONS["settings"], "Settings",
            NavigationItemPosition.BOTTOM,
        )

        self.navigationInterface.setReturnButtonVisible(False)
        header = self.navigationInterface.panel.topLayout
        header.insertSpacerItem(0, QSpacerItem(40, 36, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.connection_page.ssh_connect_requested.connect(self._connect_ssh)
        self.connection_page.connect_requested.connect(self._connect)
        self.connection_page.demo_requested.connect(self._start_offline_demo)
        self.connection_page.overview_requested.connect(
            lambda: self.switchTo(self.home_page)
        )
        self.connection_page.reconnect_requested.connect(self._reconnect)
        self.connection_page.forget_requested.connect(self._forget_connection)
        self.appearance_page.preferences_changed.connect(self._on_appearance_changed)
        self.appearance_page.connection_settings_requested.connect(
            lambda: self.switchTo(self.connection_page)
        )
        self.appearance_page.report_accounts_requested.connect(
            self.warehouses_page._choose_accounts
        )
        self.appearance_page.report_all_requested.connect(
            self._include_all_report_accounts
        )
        self.accounts_page.report_selection_changed.connect(self._on_report_selection_changed)
        self.accounts_page.refresh_requested.connect(lambda: self._request("accounts"))
        self.accounts_page.account_change_requested.connect(
            lambda revision, rows: self._request(
                "account_config_put", task_payload={"revision": revision, "accounts": rows},
            )
        )
        self.accounts_page.monitor_requested.connect(
            lambda account_id: self._request("monitor_attach", account_id=account_id)
        )
        self.accounts_page.assistance_check_requested.connect(
            lambda account_id: self._request("auth_assistance", account_id=account_id)
        )
        self.accounts_page.recovery_guide_requested.connect(
            lambda account_id: self._request("recovery_guide", account_id=account_id)
        )
        self.accounts_page.native_browser_login_requested.connect(self._begin_native_browser_login)
        self.accounts_page.automatic_login_requested.connect(self._begin_automatic_logins)
        self.accounts_page.automatic_login_cancel_requested.connect(self._cancel_automatic_logins)
        self.accounts_page.sync_saved_logins_requested.connect(
            lambda rows: self._request(
                "login_vault_sync",
                task_payload={"origin": self._active_backend_url, "accounts": rows},
            )
        )
        self.accounts_page.recovery_prepare_requested.connect(
            lambda account_id: self._request(
                "recovery_prepare", account_id=account_id,
            )
        )
        self.accounts_page.rebind_requested.connect(
            lambda account_id, ticket_id: self._request(
                "worker_rebind", account_id=account_id,
                task_payload={"ticket_id": ticket_id},
            )
        )
        self.accounts_page.assistance_approve_requested.connect(
            lambda account_id, ticket_id: self._request(
                "auth_assistance_approve", account_id=account_id,
                task_payload={"ticket_id": ticket_id},
            )
        )
        self.accounts_page.check_engine_requested.connect(
            lambda: self._request("connected_accounts")
        )
        self.home_page.connect_backend.connect(lambda: self.switchTo(self.connection_page))
        self.home_page.manage_accounts.connect(lambda: self.switchTo(self.accounts_page))
        self.home_page.account_selected.connect(self._select_working_account)
        self.home_page.view_warehouses.connect(self._view_home_warehouses)
        self.home_page.view_all_warehouses.connect(self._view_all_warehouses)
        self.home_page.view_all_automations.connect(self._view_all_automations)
        self.home_page.manage_automations.connect(self._view_home_automations)
        # The embedded catalog directly selects its task in TasksPage.
        # Its read-only refresh remains independently routed to the backend.
        self.operations_page.refresh_requested.connect(
            lambda: self._request("capabilities")
        )
        self.warehouses_page.load_requested.connect(
            lambda aid: self._request_warehouse_scope("warehouses", [aid])
        )
        self.warehouses_page.load_selected_requested.connect(
            lambda ids: self._request_warehouse_scope("warehouses_batch", ids)
        )
        self.warehouses_page.load_all_requested.connect(
            lambda ids: self._request_warehouse_scope("warehouses_all", ids)
        )
        self.warehouses_page.report_scope_changed.connect(
            lambda ids: self.accounts_page.set_report_exclusions(
                set(self.warehouses_page._account_ids).difference(ids)
            )
        )
        for view in self._task_views:
            view.refresh_requested.connect(
                lambda account_id: self._request("task_list", account_id=account_id)
            )
            view.preflight_requested.connect(self._queue_task_preflight)
            view.launch_requested.connect(
                lambda aid, name, config, rid: self._request(
                    "task_start", account_id=aid,
                    task_payload={"task": name, "config": config, "request_id": rid},
                )
            )
            view.stop_requested.connect(
                lambda aid, task_id: self._request(
                    "task_stop", account_id=aid, task_payload={"task_id": task_id},
                )
            )
            view.reconcile_requested.connect(
                lambda aid, rid: self._request(
                    "task_reconcile", account_id=aid, task_payload={"request_id": rid},
                )
            )
            view.batch_status_requested.connect(
                lambda ids: self._request(
                    "task_list_batch", task_payload={"account_ids": ids},
                )
            )
            view.batch_launch_requested.connect(
                lambda ids, task, config: self._request(
                    "task_start_batch",
                    task_payload={"account_ids": ids, "task": task, "config": config},
                )
            )

        self._log_handler = QtLogHandler(self.log_page.log_view, self.log_page)
        self._log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logger.addHandler(self._log_handler)
        logger.setLevel(logging.INFO)

        self.setWindowTitle("Daedalus for Ikariam")
        self.setWindowIcon(application_icon())
        self.resize(1130, 780)
        self.setMinimumSize(900, 650)
        # Mac-standard shortcuts; refresh is read-only, never a task start.
        self._settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self._settings_shortcut.activated.connect(
            lambda: self.switchTo(self.appearance_page)
        )
        self._refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self._refresh_shortcut.activated.connect(self._refresh_current_view)
        self._search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._search_shortcut.activated.connect(self._focus_search)
        logger.info("Desktop ready; HTTPS and OS-keychain access are preferred")
        # Keychain access is deferred until the native window has rendered.
        # Only previously approved HTTPS endpoints are auto-connected; an old
        # loopback/SSH URL is never silently revived or migrated to a new host.
        QTimer.singleShot(0, self._auto_reconnect_securely)

    def systemTitleBarRect(self, size: QSize) -> QRect:
        """Preserve the original Mac GUI's traffic-light positioning."""
        if sys.platform != "darwin":
            return super().systemTitleBarRect(size)
        return QRect(0, 0 if self.isFullScreen() else 8, 75, size.height())

    def _refresh_current_view(self) -> None:
        """Only read-only refresh actions may be reached by a global shortcut."""
        if self.client is None or self._worker is not None:
            return
        current = self.stackedWidget.currentWidget()
        if current is self.accounts_page:
            self._request("accounts")
        elif current is self.warehouses_page:
            self.warehouses_page._load_all()
        elif current is self.tasks_page:
            if self.tasks_page.stack.currentIndex() == 4:
                self._request("capabilities")
            else:
                self.tasks_page._refresh_all()
        elif current is self.home_page:
            self._request("accounts")

    def _focus_search(self) -> None:
        if self.stackedWidget.currentWidget() is self.tasks_page:
            self.tasks_page._show_section(0)
            self.tasks_page.search_input.setFocus(Qt.ShortcutFocusReason)
            self.tasks_page.search_input.selectAll()

    def _save_gui_preferences(self) -> None:
        try:
            save_gui_preferences(self._gui_preferences)
        except GuiPreferenceError as exc:
            self._notice("GUI preference not saved", str(exc))

    def _on_appearance_changed(self, values: dict[str, object]) -> None:
        theme = values.get("theme")
        if theme not in {"auto", "light", "dark"}:
            return
        self._gui_preferences.theme = str(theme)
        self._gui_preferences.only_220k = values.get("only_220k") is True
        self._gui_preferences.group_by_island = values.get("group_by_island") is True
        setTheme({"auto": Theme.AUTO, "light": Theme.LIGHT, "dark": Theme.DARK}[theme])
        self.warehouses_page.set_display_preferences(
            only_220k=self._gui_preferences.only_220k,
            group_by_island=self._gui_preferences.group_by_island,
        )
        self._save_gui_preferences()

    def _select_working_account(self, account_id: str) -> None:
        self.warehouses_page.select_account(account_id)
        for view in self._task_views:
            view.select_account(account_id)

    def _view_home_warehouses(self, account_id: str) -> None:
        self._select_working_account(account_id)
        self.switchTo(self.warehouses_page)
        self._request("warehouses", account_id=account_id)

    def _view_all_warehouses(self) -> None:
        self.switchTo(self.warehouses_page)
        self.warehouses_page._load_all()

    def _view_all_automations(self) -> None:
        self.switchTo(self.tasks_page)
        self.tasks_page._refresh_all()

    def _view_home_automations(self, account_id: str) -> None:
        self._select_working_account(account_id)
        self.tasks_page._show_section(0)
        self.switchTo(self.tasks_page)
        self._request_task_refresh(account_id)

    def _configure_catalog_task(self, name: str) -> None:
        self.tasks_page.select_task(name)
        self.switchTo(self.tasks_page)
        account_id = self.tasks_page.selected_account_id()
        if account_id:
            self._request_task_refresh(account_id)

    def _request_warehouse_scope(self, action: str, account_ids: list[str]) -> None:
        """All-account Run behaves like the old warehouse bot: login first if needed."""
        if self.client is None or self._worker is not None or self._automatic_login_active:
            self._notice("Please finish the current request", "Warehouse refresh can be repeated safely.")
            return
        ids = list(dict.fromkeys(account_ids))
        if not ids or action not in {"warehouses", "warehouses_batch", "warehouses_all"}:
            return
        pending = [
            aid for aid in ids
            if (record := self.accounts_page.account_record(aid))
            and record.get("enabled") is True
            and record.get("session_status") != "authenticated"
        ]
        if (pending and isinstance(self._active_backend_url, str)
                and self._active_backend_url.startswith("https://")
                and self.accounts_page._native_browser_login_enabled):
            self._automatic_login_report = (action, ids)
            self._begin_automatic_logins(pending)
            return
        self._perform_warehouse_scope(action, ids)

    def _perform_warehouse_scope(self, action: str, account_ids: list[str]) -> None:
        if action == "warehouses":
            self._request(action, account_id=account_ids[0])
        else:
            self._request(action, task_payload={"account_ids": account_ids})

    def _begin_automatic_logins(self, ids: list[str]) -> None:
        """Mac-keychain-backed, headless-first Selenium sign-in for a chosen cohort.

        A sign-in click or Load warehouses click is the consent. The backend
        still requires a separate one-time account-scoped handoff confirmation.
        """
        if (self.client is None or self._worker is not None
                or self._selenium_worker is not None or self._automatic_login_active):
            self._notice("Sign-in busy", "Finish the active Daedalus request first.")
            return
        if (not isinstance(self._active_backend_url, str)
                or not self._active_backend_url.startswith("https://")
                or not self.accounts_page._native_browser_login_enabled):
            self._notice(
                "Automatic login unavailable",
                "Connect to a secure HTTPS backend with native session handoff enabled.",
            )
            return
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
            return
        self._automatic_login_queue = []
        for aid in dict.fromkeys(ids):
            record = self.accounts_page.account_record(aid) if isinstance(aid, str) else None
            if (record and record.get("enabled") is True
                    and record.get("session_status") != "authenticated"
                    and isinstance(record.get("world"), str)
                    and isinstance(record.get("player"), str)):
                self._automatic_login_queue.append(aid)
        self._automatic_login_cancelled = False
        self._automatic_login_successes = 0
        self._automatic_login_failures = 0
        self._automatic_login_active = bool(self._automatic_login_queue)
        if not self._automatic_login_active:
            self.accounts_page.auto_login_status.setText(
                "All chosen accounts already have verified sessions; no login needed."
            )
            report, self._automatic_login_report = self._automatic_login_report, None
            if report is not None:
                self._perform_warehouse_scope(*report)
            return
        self.accounts_page.set_automatic_login_busy(
            True, f"Starting headless Chrome for {len(self._automatic_login_queue)} accounts…"
        )
        self._advance_automatic_login()

    def _advance_automatic_login(self) -> None:
        if not self._automatic_login_active or self._worker is not None:
            return
        if self._automatic_login_cancelled:
            self._automatic_login_queue.clear()
        while self._automatic_login_queue:
            aid = self._automatic_login_queue.pop(0)
            record = self.accounts_page.account_record(aid)
            if not record or record.get("enabled") is not True:
                self._automatic_login_failures += 1
                continue
            world = str(record.get("world") or "")
            origin = str(self._active_backend_url)
            credentials = None
            save_credentials = False
            try:
                credentials = get_saved_login(origin, aid, world)
                save_credentials = credentials is not None
                if credentials is None:
                    wrapped = self._server_login_vaults.get(aid)
                    if isinstance(wrapped, dict):
                        credentials = unseal_login(origin, aid, world, wrapped)
                        save_credentials = credentials is not None
                if credentials is None:
                    # Exact-alias reuse from the old local IkaBot warehouse bot,
                    # never a whole-file migration or guessed account mapping.
                    credentials = legacy_warehouse_login(record)
                    save_credentials = credentials is not None
            except LoginCredentialError:
                self._notice(
                    "Saved login unavailable",
                    "Unlock macOS Keychain to restore the encrypted server login.",
                )
            if credentials is None:
                dialog = SeleniumCredentialsDialog(
                    player=str(record["player"]), world=world,
                    email=str(record.get("email") or ""), parent=self,
                )
                if dialog.exec() != QDialog.Accepted:
                    dialog.discard()
                    dialog.deleteLater()
                    self._automatic_login_failures += 1
                    continue
                try:
                    credentials = dialog.credentials()
                    save_credentials = dialog.remember.isChecked()
                finally:
                    dialog.discard()
                    dialog.deleteLater()
            self._automatic_login_current = aid
            self._automatic_login_credentials = credentials
            self._automatic_login_save_credentials = save_credentials
            self.accounts_page.set_automatic_login_busy(
                True, f"Signing in {record.get('label') or record.get('player')} "
                "with headless Selenium Chrome…",
            )
            self._request("native_login_start", account_id=aid)
            return
        self._finish_automatic_logins()

    def _finish_automatic_logins(self) -> None:
        succeeded = self._automatic_login_successes
        failures = self._automatic_login_failures
        cancelled = self._automatic_login_cancelled
        self._automatic_login_active = False
        self._automatic_login_cancelled = False
        self._automatic_login_queue.clear()
        self._automatic_login_current = None
        self._automatic_login_credentials = None
        self._automatic_login_challenge = None
        self.accounts_page.set_automatic_login_busy(
            False,
            f"Automatic sign-in {'cancelled' if cancelled else 'finished'}: "
            f"{succeeded} verified, {failures} unavailable. "
            "Unverified accounts remain unavailable; no game tasks were started.",
        )
        report, self._automatic_login_report = self._automatic_login_report, None
        if report is not None and not cancelled:
            self.switchTo(self.warehouses_page)
            # A successful login binds the verified cookie; a separate
            # authoritative worker is still needed to obtain snapshots.
            # Always ask the backend for a partial read-only result rather
            # than claiming all newly bound cookies are active workers.
            self._recovery_followup = ("accounts", "")
            self._perform_warehouse_scope(*report)
        elif self.client is not None and self._worker is None:
            self._request("accounts")

    def _cancel_automatic_logins(self) -> None:
        if not self._automatic_login_active:
            return
        self._automatic_login_cancelled = True
        self._automatic_login_queue.clear()
        self._automatic_login_report = None
        self.accounts_page.set_automatic_login_busy(
            True, "Cancelling Selenium login and discarding any unverified session…"
        )
        if self._selenium_worker is not None:
            self._selenium_worker.cancel()
        elif self._worker is None:
            self._finish_automatic_logins()

    def _launch_headless_selenium(self, challenge: dict[str, object]) -> None:
        aid = self._automatic_login_current
        record = self.accounts_page.account_record(aid) if aid else None
        if (self._automatic_login_cancelled or not self._automatic_login_active
                or record is None or challenge.get("account_id") != aid
                or record.get("world") != challenge.get("world")
                or self._automatic_login_credentials is None):
            self._cancel_selenium_handoff(challenge)
            return
        self._automatic_login_challenge = challenge
        worker = SeleniumLoginWorker(
            str(record["world"]), self._automatic_login_credentials, self
        )
        self._selenium_worker = worker
        worker.stage_changed.connect(self._selenium_progress)
        worker.cookie_ready.connect(self._selenium_success)
        worker.login_failed.connect(self._selenium_failure)
        worker.finished.connect(self._selenium_finished)
        worker.start()

    def _selenium_progress(self, stage: str) -> None:
        descriptions = {
            "headless_login": "Logging in automatically in headless Chrome…",
            "opening_visible_captcha": (
                "A CAPTCHA was detected. Opening visible Chrome only for that challenge…"
            ),
            "captcha_required": (
                "CAPTCHA needs you: complete the challenge in visible Chrome. "
                "Selenium continues automatically afterward."
            ),
            "captcha_resolved": "CAPTCHA solved. Selenium is opening the selected game world…",
            "visible_captcha_login": "Continuing the headless attempt in temporary visible Chrome…",
        }
        message = descriptions.get(stage)
        if message:
            self.accounts_page.set_automatic_login_busy(True, message)
        if stage == "captcha_required":
            self._notice("Gameforge CAPTCHA", "Complete it in the visible Chrome window; no password entry needed.")

    def _selenium_success(self, cookie: str) -> None:
        challenge = self._automatic_login_challenge
        aid = self._automatic_login_current
        record = self.accounts_page.account_record(aid) if aid else None
        if not challenge or not record or not self._automatic_login_credentials:
            return
        if self._automatic_login_cancelled:
            self._cancel_selenium_handoff(challenge)
            return
        try:
            account = Account(
                str(record["id"]), str(record["world"]), str(record["player"]),
                str(record.get("label") or record["player"]), True,
            )
            envelope = encrypt_mac_world_session(
                challenge, account, cookie,
                email=self._automatic_login_credentials.email,
            )
        except (NativeHandoffUnavailable, ValueError):
            self._notice("Gameforge session invalid", "World cookie was rejected before transmission.")
            self._cancel_selenium_handoff(challenge)
            return
        self.accounts_page.set_automatic_login_busy(
            True, "Headless sign-in complete. Waiting for independent server player verification…"
        )
        payload: dict[str, object] = {
            "ticket_id": challenge["ticket_id"], "envelope": envelope,
        }
        if self._automatic_login_save_credentials:
            try:
                payload["vault"] = seal_login(
                    str(self._active_backend_url), str(aid), str(record["world"]),
                    self._automatic_login_credentials,
                )
            except LoginCredentialError:
                # Do not block an authenticated session if backup fails.
                self._notice(
                    "Encrypted login backup unavailable",
                    "Unlock macOS Keychain to preserve the password securely.",
                )
        self._request("native_login_complete", account_id=aid, task_payload=payload)

    def _selenium_failure(self, reason: str) -> None:
        self._notice("Automatic sign-in unsuccessful", reason)
        if self._automatic_login_challenge is not None:
            self._cancel_selenium_handoff(self._automatic_login_challenge)

    def _selenium_finished(self) -> None:
        worker = self._selenium_worker
        self._selenium_worker = None
        if worker is not None:
            worker.deleteLater()
        # The Selenium finished signal and HTTP cancellation response can
        # arrive in either order. Advance exactly once after BOTH are idle.
        if self._worker is None and self._automatic_login_pending_advance:
            self._automatic_login_pending_advance = False
            QTimer.singleShot(0, self._advance_automatic_login)

    def _cancel_selenium_handoff(self, challenge: dict[str, object]) -> None:
        aid, ticket = challenge.get("account_id"), challenge.get("ticket_id")
        if isinstance(aid, str) and isinstance(ticket, str):
            self._request("native_login_cancel", account_id=aid,
                          task_payload={"ticket_id": ticket})
        else:
            self._automatic_login_failures += 1
            self._reset_automatic_attempt()
            self._automatic_login_pending_advance = True

    def _reset_automatic_attempt(self) -> None:
        self._automatic_login_current = None
        self._automatic_login_credentials = None
        self._automatic_login_challenge = None
        self._automatic_login_save_credentials = False

    def _begin_native_browser_login(self, account_id: str) -> None:
        if self.client is None or self._worker is not None:
            self._notice("Cannot open login", "Connect and finish the current request first.")
            return
        account = self.accounts_page.account_record(account_id)
        if account is None or account.get("enabled") is not True:
            return
        answer = QMessageBox.question(
            self, "Secure Gameforge browser login on your Mac",
            "An isolated Mac browser will open official Gameforge pages. "
            "You enter your password and complete any CAPTCHA yourself. "
            "When you approve the handoff, only the selected world's secure "
            "session cookie is encrypted to your backend. The server will "
            "independently verify your player before replacing any worker. "
            "Existing tasks are NEVER replayed. A dedicated worker must be idle "
            "and may be paused for recovery. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._request("native_login_start", account_id=account_id)

    def _open_native_browser_login(self, challenge: dict[str, object]) -> None:
        account_id = challenge.get("account_id")
        record = self.accounts_page.account_record(account_id) if isinstance(account_id, str) else None
        if (record is None or record.get("world") != challenge.get("world")
                or record.get("enabled") is not True):
            self._notice("Login cancelled", "The account identity changed before browser login.")
            if isinstance(account_id, str) and isinstance(challenge.get("ticket_id"), str):
                self._request("native_login_cancel", account_id=account_id,
                              task_payload={"ticket_id": challenge["ticket_id"]})
            return
        try:
            from daedalus.desktop.native_login_dialog import NativeLoginDialog

            dialog = NativeLoginDialog(
                world=str(record["world"]), player=str(record["player"]),
                ttl_seconds=int(challenge["expires_in_seconds"]), parent=self,
            )
        except (ImportError, RuntimeError, ValueError):
            logger.warning("Native browser could not open")
            self._notice("Native browser unavailable", "This preview needs the Qt WebEngine runtime.")
            self._request("native_login_cancel", account_id=account_id,
                          task_payload={"ticket_id": challenge["ticket_id"]})
            return
        was_polling = self._assistance_poll.isActive()
        self._assistance_poll.stop()
        try:
            if dialog.exec() != QDialog.Accepted:
                self._request("native_login_cancel", account_id=account_id,
                              task_payload={"ticket_id": challenge["ticket_id"]})
                return
            try:
                selected = Account(
                    str(record["id"]), str(record["world"]), str(record["player"]),
                    str(record.get("label") or record["player"]), True,
                )
                envelope = encrypt_mac_world_session(
                    challenge, selected, dialog.world_session(),
                    email=dialog.optional_email(),
                )
            except (NativeHandoffUnavailable, ValueError):
                self._notice("World login not ready", "The secure world session is invalid. Try again.")
                self._request("native_login_cancel", account_id=account_id,
                              task_payload={"ticket_id": challenge["ticket_id"]})
                return
            finally:
                dialog.discard_session()
            # The HTTP thread sees ciphertext only. It never owns a plaintext
            # Gameforge session, email, password or browser page.
            self._request("native_login_complete", account_id=account_id,
                          task_payload={"ticket_id": challenge["ticket_id"],
                                        "envelope": envelope})
        finally:
            dialog.dispose_browser()
            dialog.deleteLater()
            if was_polling:
                self._assistance_poll.start()

    def _request_task_refresh(self, account_id: str) -> None:
        if self.client is None:
            return
        if self._worker is not None:
            # Never silently lose a task-list refresh to the single-worker
            # busy guard, particularly after an uncertain task start.
            self._pending_task_refresh = account_id
        else:
            self._request("task_list", account_id=account_id)

    def _include_all_report_accounts(self) -> None:
        """Settings and Warehouses share one persisted account selection."""
        # Setting exclusions updates and persists the warehouse scope through
        # the existing report_selection_changed signal (no duplicate write).
        self.accounts_page.set_report_exclusions(set())

    def _on_report_selection_changed(self, selected: list[str]) -> None:
        self.warehouses_page.set_selected_accounts(selected)
        self.appearance_page.set_report_scope(
            len(self.warehouses_page._account_ids), len(
                self.warehouses_page._included_ids
            ),
        )
        if self._syncing_report_preferences or self._active_backend_url is None:
            return
        try:
            self._gui_preferences.set_excluded(
                self._active_backend_url, self.accounts_page.report_exclusions(),
            )
        except (ValueError, GuiPreferenceError):
            self._notice("Invalid report selection", "Unable to save selected accounts")
            return
        self._save_gui_preferences()

    def _auto_reconnect_securely(self) -> None:
        if self.client is not None or self._worker is not None:
            return
        try:
            saved = saved_connection()
        except PreferenceError:
            # Missing/locked Keychain is not a reason to block a first launch.
            # The user can unlock it through the OS or paste the token again.
            logger.info("Saved Keychain connection not currently available")
            return
        if saved is None or not saved[0].startswith("https://"):
            return
        self._connect(*saved, saved_keychain=True)

    def _start_offline_demo(self) -> None:
        """Explicit local demonstration; never imports real session data."""
        if self._worker is not None:
            self._notice("Request in progress", "Finish the backend request first.")
            return
        try:
            from daedalus.desktop.demo_backend import EmbeddedDemoServer, OfflineDemoUnavailable

            if self._embedded_demo is None:
                self._embedded_demo = EmbeddedDemoServer()
            self._embedded_demo.start()
        except (OfflineDemoUnavailable, ImportError) as exc:
            self._notice("Offline demo unavailable", str(exc))
            return
        # Temporary demo bearer tokens must never enter persistent preferences,
        # but preserve the user's normal Keychain choice for future real logins.
        remember = self.connection_page.remember_checkbox.isChecked()
        self.connection_page.remember_checkbox.setChecked(False)
        try:
            self._connect(self._embedded_demo.url, self._embedded_demo.token)
        finally:
            self.connection_page.remember_checkbox.setChecked(remember)

    def _connect_ssh(self, destination: str, token: str) -> None:
        if self._worker is not None:
            self._notice("Request in progress", "Finish the current request before connecting.")
            return
        try:
            destination = validate_ssh_destination(destination)
            if not token:
                # A saved bearer must never be sent to a different SSH host.
                # Reuse it only for the exact destination previously approved.
                stored_destination = load_ssh_destination()
                if stored_destination == destination:
                    saved = saved_connection()
                    if saved is not None and saved[0] == "http://127.0.0.1:8765":
                        token = saved[1]
            # Validate only the token shape without sending it over any network.
            test_client = DaedalusClient("http://127.0.0.1:8765", token)
            test_client.close()
        except (ValueError, PreferenceError) as exc:
            self._notice("Cannot connect via SSH", str(exc))
            return
        self._pending_ssh_destination = destination
        self._pending_ssh_token = token
        self._pending_preferences = (
            ("http://127.0.0.1:8765", token)
            if self.connection_page.remember_checkbox.isChecked() else None
        )
        worker = SecureSSHConnectionWorker(destination, token, parent=self)
        self._worker = worker
        self.connection_page.set_connecting(True)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _connect(self, url: str, token: str, *, saved_keychain: bool = False) -> None:
        if self._worker is not None:
            self._notice("Request in progress", "Finish the current request before connecting.")
            return
        # A saved trusted-HTTPS token must not be written again on every app
        # launch, which may otherwise trigger repeated macOS Keychain prompts.
        remembered = saved_keychain
        if not token:
            # An empty token field may use the OS Keychain only for exactly the
            # stored endpoint. Never forward a saved bearer to a different URL.
            try:
                saved = saved_connection()
            except PreferenceError as exc:
                self._notice("Keychain unavailable", str(exc))
                return
            if saved is None or saved[0] != url:
                self._notice("API token required", "Paste the token once to connect to this server.")
                return
            token = saved[1]
            remembered = True
        try:
            candidate = DaedalusClient(url, token)
        except ValueError as exc:
            self._notice("Invalid connection", str(exc))
            return
        self._pending_client = candidate
        self._pending_secret_saved = remembered
        self._pending_preferences = (
            (url, token) if self.connection_page.remember_checkbox.isChecked() and not remembered
            else None
        )
        self._launch(candidate, "connect")

    def _reconnect(self) -> None:
        """Explicitly repeat only read-only handshake, never game task dispatch."""
        if self._worker is not None:
            self._notice("Request in progress", "Finish the current request first.")
            return
        if self._ssh_tunnel is not None:
            if self._ssh_tunnel.running() and self.client is not None:
                self._launch(self.client, "connect")
                return
            if self._active_ssh_destination and self._active_ssh_token:
                self._connect_ssh(self._active_ssh_destination, self._active_ssh_token)
                return
        elif self.client is not None:
            self._launch(self.client, "connect")
            return
        try:
            saved = saved_connection()
        except PreferenceError as exc:
            self._notice("Cannot retrieve saved connection", str(exc))
            return
        if saved is None:
            self._notice("No saved connection", "Enter an SSH host and API token.")
            return
        try:
            destination = load_ssh_destination()
        except SSHConnectionUnavailable:
            destination = None
        if destination and not saved[0].startswith("https://"):
            self._connect_ssh(destination, saved[1])
        else:
            self._connect(*saved, saved_keychain=True)

    def _forget_connection(self) -> None:
        try:
            forget_connection()
        except PreferenceError as exc:
            self._notice("Unable to forget saved connection", str(exc))
            return
        try:
            forget_ssh_destination()
        except SSHConnectionUnavailable as exc:
            self._notice("SSH host preference not cleared", str(exc))
            return
        self.connection_page.set_token_saved(False)
        self.connection_page.remember_checkbox.setChecked(False)
        self._notice("Saved preference cleared", "The current in-memory connection is unchanged.")

    def _poll_pending_assistance(self) -> None:
        if self.client is not None and self._worker is None:
            self._launch(self.client, "assistance_pending")

    def _request(
        self, action: str, *, account_id: str | None = None,
        task_payload: dict[str, object] | None = None,
    ) -> None:
        if self.client is None:
            self._notice("Not connected", "Connect to a Daedalus backend first.")
            return
        if self._worker is not None:
            self._notice("Request in progress", "Another backend request is still running.")
            return
        self._launch(self.client, action, account_id=account_id, task_payload=task_payload)

    def _queue_task_preflight(self, account_id: str, task: str) -> None:
        """Queue only current-generation readiness checks for the single workspace."""
        view = self.tasks_page
        if view.selected_account_id() != account_id or view.selected_task_name() != task:
            return
        key = (account_id, task, view._selection_generation)
        # Superseded drafts should never consume a queued request slot.
        self._preflight_queue = [item for item in self._preflight_queue if item == key]
        if key not in self._preflight_queue:
            self._preflight_queue.append(key)
        if self._worker is None:
            self._run_next_preflight()

    def _run_next_preflight(self) -> None:
        if self.client is None or self._worker is not None:
            return
        # A prior selection may have become obsolete during the last network call.
        while self._preflight_queue:
            account_id, task, generation = self._preflight_queue.pop(0)
            view = self.tasks_page
            if (view.selected_account_id() == account_id
                    and view.selected_task_name() == task
                    and view._selection_generation == generation):
                self._launch(
                    self.client, "task_preflight", account_id=account_id,
                    task_payload={"task": task, "generation": generation},
                )
                return

    def _launch(
        self, client: DaedalusClient, action: str, *, account_id: str | None = None,
        task_payload: dict[str, object] | None = None,
    ) -> None:
        worker = APIWorker(
            client, action, account_id=account_id, task_payload=task_payload, parent=self,
        )
        self._worker = worker
        if action == "connect":
            self.connection_page.set_connecting(True)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_completed(self, action: str, payload: object) -> None:
        if action == "ssh_connect":
            assert isinstance(payload, dict)
            self._pending_client = payload["client"]
            self._pending_ssh_tunnel = payload["tunnel"]
            payload = payload["result"]
            action = "connect"
        if action == "connect":
            assert isinstance(payload, dict)
            if self._pending_client is not None:
                if self.client is not None and self.client is not self._pending_client:
                    self.client.close()
                self.client = self._pending_client
                self._pending_client = None
                old_tunnel = self._ssh_tunnel
                self._ssh_tunnel = self._pending_ssh_tunnel
                self._pending_ssh_tunnel = None
                if old_tunnel is not None and old_tunnel is not self._ssh_tunnel:
                    old_tunnel.close()
                self._active_ssh_destination = self._pending_ssh_destination
                self._active_ssh_token = self._pending_ssh_token
            preferences = self._pending_preferences
            self._pending_preferences = None
            token_saved = self._pending_secret_saved
            self._pending_secret_saved = False
            if preferences is not None:
                try:
                    remember_connection(*preferences)
                    token_saved = True
                    if self._pending_ssh_destination:
                        save_ssh_destination(self._pending_ssh_destination)
                except (PreferenceError, SSHConnectionUnavailable, ValueError) as exc:
                    self._notice("Connection not saved", str(exc))
            self.connection_page.set_token_saved(token_saved)
            self._pending_ssh_destination = None
            self._pending_ssh_token = None
            health = payload.get("health") or {}
            demo = bool(health.get("synthetic_demo") is True)
            self.connection_page.set_connected(True, demo=demo)
            self.home_page.set_connected(True, demo=demo)
            browser_capability = payload.get("native_browser_login") or {}
            self.accounts_page.set_native_browser_login_enabled(
                not demo and browser_capability.get("enabled") is True
            )
            self.warehouses_page.set_demo(demo)
            self.warehouses_page.clear_reports()
            self.setWindowTitle("Daedalus for Ikariam — SYNTHETIC DEMO" if demo else "Daedalus for Ikariam")
            # Report selection must never leak across remote backends.
            self._syncing_report_preferences = True
            try:
                # SSH forwarding uses a different random local port on every
                # launch; scope private report choices by the trusted host.
                prior_backend_url = self._active_backend_url
                self._active_backend_url = (
                    "ssh://" + self._active_ssh_destination
                    if self._ssh_tunnel is not None and self._active_ssh_destination
                    else getattr(self.client, "_server", None)
                )
                if (prior_backend_url is not None
                        and prior_backend_url != self._active_backend_url):
                    # Equal account IDs on two servers are not equal authority.
                    # Never carry a prior backend's task review, preflight,
                    # selection or cached account summary into the new session.
                    self._preflight_queue.clear()
                    self._pending_task_refresh = None
                    self._pending_batch_status = None
                    self.tasks_page.reset_backend_context()
                    self.home_page.set_accounts([])
                excluded = self._gui_preferences.excluded_for(self._active_backend_url) if self._active_backend_url else set()
                self.accounts_page.set_report_exclusions(excluded)
                self.accounts_page.set_connected_ids(
                    payload.get("connected_accounts")
                    if isinstance(payload.get("connected_accounts"), list) else None
                )
                vaults = payload.get("login_vaults")
                self._server_login_vaults = vaults if isinstance(vaults, dict) else {}
                self._show_accounts(payload["accounts"])
            finally:
                self._syncing_report_preferences = False
            self._on_report_selection_changed(self.accounts_page.selected_report_account_ids())
            self._show_capabilities(payload["capabilities"])
            enabled = bool(payload["capabilities"].get("session_monitoring", False))
            self._seen_assistance_ids.clear()
            if enabled:
                self._assistance_poll.start()
                QTimer.singleShot(0, self._poll_pending_assistance)
            else:
                self._assistance_poll.stop()
            self.accounts_page.set_editable_config(
                payload.get("account_config", {"enabled": False})
            )
            logger.info("Connected to Daedalus API")
        elif action == "accounts":
            self._show_accounts(payload)
            logger.info("Accounts refreshed")
        elif action == "login_vault_sync":
            assert isinstance(payload, dict)
            self._notice(
                "Encrypted logins backed up",
                f"{payload['saved']} stored securely on the server; "
                f"{payload['missing']} not yet saved on this Mac; "
                f"{payload['failed']} could not be backed up.",
            )
        elif action == "account_config":
            assert isinstance(payload, dict)
            self.accounts_page.set_editable_config(payload)
        elif action == "account_config_put":
            assert isinstance(payload, dict)
            self.accounts_page.set_editable_config(payload)
            logger.info("Account metadata changed after explicit confirmation")
            self._notice("Account metadata saved", "Account metadata updated; refreshing views.")
            QTimer.singleShot(0, lambda: self._request("accounts"))
        elif action == "monitor_attach":
            assert isinstance(payload, dict)
            self._notice(
                "Session monitoring enabled",
                "Existing IkaBot session validated; no new login or task was started.",
            )
            QTimer.singleShot(0, lambda: self._request("accounts"))
        elif action == "assistance_pending":
            assert isinstance(payload, dict)
            for ticket in payload.get("tickets", []):
                ticket_id = ticket.get("ticket_id")
                if (
                    isinstance(ticket_id, str)
                    and ticket_id not in self._seen_assistance_ids
                    and ticket.get("state") == "waiting_operator"
                ):
                    self._seen_assistance_ids.add(ticket_id)
                    self._notice(
                        "Manual account assistance needed",
                        "An existing IkaBot session needs attention. Open Accounts to review.",
                    )
        elif action in {"auth_assistance", "auth_assistance_approve"}:
            assert isinstance(payload, dict)
            self.accounts_page.set_assistance(payload)
            if action == "auth_assistance_approve":
                logger.info("Operator completed manual step; worker validation still required")
                self._notice(
                    "Assistance acknowledged",
                    "The game worker still must validate authentication before resuming.",
                )
                account_id = payload.get("account_id")
                if isinstance(account_id, str):
                    self._recovery_followup = ("recovery_guide", account_id)
        elif action == "native_login_start":
            assert isinstance(payload, dict)
            self._pending_native_login_challenge = payload
            logger.info("One-time Mac browser login prepared; no game action started")
        elif action == "native_login_complete":
            assert isinstance(payload, dict)
            automatic_result = (
                self._automatic_login_active
                and payload.get("account_id") == self._automatic_login_current
            )
            if automatic_result:
                if self._automatic_login_save_credentials:
                    creds = self._automatic_login_credentials
                    record = self.accounts_page.account_record(self._automatic_login_current)
                    if creds is not None and record is not None:
                        try:
                            remember_login(
                                str(self._active_backend_url), str(record["id"]),
                                str(record["world"]), creds,
                            )
                        except LoginCredentialError:
                            self._notice(
                                "Gameforge login not remembered",
                                "Unlock macOS Keychain. The server verified the session, "
                                "but future automatic logins need saved credentials.",
                            )
                self._automatic_login_successes += 1
                self._reset_automatic_attempt()
                self._automatic_login_pending_advance = True
            if payload.get("status") == "worker_recovered_verified":
                self._notice(
                    "Game session verified",
                    "The backend independently verified the selected player and "
                    "rebound the idle worker. No old task was restarted.",
                )
            else:
                self._notice(
                    "Game session verified and saved",
                    "The server stored a verified world session in its OS keyring. "
                    "Start or attach a dedicated worker before running tasks.",
                )
            # The cohort queue must advance before refreshing account status:
            # a refresh launched here consumes the only APIWorker slot and
            # strands the next Selenium account in a busy state.
            if not automatic_result:
                self._recovery_followup = ("accounts", "")
        elif action == "native_login_cancel":
            if self._automatic_login_active and self._automatic_login_current:
                self._automatic_login_failures += 1
                self._reset_automatic_attempt()
                self._automatic_login_pending_advance = True
            self._notice(
                "Mac browser login cancelled",
                "No new session was imported. A dedicated worker may remain "
                "paused; start a new login or review its recovery status.",
            )
        elif action == "recovery_guide":
            assert isinstance(payload, dict)
            self.accounts_page.set_recovery_guide(payload)
        elif action == "recovery_prepare":
            assert isinstance(payload, dict)
            self._notice(
                "Dedicated worker recovery prepared",
                "New tasks are paused. Complete human login only on the "
                "authoritative worker host, then acknowledge the manual step.",
            )
            account_id = payload.get("account_id")
            if isinstance(account_id, str):
                # Render the returned safe broker ticket immediately. The
                # worker is still completing this request; queue only one
                # follow-up, rather than dropping a concurrent second fetch.
                self.accounts_page.set_assistance({
                    "enabled": True,
                    "account_id": account_id,
                    "ticket": payload.get("ticket"),
                })
                self._recovery_followup = ("recovery_guide", account_id)
        elif action == "worker_rebind":
            assert isinstance(payload, dict)
            logger.info("Dedicated worker rebind completed after host-only game attestation")
            self._notice(
                "Recovered worker verified",
                "Authoritative worker confirmed the game-world player. "
                "Old tasks were not replayed.",
            )
            self._recovery_followup = ("accounts", "")
        elif action == "connected_accounts":
            assert isinstance(payload, list)
            self.accounts_page.set_connected_ids(payload)
            logger.info("IkaBot existing-session status refreshed")
        elif action == "capabilities":
            self._show_capabilities(payload)
            logger.info("Operations inventory refreshed")
        elif action == "warehouses":
            assert isinstance(payload, dict)
            self.warehouses_page.set_snapshots(payload["account_id"], payload["cities"])
            self.home_page.set_warehouse_report(1)
            logger.info("Warehouse snapshot report updated")
        elif action in {"warehouses_batch", "warehouses_all"}:
            assert isinstance(payload, list)
            self.warehouses_page.set_batch_snapshots(payload)
            successful = sum(
                isinstance(item, dict) and isinstance(item.get("cities"), list)
                and not item.get("error") for item in payload
            )
            self.home_page.set_warehouse_report(successful, len(payload) - successful)
            logger.info("Multi-account warehouse report updated")
        elif action == "task_preflight":
            assert isinstance(payload, dict)
            worker = self._worker
            request = getattr(worker, "task_payload", None)
            generation = request.get("generation") if isinstance(request, dict) else None
            view = self.tasks_page
            if generation is None or generation == view._selection_generation:
                view.set_preflight(payload)
        elif action == "task_list_batch":
            assert isinstance(payload, list)
            for view in self._task_views:
                view.set_batch_status(payload)
            successful = sum(
                isinstance(item, dict) and not item.get("error")
                and isinstance(item.get("engine_tasks"), list) for item in payload
            )
            self.home_page.set_task_report(successful, len(payload) - successful)
            logger.info("Multi-account read-only managed task statuses refreshed")
        elif action == "task_start_batch":
            assert isinstance(payload, dict)
            for view in self._task_views:
                view.set_batch_launch_result(payload)
            ids = payload.get("account_ids", [])
            if isinstance(ids, list):
                self._pending_batch_status = ids
            if payload.get("blocked"):
                self._notice(
                    "Multi-account automation blocked",
                    "No account was launched. Review the readiness of each selected account.",
                )
            elif payload.get("halted"):
                self._notice(
                    "Multi-account automation stopped",
                    "A request may be unconfirmed. No further accounts were started. "
                    "Inspect the request ledger before retrying.",
                )
            else:
                count = len(payload.get("submitted", []))
                InfoBar.success(
                    "Automation requests received",
                    f"Received {count} account-scoped receipts; review their status.",
                    parent=self, position=InfoBarPosition.TOP_RIGHT,
                )
        elif action == "task_list":
            assert isinstance(payload, dict)
            account_id = payload.get("account_id")
            for view in self._task_views:
                if account_id == view.selected_account_id() or (
                    account_id is None and view is self.tasks_page
                ):
                    view.set_tasks(payload)
            logger.info("Managed tasks refreshed")
        elif action in {"task_start", "task_stop", "task_reconcile"}:
            assert isinstance(payload, dict)
            if action == "task_start":
                for view in self._task_views:
                    view.finish_launch()
            logger.info("Task operation acknowledged: %s", action)
            self._notice("Task operation accepted", str(payload.get("status", "Complete")))
            account_id = payload.get("account_id")
            if isinstance(account_id, str):
                self._pending_task_refresh = account_id

    def _show_accounts(self, data: object) -> None:
        assert isinstance(data, list)
        visible = []
        for raw in data:
            account = dict(raw)
            # Local Keychain can also identify an imported account even when
            # a previous backend version omits its protected email binding.
            if (not account.get("email")
                    and isinstance(self._active_backend_url, str)
                    and self._active_backend_url.startswith("https://")):
                try:
                    saved = get_saved_login(
                        self._active_backend_url,
                        str(account["id"]), str(account["world"]),
                    )
                except (LoginCredentialError, KeyError):
                    saved = None
                if saved is not None:
                    account["email"] = saved.email
            visible.append(account)
        self.accounts_page.set_accounts(visible)
        self.warehouses_page.set_accounts(visible)
        self.home_page.set_accounts(visible)
        # Refresh inclusion *after* the warehouse account map is replaced.
        # This also handles accounts newly created via metadata editing.
        self.warehouses_page.set_selected_accounts(
            self.accounts_page.selected_report_account_ids()
        )
        self.appearance_page.set_report_scope(
            len(self.warehouses_page._account_ids),
            len(self.warehouses_page._included_ids),
        )
        for view in self._task_views:
            view.set_accounts(data)

    def _show_capabilities(self, data: object) -> None:
        assert isinstance(data, dict)
        for view in self._task_views:
            view.set_capabilities(
                data["operations"], bool(data.get("structured_engine_dispatch", False)),
            )
        self.accounts_page.set_monitoring_enabled(bool(data.get("session_monitoring", False)))

    def _on_failed(self, action: str, error: str) -> None:
        # Never reuse a recovery refresh across a failed or changed backend.
        self._recovery_followup = None
        if action == "native_login_start":
            self._pending_native_login_challenge = None
        if (action in {"native_login_start", "native_login_complete", "native_login_cancel"}
                and self._automatic_login_active and self._automatic_login_current):
            self._automatic_login_failures += 1
            self._reset_automatic_attempt()
            self._automatic_login_pending_advance = True
        if action == "task_preflight":
            worker = self._worker
            request = getattr(worker, "task_payload", None)
            generation = request.get("generation") if isinstance(request, dict) else None
            if generation is None or generation == self.tasks_page._selection_generation:
                self.tasks_page.set_preflight_unavailable()
        if action in {"task_start_batch", "task_start"}:
            for view in self._task_views:
                view.finish_launch()
        if action == "task_start_batch":
            # Failure could have happened after an irreversible request;
            # do not rerun or automatically acknowledge a task.
            self._pending_batch_status = None
            self._notice(
                "Multi-account dispatch interrupted",
                "Check every selected account's request history before starting again.",
            )
        if action in {"task_start", "task_stop", "task_reconcile"} and self._worker is not None:
            account_id = getattr(self._worker, "account_id", None)
            if isinstance(account_id, str):
                self._pending_task_refresh = account_id
        if action in {"warehouses", "warehouses_batch", "warehouses_all"}:
            self.warehouses_page.status_label.setText(
                "Warehouse refresh failed. The earlier report, if shown, is stale. "
                "Check your account sessions and try again."
            )
        if action in {"connect", "ssh_connect"}:
            self._pending_ssh_destination = None
            self._pending_ssh_token = None
            if self._pending_ssh_tunnel is not None:
                self._pending_ssh_tunnel.close()
                self._pending_ssh_tunnel = None
            self._pending_preferences = None
            self._pending_secret_saved = False
            if self._pending_client is not None:
                self._pending_client.close()
                self._pending_client = None
            if self.client is None:
                self.connection_page.set_connection_error(error)
            else:
                # A failed reconnect must not hide an existing authorized session.
                self.connection_page.set_connected(True)
        logger.warning("Backend %s request failed", action)
        if action not in {"assistance_pending", "task_preflight"}:
            if action.startswith("native_login_"):
                known_reason = str(error) if str(error) in {
                    "A Gameforge email is required for first-time account binding",
                    "This worker is busy or has an uncertain task; reconcile it before login",
                    "Running or uncertain tasks must be reconciled before login",
                } else None
                self._notice(
                    "Mac browser recovery unavailable",
                    known_reason or "The server could not complete the secure session step. "
                    "Check that the worker is idle, prior uncertain tasks are reconciled, "
                    "and the selected account is configured on the server.",
                )
            elif action in {"connect", "ssh_connect"}:
                self._notice(
                    "Secure connection failed",
                    self.connection_page.status_label.text(),
                )
            elif action == "task_start":
                self._notice("Automation not started", error)
            elif action in {"task_stop", "task_reconcile"}:
                self._notice("Automation action failed", error)
            else:
                self._notice("Backend unavailable", error)

    def _on_worker_finished(self) -> None:
        self._worker = None
        self.connection_page.set_connecting(False)
        challenge, self._pending_native_login_challenge = (
            self._pending_native_login_challenge, None
        )
        if challenge is not None and self.client is not None:
            if self._automatic_login_active:
                QTimer.singleShot(0, lambda: self._launch_headless_selenium(challenge))
            else:
                QTimer.singleShot(0, lambda: self._open_native_browser_login(challenge))
            return
        followup, self._recovery_followup = self._recovery_followup, None
        if followup is not None and self.client is not None:
            action, account_id = followup
            self._request(action, account_id=account_id or None)
        if self._worker is None and self._pending_task_refresh is not None:
            account_id = self._pending_task_refresh
            self._pending_task_refresh = None
            self._request("task_list", account_id=account_id)
        if self._worker is None and self._pending_batch_status:
            ids = self._pending_batch_status
            self._pending_batch_status = None
            self._request("task_list_batch", task_payload={"account_ids": ids})
        if (self._worker is None and self._selenium_worker is None
                and self._automatic_login_pending_advance):
            self._automatic_login_pending_advance = False
            QTimer.singleShot(0, self._advance_automatic_login)
        if self._worker is None and not self._automatic_login_active:
            self._run_next_preflight()

    def _notice(self, title: str, message: str) -> None:
        InfoBar.warning(
            title, message, parent=self, position=InfoBarPosition.TOP_RIGHT
        )

    def closeEvent(self, event) -> None:
        self._assistance_poll.stop()
        # Never destroy a live Selenium QThread/Chrome driver while Gameforge
        # may still own an active challenge. Request cooperative cancellation.
        if self._selenium_worker is not None and self._selenium_worker.isRunning():
            self._selenium_worker.cancel()
            event.ignore()
            self._notice(
                "Selenium login stopping",
                "Chrome is closing. Close Daedalus after automatic login stops.",
            )
            return
        # Preserve the old GUI's rule: never destroy a live QThread.
        if (
            self._worker is not None
            and self._worker.isRunning()
            and not self._worker.wait(9000)
        ):
            event.ignore()
            self._notice("Request still running", "Close the window after the request finishes.")
            return
        if self.client is not None:
            self.client.close()
            self.client = None
        if self._ssh_tunnel is not None:
            self._ssh_tunnel.close()
            self._ssh_tunnel = None
        if self._pending_ssh_tunnel is not None:
            self._pending_ssh_tunnel.close()
            self._pending_ssh_tunnel = None
        if self._pending_client is not None:
            self._pending_client.close()
            self._pending_client = None
        if self._embedded_demo is not None:
            from daedalus.desktop.demo_backend import OfflineDemoUnavailable

            try:
                self._embedded_demo.stop()
            except OfflineDemoUnavailable:
                logger.warning("Ephemeral local demo backend shutdown was incomplete")
            self._embedded_demo = None
        logger.removeHandler(self._log_handler)
        super().closeEvent(event)
