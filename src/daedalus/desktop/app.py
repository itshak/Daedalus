"""Native Fluent control center. Adapted from the user's original Mac main window.

Read-only dashboards are the default. Explicitly enabled task start/stop
uses an existing authenticated IkaBot session; no Selenium login is started.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, QRect, QSize, QThread, Signal
from PySide6.QtWidgets import QPlainTextEdit, QSizePolicy, QSpacerItem
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import FluentWindow, InfoBar, InfoBarPosition, NavigationItemPosition

from daedalus.client import APIConnectionError, DaedalusClient
from daedalus.desktop.log_page import LogPage
from daedalus.desktop.pages import AccountsPage, ConnectionPage, OperationsPage, WarehousesPage
from daedalus.desktop.tasks_page import TaskControlPage

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
        parameters: dict[str, object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.client = client
        self.action = action
        self.account_id = account_id
        self.parameters = parameters or {}

    def run(self) -> None:
        try:
            if self.action == "connect":
                result = {
                    "health": self.client.health(),
                    "accounts": self.client.accounts(),
                    "capabilities": self.client.capabilities(),
                    "task_control": self.client.task_control_status(),
                }
            elif self.action == "accounts":
                result = self.client.accounts()
            elif self.action == "connected_accounts":
                result = self.client.connected_accounts()
            elif self.action == "capabilities":
                result = self.client.capabilities()
            elif self.action == "warehouses" and self.account_id:
                result = {
                    "account_id": self.account_id,
                    "cities": self.client.warehouses(self.account_id),
                }
            elif self.action == "tasks" and self.account_id:
                result = {
                    "account_id": self.account_id,
                    "tasks": self.client.tasks(self.account_id),
                }
            elif self.action == "start_task" and self.account_id:
                result = self.client.start_task(
                    self.account_id,
                    self.parameters["task"],
                    self.parameters["config"],
                )
            elif self.action == "stop_task" and self.account_id:
                result = self.client.stop_task(self.account_id, self.parameters["pid"])
            else:
                raise ValueError("Unsupported desktop API request")
            self.completed.emit(self.action, result)
        except (APIConnectionError, ValueError, TypeError) as exc:
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
        self._worker: APIWorker | None = None
        self._pending_task_refresh: str | None = None

        self.accounts_page = AccountsPage(self)
        self.warehouses_page = WarehousesPage(self)
        self.operations_page = OperationsPage(self)
        self.tasks_page = TaskControlPage(self)
        self.log_page = LogPage(self)
        self.connection_page = ConnectionPage(self)

        self.addSubInterface(self.accounts_page, FIF.PEOPLE, "Accounts")
        self.addSubInterface(self.warehouses_page, FIF.SAVE, "Warehouses")
        self.addSubInterface(self.operations_page, FIF.PLAY, "Operations")
        self.addSubInterface(self.tasks_page, FIF.ROBOT, "Tasks")
        self.addSubInterface(self.log_page, FIF.DOCUMENT, "Log")
        self.addSubInterface(
            self.connection_page, FIF.SETTING, "Connection", NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.setReturnButtonVisible(False)
        header = self.navigationInterface.panel.topLayout
        header.insertSpacerItem(0, QSpacerItem(40, 36, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.connection_page.connect_requested.connect(self._connect)
        self.accounts_page.refresh_requested.connect(lambda: self._request("accounts"))
        self.accounts_page.check_engine_requested.connect(
            lambda: self._request("connected_accounts")
        )
        self.operations_page.refresh_requested.connect(lambda: self._request("capabilities"))
        self.tasks_page.refresh_requested.connect(
            lambda account_id: self._request("tasks", account_id=account_id)
        )
        self.tasks_page.start_requested.connect(
            lambda account_id, task, config: self._request(
                "start_task", account_id=account_id,
                parameters={"task": task, "config": config},
            )
        )
        self.tasks_page.stop_requested.connect(
            lambda account_id, pid: self._request(
                "stop_task", account_id=account_id, parameters={"pid": pid},
            )
        )
        self.warehouses_page.load_requested.connect(
            lambda account_id: self._request("warehouses", account_id=account_id)
        )

        self._log_handler = QtLogHandler(self.log_page.log_view)
        self._log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logger.addHandler(self._log_handler)
        logger.setLevel(logging.INFO)

        self.setWindowTitle("Daedalus for Ikariam")
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
        self._launch(candidate, "connect")

    def _request(
        self, action: str, *, account_id: str | None = None,
        parameters: dict[str, object] | None = None,
    ) -> None:
        if self.client is None:
            self._notice("Not connected", "Connect to a Daedalus backend first.")
            return
        if self._worker is not None:
            self._notice("Request in progress", "Another backend request is still running.")
            return
        self._launch(self.client, action, account_id=account_id, parameters=parameters)

    def _launch(
        self, client: DaedalusClient, action: str, *,
        account_id: str | None = None,
        parameters: dict[str, object] | None = None,
    ) -> None:
        worker = APIWorker(
            client, action, account_id=account_id, parameters=parameters, parent=self
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
            if self.client is not None:
                self.client.close()
            self.client = self._pending_client
            self._pending_client = None
            self.connection_page.set_connected(True)
            self._show_accounts(payload["accounts"])
            self._show_capabilities(payload["capabilities"])
            self.tasks_page.set_enabled(payload["task_control"].get("enabled") is True)
            logger.info("Connected to Daedalus API")
        elif action == "accounts":
            self._show_accounts(payload)
            logger.info("Accounts refreshed")
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
        elif action == "tasks":
            assert isinstance(payload, dict)
            self.tasks_page.set_tasks(payload["tasks"])
            logger.info("Managed task status refreshed")
        elif action in {"start_task", "stop_task"}:
            assert isinstance(payload, dict)
            self._pending_task_refresh = self.tasks_page.selected_account_id()
            logger.info("Managed task action acknowledged: %s", action)

    def _show_accounts(self, data: object) -> None:
        assert isinstance(data, list)
        self.accounts_page.set_accounts(data)
        self.warehouses_page.set_accounts(data)
        self.tasks_page.set_accounts(data)

    def _show_capabilities(self, data: object) -> None:
        assert isinstance(data, dict)
        self.operations_page.set_operations(data["operations"])
        self.tasks_page.set_operations(data["operations"])

    def _on_failed(self, action: str, error: str) -> None:
        if action == "connect" and self._pending_client is not None:
            self._pending_client.close()
            self._pending_client = None
            self.connection_page.set_connected(self.client is not None)
        logger.warning("Backend %s request failed", action)
        self._notice("Backend unavailable", error)

    def _on_worker_finished(self) -> None:
        self._worker = None
        self.connection_page.connect_button.setEnabled(True)
        account_id = self._pending_task_refresh
        self._pending_task_refresh = None
        if account_id is not None:
            self._request("tasks", account_id=account_id)

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
