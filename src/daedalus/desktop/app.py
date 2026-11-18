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
from qfluentwidgets import FluentWindow, InfoBar, InfoBarPosition, NavigationItemPosition

from daedalus.client import APIConnectionError, DaedalusClient
from daedalus.connection_prefs import (
    PreferenceError,
    forget_connection,
    remember_connection,
    saved_connection,
)
from daedalus.desktop.branding import application_icon
from daedalus.desktop.log_page import LogPage
from daedalus.desktop.pages import AccountsPage, ConnectionPage, OperationsPage, WarehousesPage
from daedalus.desktop.task_page import TasksPage

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
            elif self.action == "auth_assistance" and self.account_id:
                result = self.client.auth_assistance(self.account_id)
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


class MainWindow(FluentWindow):
    """Familiar Fluent navigation with all data fetched from Daedalus backend."""

    def __init__(self) -> None:
        super().__init__()
        self.client: DaedalusClient | None = None
        self._pending_client: DaedalusClient | None = None
        self._pending_preferences: tuple[str, str] | None = None
        self._worker: APIWorker | None = None

        self.accounts_page = AccountsPage(self)
        self.warehouses_page = WarehousesPage(self)
        self.operations_page = OperationsPage(self)
        self.tasks_page = TasksPage(self)
        self.log_page = LogPage(self)
        self.connection_page = ConnectionPage(self)

        self.addSubInterface(self.accounts_page, FIF.PEOPLE, "Accounts")
        self.addSubInterface(self.warehouses_page, FIF.SAVE, "Warehouses")
        self.addSubInterface(self.operations_page, FIF.PLAY, "Operations")
        self.addSubInterface(self.tasks_page, FIF.EDIT, "Tasks")
        self.addSubInterface(self.log_page, FIF.DOCUMENT, "Log")
        self.addSubInterface(
            self.connection_page, FIF.SETTING, "Connection", NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.setReturnButtonVisible(False)
        header = self.navigationInterface.panel.topLayout
        header.insertSpacerItem(0, QSpacerItem(40, 36, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.connection_page.connect_requested.connect(self._connect)
        self.connection_page.reconnect_requested.connect(self._reconnect)
        self.connection_page.forget_requested.connect(self._forget_connection)
        self.accounts_page.refresh_requested.connect(lambda: self._request("accounts"))
        self.accounts_page.account_change_requested.connect(
            lambda revision, rows: self._request(
                "account_config_put", task_payload={"revision": revision, "accounts": rows},
            )
        )
        self.accounts_page.assistance_check_requested.connect(
            lambda account_id: self._request("auth_assistance", account_id=account_id)
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
        self.operations_page.refresh_requested.connect(lambda: self._request("capabilities"))
        self.warehouses_page.load_requested.connect(
            lambda account_id: self._request("warehouses", account_id=account_id)
        )
        self.tasks_page.refresh_requested.connect(
            lambda account_id: self._request("task_list", account_id=account_id)
        )
        self.tasks_page.launch_requested.connect(
            lambda aid, name, config, rid: self._request(
                "task_start", account_id=aid,
                task_payload={"task": name, "config": config, "request_id": rid},
            )
        )
        self.tasks_page.stop_requested.connect(
            lambda aid, task_id: self._request(
                "task_stop", account_id=aid, task_payload={"task_id": task_id},
            )
        )
        self.tasks_page.reconcile_requested.connect(
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
        logger.info("Desktop ready; connect to a local or protected remote backend")

    def systemTitleBarRect(self, size: QSize) -> QRect:
        """Preserve the original Mac GUI's traffic-light positioning."""
        if sys.platform != "darwin":
            return super().systemTitleBarRect(size)
        return QRect(0, 0 if self.isFullScreen() else 8, 75, size.height())

    def _connect(self, url: str, token: str) -> None:
        if self._worker is not None:
            self._notice("Request in progress", "Finish the current request before connecting.")
            return
        try:
            candidate = DaedalusClient(url, token)
        except ValueError as exc:
            self._notice("Invalid connection", str(exc))
            return
        self._pending_client = candidate
        self._pending_preferences = (
            (url, token) if self.connection_page.remember_checkbox.isChecked() else None
        )
        self._launch(candidate, "connect")

    def _reconnect(self) -> None:
        """Explicitly repeat only read-only handshake, never game task dispatch."""
        if self._worker is not None:
            self._notice("Request in progress", "Finish the current request first.")
            return
        if self.client is not None:
            self._launch(self.client, "connect")
            return
        try:
            saved = saved_connection()
        except PreferenceError as exc:
            self._notice("Cannot retrieve saved connection", str(exc))
            return
        if saved is None:
            self._notice("No saved connection", "Enter a backend URL and bearer token.")
            return
        self._connect(*saved)

    def _forget_connection(self) -> None:
        try:
            forget_connection()
        except PreferenceError as exc:
            self._notice("Unable to forget saved connection", str(exc))
            return
        self.connection_page.remember_checkbox.setChecked(False)
        self._notice("Saved preference cleared", "The current in-memory connection is unchanged.")

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

    def _launch(
        self, client: DaedalusClient, action: str, *, account_id: str | None = None,
        task_payload: dict[str, object] | None = None,
    ) -> None:
        worker = APIWorker(
            client, action, account_id=account_id, task_payload=task_payload, parent=self,
        )
        self._worker = worker
        self.connection_page.connect_button.setEnabled(False)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_completed(self, action: str, payload: object) -> None:
        if action == "connect":
            assert isinstance(payload, dict)
            if self._pending_client is not None:
                if self.client is not None and self.client is not self._pending_client:
                    self.client.close()
                self.client = self._pending_client
                self._pending_client = None
            preferences = self._pending_preferences
            self._pending_preferences = None
            if preferences is not None:
                try:
                    remember_connection(*preferences)
                except PreferenceError as exc:
                    self._notice("Connection not saved", str(exc))
            health = payload.get("health") or {}
            demo = bool(health.get("synthetic_demo") is True)
            self.connection_page.set_connected(True, demo=demo)
            self.warehouses_page.set_demo(demo)
            self.setWindowTitle("Daedalus for Ikariam — SYNTHETIC DEMO" if demo else "Daedalus for Ikariam")
            self._show_accounts(payload["accounts"])
            self._show_capabilities(payload["capabilities"])
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
        elif action in {"auth_assistance", "auth_assistance_approve"}:
            assert isinstance(payload, dict)
            self.accounts_page.set_assistance(payload)
            if action == "auth_assistance_approve":
                logger.info("Operator completed manual step; worker validation still required")
                self._notice(
                    "Assistance acknowledged",
                    "The game worker still must validate authentication before resuming.",
                )
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
        elif action == "task_list":
            assert isinstance(payload, dict)
            self.tasks_page.set_tasks(payload)
            logger.info("Managed tasks refreshed")
        elif action in {"task_start", "task_stop", "task_reconcile"}:
            assert isinstance(payload, dict)
            logger.info("Task operation acknowledged: %s", action)
            self._notice("Task operation accepted", str(payload.get("status", "Complete")))
            account_id = payload.get("account_id")
            if isinstance(account_id, str):
                QTimer.singleShot(0, lambda: self._request("task_list", account_id=account_id))

    def _show_accounts(self, data: object) -> None:
        assert isinstance(data, list)
        self.accounts_page.set_accounts(data)
        self.warehouses_page.set_accounts(data)
        self.tasks_page.set_accounts(data)

    def _show_capabilities(self, data: object) -> None:
        assert isinstance(data, dict)
        self.operations_page.set_operations(data["operations"])
        self.tasks_page.set_capabilities(
            data["operations"], bool(data.get("structured_engine_dispatch", False)),
        )

    def _on_failed(self, action: str, error: str) -> None:
        if action == "connect":
            self._pending_preferences = None
            if self._pending_client is not None:
                self._pending_client.close()
                self._pending_client = None
            self.connection_page.set_connected(False)
        logger.warning("Backend %s request failed", action)
        self._notice("Backend unavailable", error)

    def _on_worker_finished(self) -> None:
        self._worker = None
        self.connection_page.connect_button.setEnabled(True)

    def _notice(self, title: str, message: str) -> None:
        InfoBar.warning(
            title, message, parent=self, position=InfoBarPosition.TOP_RIGHT
        )

    def closeEvent(self, event) -> None:
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
        if self._pending_client is not None:
            self._pending_client.close()
            self._pending_client = None
        logger.removeHandler(self._log_handler)
        super().closeEvent(event)
