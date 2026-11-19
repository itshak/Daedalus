"""Native Fluent control center. Adapted from the user's original Mac main window.

The read-only views remain safe by default. An explicitly enabled backend can
accept user-confirmed task start/stop actions through existing-session IPC.
No Selenium login or new game worker is started from this desktop shell.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, QRect, QSize, QThread, QTimer, Signal
from PySide6.QtWidgets import QPlainTextEdit, QSizePolicy, QSpacerItem
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    NavigationItemPosition,
    Theme,
    setTheme,
)

from daedalus.client import APIConnectionError, DaedalusClient
from daedalus.connection_prefs import (
    PreferenceError,
    forget_connection,
    remember_connection,
    saved_connection,
)
from daedalus.desktop.appearance_page import AppearancePage
from daedalus.desktop.branding import application_icon
from daedalus.desktop.home_page import HomePage
from daedalus.desktop.log_page import LogPage
from daedalus.desktop.pages import AccountsPage, ConnectionPage, OperationsPage, WarehousesPage
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

logger = logging.getLogger("daedalus.desktop")


class QtLogBridge(QObject):
    """Keep the legacy GUI's queued-signal logging to avoid cross-thread Qt crashes."""

    message = Signal(str)

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
    def __init__(self, widget: QPlainTextEdit) -> None:
        super().__init__()
        self.bridge = QtLogBridge(widget)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.bridge.message.emit(self.format(record))
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
                }
            elif self.action == "accounts":
                result = self.client.accounts()
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
            elif self.action == "warehouses_batch" and self.task_payload is not None:
                ids = self.task_payload.get("account_ids")
                if (
                    not isinstance(ids, list) or not 1 <= len(ids) <= 32
                    or any(not isinstance(aid, str) for aid in ids)
                    or len(set(ids)) != len(ids)
                ):
                    raise ValueError("Select between 1 and 32 distinct report accounts")
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
        self._preflight_queue: list[tuple[str, str]] = []
        self._pending_task_refresh: str | None = None
        self._recovery_followup: tuple[str, str] | None = None
        self._embedded_demo = None
        self._seen_assistance_ids: set[str] = set()
        self._active_backend_url: str | None = None
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
        self.operations_page = OperationsPage(self)
        self.tasks_page = TasksPage(self)
        self.wine_page = TasksPage(self, workflow="wine")
        self.construction_page = TasksPage(self, workflow="construction")
        self._task_views = (self.tasks_page, self.wine_page, self.construction_page)
        self.log_page = LogPage(self)
        self.connection_page = ConnectionPage(self)
        self.appearance_page = AppearancePage(self)
        self.appearance_page.set_preferences(self._gui_preferences)
        self.warehouses_page.set_display_preferences(
            only_220k=self._gui_preferences.only_220k,
            group_by_island=self._gui_preferences.group_by_island,
        )

        self.addSubInterface(self.home_page, FIF.HOME, "Home")
        self.addSubInterface(self.accounts_page, FIF.PEOPLE, "Accounts")
        self.addSubInterface(self.warehouses_page, FIF.SAVE, "Warehouses")
        self.addSubInterface(self.wine_page, FIF.PLAY, "Wine")
        self.addSubInterface(self.construction_page, FIF.EDIT, "Construction")
        self.addSubInterface(self.tasks_page, FIF.PLAY, "Automations")
        self.addSubInterface(self.operations_page, FIF.APPLICATION, "Explore")
        self.addSubInterface(self.log_page, FIF.DOCUMENT, "Activity")
        self.addSubInterface(
            self.appearance_page, FIF.SETTING, "Appearance", NavigationItemPosition.BOTTOM
        )
        self.addSubInterface(
            self.connection_page, FIF.SETTING, "Connection", NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.setReturnButtonVisible(False)
        header = self.navigationInterface.panel.topLayout
        header.insertSpacerItem(0, QSpacerItem(40, 36, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.connection_page.ssh_connect_requested.connect(self._connect_ssh)
        self.connection_page.connect_requested.connect(self._connect)
        self.connection_page.demo_requested.connect(self._start_offline_demo)
        self.connection_page.reconnect_requested.connect(self._reconnect)
        self.connection_page.forget_requested.connect(self._forget_connection)
        self.appearance_page.preferences_changed.connect(self._on_appearance_changed)
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
        self.home_page.manage_automations.connect(self._view_home_automations)
        self.operations_page.configure_requested.connect(self._configure_catalog_task)
        self.operations_page.refresh_requested.connect(lambda: self._request("capabilities"))
        self.warehouses_page.load_requested.connect(
            lambda account_id: self._request("warehouses", account_id=account_id)
        )
        self.warehouses_page.load_selected_requested.connect(
            lambda ids: self._request("warehouses_batch", task_payload={"account_ids": ids})
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

        self._log_handler = QtLogHandler(self.log_page.log_view)
        self._log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logger.addHandler(self._log_handler)
        logger.setLevel(logging.INFO)

        self.setWindowTitle("Daedalus for Ikariam")
        self.setWindowIcon(application_icon())
        self.resize(1130, 780)
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

    def _view_home_automations(self, account_id: str) -> None:
        self._select_working_account(account_id)
        self.switchTo(self.tasks_page)
        self._request_task_refresh(account_id)

    def _configure_catalog_task(self, name: str) -> None:
        self.tasks_page.select_task(name)
        self.switchTo(self.tasks_page)
        account_id = self.tasks_page.selected_account_id()
        if account_id:
            self._request_task_refresh(account_id)

    def _request_task_refresh(self, account_id: str) -> None:
        if self.client is None:
            return
        if self._worker is not None:
            # Never silently lose a task-list refresh to the single-worker
            # busy guard, particularly after an uncertain task start.
            self._pending_task_refresh = account_id
        else:
            self._request("task_list", account_id=account_id)

    def _on_report_selection_changed(self, selected: list[str]) -> None:
        self.warehouses_page.set_selected_accounts(selected)
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
        self.connection_page.connect_button.setEnabled(False)
        self.connection_page.ssh_button.setEnabled(False)
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
        """Defer harmless readiness probes until the single HTTP worker is free."""
        key = (account_id, task)
        if key not in self._preflight_queue:
            self._preflight_queue.append(key)
        if self._worker is None:
            self._run_next_preflight()

    def _run_next_preflight(self) -> None:
        if self.client is None or self._worker is not None:
            return
        # A prior selection may have become obsolete during the last network call.
        while self._preflight_queue:
            account_id, task = self._preflight_queue.pop(0)
            if any(
                view.selected_account_id() == account_id
                and view.selected_task_name() == task
                for view in self._task_views
            ):
                self._launch(
                    self.client, "task_preflight", account_id=account_id,
                    task_payload={"task": task},
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
        self.connection_page.connect_button.setEnabled(False)
        self.connection_page.ssh_button.setEnabled(False)
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
            self.warehouses_page.set_demo(demo)
            self.warehouses_page.clear_reports()
            self.setWindowTitle("Daedalus for Ikariam — SYNTHETIC DEMO" if demo else "Daedalus for Ikariam")
            # Report selection must never leak across remote backends.
            self._syncing_report_preferences = True
            try:
                # SSH forwarding uses a different random local port on every
                # launch; scope private report choices by the trusted host.
                self._active_backend_url = (
                    "ssh://" + self._active_ssh_destination
                    if self._ssh_tunnel is not None and self._active_ssh_destination
                    else getattr(self.client, "_server", None)
                )
                excluded = self._gui_preferences.excluded_for(self._active_backend_url) if self._active_backend_url else set()
                self.accounts_page.set_report_exclusions(excluded)
                self.accounts_page.set_connected_ids(None)
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
            logger.info("Warehouse snapshot report updated")
        elif action == "warehouses_batch":
            assert isinstance(payload, list)
            self.warehouses_page.set_batch_snapshots(payload)
            logger.info("Multi-account warehouse report updated")
        elif action == "task_preflight":
            assert isinstance(payload, dict)
            for view in self._task_views:
                view.set_preflight(payload)
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
            logger.info("Task operation acknowledged: %s", action)
            self._notice("Task operation accepted", str(payload.get("status", "Complete")))
            account_id = payload.get("account_id")
            if isinstance(account_id, str):
                self._pending_task_refresh = account_id

    def _show_accounts(self, data: object) -> None:
        assert isinstance(data, list)
        self.accounts_page.set_accounts(data)
        self.warehouses_page.set_accounts(data)
        self.home_page.set_accounts(data)
        # Refresh inclusion *after* the warehouse account map is replaced.
        # This also handles accounts newly created via metadata editing.
        self.warehouses_page.set_selected_accounts(
            self.accounts_page.selected_report_account_ids()
        )
        for view in self._task_views:
            view.set_accounts(data)

    def _show_capabilities(self, data: object) -> None:
        assert isinstance(data, dict)
        self.operations_page.set_operations(data["operations"])
        for view in self._task_views:
            view.set_capabilities(
                data["operations"], bool(data.get("structured_engine_dispatch", False)),
            )
        self.accounts_page.set_monitoring_enabled(bool(data.get("session_monitoring", False)))

    def _on_failed(self, action: str, error: str) -> None:
        # Never reuse a recovery refresh across a failed or changed backend.
        self._recovery_followup = None
        if action == "task_preflight":
            for view in self._task_views:
                view.set_preflight_unavailable()
        if action in {"task_start", "task_stop", "task_reconcile"} and self._worker is not None:
            account_id = getattr(self._worker, "account_id", None)
            if isinstance(account_id, str):
                self._pending_task_refresh = account_id
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
            self.connection_page.set_connected(self.client is not None)
        logger.warning("Backend %s request failed", action)
        if action not in {"assistance_pending", "task_preflight"}:
            if action == "task_start":
                self._notice("Automation not started", error)
            elif action in {"task_stop", "task_reconcile"}:
                self._notice("Automation action failed", error)
            else:
                self._notice("Backend unavailable", error)

    def _on_worker_finished(self) -> None:
        self._worker = None
        self.connection_page.connect_button.setEnabled(True)
        self.connection_page.ssh_button.setEnabled(True)
        followup, self._recovery_followup = self._recovery_followup, None
        if followup is not None and self.client is not None:
            action, account_id = followup
            self._request(action, account_id=account_id or None)
        if self._worker is None and self._pending_task_refresh is not None:
            account_id = self._pending_task_refresh
            self._pending_task_refresh = None
            self._request("task_list", account_id=account_id)
        if self._worker is None:
            self._run_next_preflight()

    def _notice(self, title: str, message: str) -> None:
        InfoBar.warning(
            title, message, parent=self, position=InfoBarPosition.TOP_RIGHT
        )

    def closeEvent(self, event) -> None:
        self._assistance_poll.stop()
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
