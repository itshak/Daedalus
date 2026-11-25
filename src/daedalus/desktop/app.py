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
from daedalus.desktop.military_page import MilitaryPage
from daedalus.desktop.pages import AccountsPage, ConnectionPage, WarehousesPage
from daedalus.desktop.selenium_auth import GameforgeCredentials
from daedalus.desktop.selenium_credentials import (
    LoginCredentialError,
    get_saved_login,
    legacy_warehouse_login,
)
from daedalus.desktop.selenium_credentials_dialog import SeleniumCredentialsDialog
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
from daedalus.desktop.task_presentation import BATCH_TASKS
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


def _safe_api_failure(reason: str) -> str:
    """Allow reviewed client errors in diagnostics, never arbitrary API bodies."""
    permitted = {
        "Cannot connect to Daedalus backend",
        "Backend task request was rejected",
        "Backend returned invalid task JSON",
        "Backend returned invalid task receipt",
        "Browser login did not receive a verified server receipt",
        "Backend native browser challenge is malformed",
        "A Gameforge email is required for first-time account binding",
        "This worker is busy or has an uncertain task; reconcile it before login",
        "Running or uncertain tasks must be reconciled before login",
        "This backend has not enabled native browser login",
        "Server did not verify the exact game account; login was not accepted",
        "Gameforge email differs from the existing account binding",
        "Another worker owns this game account",
        "Browser handoff is expired or already consumed",
        "Game world is unreachable from the Daedalus server; saved sessions will retry when connectivity recovers",
    }
    return reason if reason in permitted else "request failed (unreviewed detail suppressed)"


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
            elif self.action == "extension_settings" and self.account_id:
                result = self.client.extension_settings(self.account_id, self.task_payload)
            elif self.action == "release_status":
                result = self.client.release_status()
            elif self.action == "accounts":
                result = self.client.accounts()
            elif self.action == "notification_settings" and self.account_id and self.task_payload:
                provider = self.task_payload["provider"]
                settings = self.task_payload.pop("settings")
                try:
                    result = self.client.configure_notification(self.account_id, provider, settings)
                finally:
                    settings.clear()
            elif self.action == "administrative_status" and self.account_id:
                result = self.client.administrative_status(self.account_id)
            elif self.action == "recovery_index":
                result = self.client.recovery_index()
            elif self.action == "recovery_import" and self.account_id:
                result = self.client.recovery_import(self.account_id)
            elif (self.action == "recovery_policy" and self.account_id
                  and self.task_payload is not None):
                result = self.client.recovery_policy(
                    self.account_id,
                    enabled=self.task_payload["enabled"],
                    expected_revision=self.task_payload["expected_revision"],
                )
            elif self.action == "recovery_bulk" and self.task_payload:
                result = self.client.recovery_bulk(
                    self.task_payload["account_ids"],
                    enabled=self.task_payload["enabled"],
                )
            elif (self.action == "recovery_pause" and self.account_id
                  and self.task_payload is not None):
                result = self.client.recovery_pause(
                    self.account_id, self.task_payload.get("seconds"),
                )
            elif self.action == "recovery_resume" and self.account_id:
                result = self.client.recovery_resume(self.account_id)
            elif self.action == "recovery_jobs" and self.account_id:
                result = self.client.recovery_jobs(self.account_id)
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
                result = _known_ikabot_workers(self.client)
            elif self.action == "capabilities":
                result = self.client.capabilities()
            elif self.action == "server_activity" and self.account_id and self.task_payload:
                result = self.client.activity(self.account_id, before=self.task_payload["before"],
                                              status=self.task_payload["status"])
            elif self.action == "task_shipment_preview" and self.account_id and self.task_payload:
                result = self.client.shipment_preview(self.account_id, self.task_payload["draft"])
            elif self.action == "task_island_destinations" and self.account_id and self.task_payload:
                result = self.client.island_destinations(self.account_id, self.task_payload["x"], self.task_payload["y"])
            elif self.action == "task_cities" and self.account_id:
                result = {
                    "account_id": self.account_id,
                    "cities": self.client.cities(self.account_id),
                }
            elif self.action == "task_vacation_preview" and self.account_id and self.task_payload:
                result = self.client.vacation_preview(self.account_id, self.task_payload["city_id"])
            elif self.action == "task_attack_inventory" and self.account_id and self.task_payload:
                result = self.client.attack_inventory(self.account_id, self.task_payload["city_id"])
            elif self.action == "task_attack_preview" and self.account_id and self.task_payload:
                draft = self.task_payload["draft"]
                result = self.client.attack_preview(self.account_id, draft["city_id"],
                                                    {k: v for k, v in draft.items() if k != "city_id"})
            elif self.action == "task_grind_preview" and self.account_id and self.task_payload:
                draft = self.task_payload["draft"]
                result = self.client.grind_preview(self.account_id, draft["city_id"],
                                                   {k: v for k, v in draft.items() if k != "city_id"})
            elif self.action == "task_training_preview" and self.account_id and self.task_payload:
                result = self.client.training_preview(self.account_id, self.task_payload["draft"])
            elif self.action == "task_station_preview" and self.account_id and self.task_payload:
                draft = self.task_payload["draft"]
                result = self.client.station_preview(self.account_id, draft["city_id"],
                                                     {k: v for k, v in draft.items() if k != "city_id"})
            elif self.action == "task_build_options" and self.account_id and self.task_payload:
                result = self.client.build_options(self.account_id, self.task_payload["city_id"])
            elif self.action == "task_build_preview" and self.account_id and self.task_payload:
                draft = self.task_payload["draft"]
                result = self.client.build_preview(self.account_id, draft["city_id"],
                                                   {k: v for k, v in draft.items() if k != "city_id"})
            elif self.action == "task_layout_preview" and self.account_id and self.task_payload:
                draft = self.task_payload["draft"]
                result = self.client.layout_preview(self.account_id, draft["city_id"], draft["template_city_id"])
            elif self.action == "task_worker_preview" and self.account_id and self.task_payload:
                draft = self.task_payload["draft"]
                result = self.client.worker_preview(
                    self.account_id, draft["city_id"], self.task_payload["task"],
                    {k: v for k, v in draft.items() if k != "city_id"},
                )
            elif self.action == "task_donation_preview" and self.account_id and self.task_payload:
                draft = self.task_payload["draft"]
                result = self.client.donation_preview(
                    self.account_id, draft["city_id"], draft["project"], draft["amount"])
            elif self.action == "task_construction_preview" and self.account_id and self.task_payload:
                city_id = self.task_payload.get("city_id")
                upgrades = self.task_payload.get("upgrades")
                if type(city_id) is not int or not isinstance(upgrades, list):
                    raise ValueError("Invalid construction preview")
                supply = self.task_payload.get("supply")
                result = self.client.construction_preview(self.account_id, city_id, upgrades, supply=supply) if supply is not None else self.client.construction_preview(self.account_id, city_id, upgrades)
            elif self.action == "military_overview" and self.account_id:
                result = self.client.military_overview(self.account_id)
            elif self.action == "military_movements" and self.account_id:
                result = self.client.ship_movements(self.account_id)
            elif self.action == "task_piracy" and self.account_id:
                result = self.client.pirate_fortresses(self.account_id)
            elif self.action == "task_shrine" and self.account_id:
                result = self.client.shrine_status(self.account_id)
            elif self.action == "task_miracles" and self.account_id:
                result = self.client.miracles(self.account_id)
            elif self.action == "task_taverns" and self.account_id:
                result = self.client.taverns(self.account_id)
            elif self.action == "task_academies" and self.account_id:
                result = self.client.academies(self.account_id)
            elif self.action == "task_market" and self.account_id and self.task_payload:
                city_id = self.task_payload.get("city_id")
                resource_type = self.task_payload.get("resource_type")
                side = self.task_payload.get("side")
                if (type(city_id) is not int or type(resource_type) is not int
                        or not isinstance(side, str)):
                    raise ValueError("Invalid market quote scope")
                result = self.client.market_quotes(
                    self.account_id, city_id, resource_type, side,
                )
            elif self.action == "task_trainables" and self.account_id and self.task_payload:
                city_id = self.task_payload.get("city_id")
                train_troops = self.task_payload.get("train_troops")
                if type(city_id) is not int or type(train_troops) is not bool:
                    raise ValueError("Invalid army training city or mode")
                result = self.client.trainable_units(
                    self.account_id, city_id, train_troops=train_troops,
                )
            elif self.action == "task_workshop" and self.account_id and self.task_payload:
                city_id = self.task_payload.get("city_id")
                if type(city_id) is not int:
                    raise ValueError("Invalid workshop city")
                result = self.client.workshop_upgrades(self.account_id, city_id)
            elif self.action == "task_buildings" and self.account_id and self.task_payload:
                city_id = self.task_payload.get("city_id")
                if type(city_id) is not int:
                    raise ValueError("Invalid selected construction city")
                result = {
                    "account_id": self.account_id, "city_id": city_id,
                    "buildings": self.client.buildings(self.account_id, city_id),
                }
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
            elif self.action == "reviewed_batch" and self.task_payload is not None:
                from daedalus.reviewed_batch import dispatch_reviewed_batch
                result = dispatch_reviewed_batch(self.client, self.task_payload["entries"])
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
                    or task not in BATCH_TASKS
                ):
                    raise ValueError("Select authorized accounts and an account-independent task")
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
        self._pending_task_cities: str | None = None
        self._pending_military_reads: list[tuple[str, str]] = []
        self._pending_task_buildings: tuple[str, int] | None = None
        self._pending_workshop: tuple[str, int] | None = None
        self._pending_trainables: tuple[str, int, bool] | None = None
        self._pending_market: tuple[str, int, int, str] | None = None
        self._pending_academies: str | None = None
        self._pending_taverns: str | None = None
        self._pending_miracles: str | None = None
        self._pending_shrine: str | None = None
        self._pending_piracy: str | None = None
        self._pending_construction_preview: tuple[str, int, list[dict[str, int]], dict[str, object] | None] | None = None
        self._pending_batch_status: list[str] | None = None
        self._pending_native_login_challenge: dict[str, object] | None = None
        self._selenium_worker: SeleniumLoginWorker | None = None
        self._automatic_login_active = False
        self._automatic_login_cancelled = False
        self._automatic_login_queue: list[str] = []
        self._automatic_login_current: str | None = None
        self._automatic_login_credentials: GameforgeCredentials | None = None
        self._automatic_login_email: str | None = None
        self._automatic_login_save_credentials = False
        self._automatic_login_sealed_vault: dict[str, object] | None = None
        self._automatic_login_needs_credentials = False
        self._automatic_login_cancel_sent = False
        self._pending_selenium_cancel: dict[str, object] | None = None
        self._closing_requested = False
        self._automatic_login_challenge: dict[str, object] | None = None
        self._automatic_login_pending_advance = False
        self._automatic_login_pending_visible_retry = False
        self._automatic_login_force_visible = False
        self._automatic_login_successes = 0
        self._automatic_login_bound_sessions = 0
        self._automatic_login_worker_recovered = 0
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

        # Hard upper bound even if ChromeDriver or Keychain never responds.
        self._selenium_watchdog = QTimer(self)
        self._selenium_watchdog.setSingleShot(True)
        self._selenium_watchdog.timeout.connect(self._selenium_timeout)

        self.home_page = HomePage(self)
        self.accounts_page = AccountsPage(self)
        self.warehouses_page = WarehousesPage(self)
        self.military_page = MilitaryPage(self)
        # One authoritative automation workspace and one catalog instance.
        # Preserve the public operations_page alias for legacy navigation
        # callers without constructing a disconnected second catalog.
        self.tasks_page = TasksPage(self)
        self.operations_page = self.tasks_page.catalog_panel
        self._task_views = (self.tasks_page,)
        self.log_page = LogPage(self)
        self.log_page.server_activity_requested.connect(
            lambda aid, before, status: self._request_server_activity(aid, before, status)
        )
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
        self.addSubInterface(self.military_page, NAV_ICONS["military"], "Military")
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
        self.appearance_page.extension_settings_requested.connect(
            lambda aid, draft: self._request("extension_settings", account_id=aid, task_payload=draft))
        self.appearance_page.release_status_requested.connect(lambda: self._request("release_status"))
        self.appearance_page.notification_settings_requested.connect(
            lambda aid, provider, settings: self._request("notification_settings", account_id=aid,
                task_payload={"provider": provider, "settings": settings})
        )
        self.appearance_page.administrative_status_requested.connect(
            lambda aid: self._request("administrative_status", account_id=aid)
        )
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
        self.accounts_page.recovery_refresh_requested.connect(
            lambda: self._request("recovery_index")
        )
        self.accounts_page.recovery_import_requested.connect(
            lambda aid: self._request("recovery_import", account_id=aid)
        )
        self.accounts_page.recovery_policy_requested.connect(
            lambda aid, enabled, rev: self._request(
                "recovery_policy", account_id=aid,
                task_payload={"enabled": enabled, "expected_revision": rev},
            )
        )
        self.accounts_page.recovery_bulk_requested.connect(
            lambda ids, enabled: self._request(
                "recovery_bulk", task_payload={"account_ids": ids, "enabled": enabled},
            )
        )
        self.accounts_page.recovery_pause_requested.connect(
            lambda aid, seconds: self._request(
                "recovery_pause", account_id=aid, task_payload={"seconds": seconds},
            )
        )
        self.accounts_page.recovery_resume_requested.connect(
            lambda aid: self._request("recovery_resume", account_id=aid)
        )
        self.accounts_page.recovery_jobs_requested.connect(
            lambda aid: self._request("recovery_jobs", account_id=aid)
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
        self.military_page.refresh_requested.connect(self._queue_military_reads)
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
            view.cities_requested.connect(self._queue_task_cities)
            view.shipment_preview_requested.connect(
                lambda aid, draft, nonce: self._request("task_shipment_preview", account_id=aid,
                    task_payload={"draft": draft, "nonce": nonce})
            )
            view.island_destinations_requested.connect(
                lambda aid, x, y, nonce: self._request("task_island_destinations", account_id=aid,
                    task_payload={"x": x, "y": y, "nonce": nonce})
            )
            view.buildings_requested.connect(self._queue_task_buildings)
            view.workshop_requested.connect(self._queue_workshop)
            view.trainable_units_requested.connect(self._queue_trainables)
            view.market_quotes_requested.connect(self._queue_market)
            view.academies_requested.connect(self._queue_academies)
            view.taverns_requested.connect(self._queue_taverns)
            view.miracles_requested.connect(self._queue_miracles)
            view.shrine_requested.connect(self._queue_shrine)
            view.pirate_fortresses_requested.connect(self._queue_piracy)
            view.construction_preview_requested.connect(self._queue_construction_preview)
            view.construction_supply_preview_requested.connect(self._queue_construction_preview)
            view.vacation_preview_requested.connect(
                lambda aid, city, nonce: self._request("task_vacation_preview", account_id=aid,
                    task_payload={"city_id": city, "nonce": nonce})
            )
            view.attack_inventory_requested.connect(
                lambda aid, city, nonce: self._request("task_attack_inventory", account_id=aid,
                    task_payload={"city_id": city, "nonce": nonce})
            )
            view.attack_preview_requested.connect(
                lambda aid, draft, nonce: self._request("task_attack_preview", account_id=aid,
                    task_payload={"draft": draft, "nonce": nonce})
            )
            view.grind_preview_requested.connect(
                lambda aid, draft, nonce: self._request("task_grind_preview", account_id=aid,
                    task_payload={"draft": draft, "nonce": nonce})
            )
            view.training_preview_requested.connect(
                lambda aid, draft, nonce: self._request("task_training_preview", account_id=aid,
                    task_payload={"draft": draft, "nonce": nonce})
            )
            view.station_preview_requested.connect(
                lambda aid, draft, nonce: self._request("task_station_preview", account_id=aid,
                    task_payload={"draft": draft, "nonce": nonce})
            )
            view.build_options_requested.connect(
                lambda aid, city, nonce: self._request("task_build_options", account_id=aid,
                    task_payload={"city_id": city, "nonce": nonce})
            )
            view.build_preview_requested.connect(
                lambda aid, draft, nonce: self._request("task_build_preview", account_id=aid,
                    task_payload={"draft": draft, "nonce": nonce})
            )
            view.layout_preview_requested.connect(
                lambda aid, draft, nonce: self._request(
                    "task_layout_preview", account_id=aid, task_payload={"draft": draft, "nonce": nonce},
                )
            )
            view.worker_preview_requested.connect(
                lambda aid, task, draft, nonce: self._request(
                    "task_worker_preview", account_id=aid,
                    task_payload={"task": task, "draft": draft, "nonce": nonce},
                )
            )
            view.donation_preview_requested.connect(
                lambda aid, draft, nonce: self._request(
                    "task_donation_preview", account_id=aid,
                    task_payload={"draft": draft, "nonce": nonce},
                )
            )
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
            view.reviewed_batch_requested.connect(
                lambda entries: self._request("reviewed_batch", task_payload={"entries": entries})
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
        self._quit_shortcut = QShortcut(QKeySequence.StandardKey.Quit, self)
        self._quit_shortcut.activated.connect(self.close)
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
        elif current is self.military_page:
            self.military_page.refresh()
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
        self.military_page.select_account(account_id)
        for view in self._task_views:
            view.select_account(account_id)

    def _view_home_warehouses(self, account_id: str) -> None:
        self._select_working_account(account_id)
        self.switchTo(self.warehouses_page)
        self._request_warehouse_scope("warehouses", [account_id])

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
        self._automatic_login_bound_sessions = 0
        self._automatic_login_worker_recovered = 0
        self._automatic_login_failures = 0
        self._automatic_login_pending_visible_retry = False
        self._automatic_login_force_visible = False
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
        self.log_page.add_login_stage("sign_in_requested")
        logger.info("Automatic sign-in queued for %d accounts", len(self._automatic_login_queue))
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
            # Never call macOS Keychain on the GUI event loop. The isolated
            # helper resolves saved logins and launches Chrome in a killable
            # child process, after a one-time backend handoff is prepared.
            self._automatic_login_current = aid
            # Do not emit account IDs in activity/technical logs.
            logger.info("Preparing next isolated account sign-in")
            self.log_page.add_login_stage("backend_handoff_requested")
            self._automatic_login_credentials = None
            self._automatic_login_email = None
            self._automatic_login_save_credentials = False
            self._automatic_login_sealed_vault = None
            self._automatic_login_cancel_sent = False
            self._automatic_login_pending_visible_retry = False
            self._automatic_login_force_visible = False
            self.accounts_page.set_automatic_login_busy(
                True, f"Preparing isolated sign-in for {record.get('label') or record.get('player')}…",
            )
            self._request("native_login_start", account_id=aid)
            return
        self._finish_automatic_logins()

    def _finish_automatic_logins(self) -> None:
        failures = self._automatic_login_failures
        cancelled = self._automatic_login_cancelled
        self._automatic_login_active = False
        self._automatic_login_cancelled = False
        self._selenium_watchdog.stop()
        self._automatic_login_queue.clear()
        self._automatic_login_current = None
        self._automatic_login_force_visible = False
        self._automatic_login_pending_visible_retry = False
        self._automatic_login_credentials = None
        self._automatic_login_email = None
        self._automatic_login_sealed_vault = None
        self._automatic_login_needs_credentials = False
        self._automatic_login_challenge = None
        self.log_page.add_login_stage("sign_in_cancelled" if cancelled else "sign_in_finished")
        logger.info(
            "Automatic sign-in finished: %d verified cookies saved, %d workers recovered, %d failed",
            self._automatic_login_bound_sessions, self._automatic_login_worker_recovered,
            failures,
        )
        self.accounts_page.set_automatic_login_busy(
            False,
            f"Automatic sign-in {'cancelled' if cancelled else 'finished'}: "
            f"{self._automatic_login_bound_sessions} verified session(s) saved, "
            f"{self._automatic_login_worker_recovered} worker(s) connected, "
            f"{failures} unavailable. Only verified, attached workers can "
            "supply live warehouse data.",
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
        logger.info("Cancelling isolated Selenium login")
        self._automatic_login_queue.clear()
        self._automatic_login_report = None
        self.accounts_page.set_automatic_login_busy(
            True, "Cancelling Selenium login and discarding any unverified session…"
        )
        if self._selenium_worker is not None:
            self._selenium_worker.cancel()
        elif self._automatic_login_challenge is not None:
            self._cancel_selenium_handoff(self._automatic_login_challenge)
        elif self._worker is None:
            self._finish_automatic_logins()

    def _selenium_timeout(self) -> None:
        if self._selenium_worker is not None and self._selenium_worker.isRunning():
            logger.warning("Isolated Selenium login exceeded the watchdog deadline")
            self.log_page.add_login_stage("handoff_failed")
            self._notice(
                "Automatic sign-in timed out",
                "The isolated Chrome process exceeded its time limit and was terminated.",
            )
            self._cancel_automatic_logins()

    def _launch_headless_selenium(self, challenge: dict[str, object]) -> None:
        aid = self._automatic_login_current
        record = self.accounts_page.account_record(aid) if aid else None
        if (self._automatic_login_cancelled or self._closing_requested
                or not self._automatic_login_active
                or record is None or challenge.get("account_id") != aid
                or record.get("world") != challenge.get("world") or self._selenium_worker is not None):
            self._cancel_selenium_handoff(challenge)
            return
        self._automatic_login_challenge = challenge
        worker = SeleniumLoginWorker(
            str(record["world"]), self._automatic_login_credentials, self,
            origin=str(self._active_backend_url), account_id=aid,
            record=record, sealed_vault=self._server_login_vaults.get(aid),
            remember=self._automatic_login_save_credentials,
            visible_only=self._automatic_login_force_visible,
        )
        self._selenium_worker = worker
        logger.info(
            "Starting isolated Selenium helper in %s mode",
            "visible" if self._automatic_login_force_visible else "headless-first",
        )
        worker.stage_changed.connect(self._selenium_progress)
        worker.credentials_resolved.connect(self._selenium_credentials_resolved)
        worker.credentials_required.connect(self._selenium_credentials_required)
        worker.vault_ready.connect(self._selenium_vault_ready)
        worker.cookie_ready.connect(self._selenium_success)
        worker.login_failed.connect(self._selenium_failure)
        worker.finished.connect(self._selenium_finished)
        self._selenium_watchdog.start(330_000)
        worker.start()
        # The helper holds its own copy while Chrome runs. A manually entered
        # password must not linger in MainWindow state after launch.
        self._automatic_login_credentials = None

    def _selenium_credentials_resolved(self, email: str, remember: bool) -> None:
        if not self._automatic_login_cancelled and not self._closing_requested:
            self._automatic_login_email = email
            self._automatic_login_save_credentials = remember
            # Display-only metadata: no Keychain call on the Qt event loop.
            for account in self.accounts_page._accounts:
                if account.get("id") == self._automatic_login_current:
                    account["email"] = email
                    break

    def _selenium_credentials_required(self) -> None:
        self._automatic_login_needs_credentials = True
        self.log_page.add_login_stage("credentials_required")
        logger.warning("Saved Gameforge login unavailable; prompting for credentials")

    def _selenium_vault_ready(self, vault: dict[str, object]) -> None:
        if not self._automatic_login_cancelled:
            self._automatic_login_sealed_vault = vault

    def _prompt_automatic_login_credentials(self) -> None:
        if self._closing_requested or self._automatic_login_cancelled:
            return
        aid = self._automatic_login_current
        record = self.accounts_page.account_record(aid) if aid else None
        challenge = self._automatic_login_challenge
        if record is None or challenge is None:
            return
        dialog = SeleniumCredentialsDialog(
            player=str(record["player"]), world=str(record["world"]),
            email=str(record.get("email") or ""), parent=self,
        )
        try:
            if dialog.exec() != QDialog.Accepted:
                self._cancel_selenium_handoff(challenge)
                return
            self._automatic_login_credentials = dialog.credentials()
            self._automatic_login_save_credentials = dialog.remember.isChecked()
        finally:
            dialog.discard()
            dialog.deleteLater()
        self._launch_headless_selenium(challenge)

    def _selenium_progress(self, stage: str) -> None:
        descriptions = {
            "helper_starting": "Starting the background login helper…",
            "helper_running": "Login helper running; checking account credentials…",
            "starting_headless_browser": "Starting Chrome in the background…",
            "checking_saved_session": "Checking for a reusable world session…",
            "saved_session_expired": "Saved world session unusable; looking for login credentials…",
            "saved_session_restored": "World session restored; verifying with backend…",
            "opening_lobby": "Opening the Gameforge lobby…",
            "lobby_loaded": "Gameforge lobby opened…",
            "waiting_for_login_form": "Waiting for the Gameforge sign-in form…",
            "login_submitted": "Login submitted. Waiting for Gameforge…",
            "sign_in_tab_selected": "Sign-in tab identified; entering credentials securely…",
            "sign_in_tab_not_found": "Cannot identify the sign-in form. Visible Chrome recovery required…",
            "lobby_session_active": "Lobby session exists; opening the selected world…",
            "waiting_for_world": "Waiting for the exact selected game world…",
            "play_clicked": "Gameforge Play clicked; opening the world…",
            "world_ready": "Game world opened. Checking session security…",
            "world_cookie_ready": "Secure world session found. Waiting for server verification…",
            "headless_login_failed": "Background login failed; switching to visible Chrome…",
            "opening_visible_recovery": (
                "Opening Chrome so you can complete or correct Gameforge login…"
            ),
            "opening_visible_browser": "Visible Chrome starting. Complete login if needed…",
            "manual_login_required": (
                "Complete the Gameforge login in the visible Chrome window."
            ),
            "login_form_timeout": "Gameforge login form timed out; trying visible recovery…",
            "browser_navigation_error": "Gameforge navigation failed; trying visible recovery…",
            "visible_login_failed": "Visible browser recovery did not complete.",
            "helper_protocol_error": "Login helper returned an invalid response.",
            "helper_exited_early": "Login helper exited before authentication completed.",
            "helper_start_failed": "Login helper could not start.",
            "headless_login": "Logging in automatically in headless Chrome…",
            "resolving_saved_login": "Looking for saved credentials in macOS Keychain…",
            "launching_chrome": "Starting isolated headless Chrome browser…",
            "opening_visible_captcha": (
                "A CAPTCHA was detected; opening visible Chrome for manual completion…"
            ),
            "captcha_required": (
                "CAPTCHA needs you: complete the challenge in visible Chrome. "
                "Selenium continues automatically afterward."
            ),
            "captcha_resolved": "CAPTCHA solved. Selenium is opening the selected game world…",
            "visible_captcha_login": "Continuing in visible Chrome…",
            "keychain_unavailable": "Saved login unavailable. Enter credentials manually if prompted.",
            "keychain_save_failed": "Chrome signed in; encrypted login backup is unavailable until Keychain unlocks.",
            "server_rejected_headless": "Server rejected the headless session. Retrying with visible Chrome…",
        }
        message = descriptions.get(stage)
        if message:
            # Fixed stage codes only: never forward raw browser exceptions,
            # credentials, account IDs or URLs into the GUI log stream.
            logger.info("Gameforge sign-in stage: %s", stage)
            self.log_page.add_login_stage(stage)
            self.accounts_page.set_automatic_login_busy(True, message)
        if stage == "captcha_required":
            self._notice("Gameforge CAPTCHA", "Complete it in the visible Chrome window; no password entry needed.")

    def _selenium_success(self, cookie: str) -> None:
        challenge = self._automatic_login_challenge
        aid = self._automatic_login_current
        record = self.accounts_page.account_record(aid) if aid else None
        if not challenge or not record:
            return
        if not self._automatic_login_email:
            self._selenium_failure("No verified login identity returned by isolated Chrome")
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
                email=self._automatic_login_email,
            )
        except (NativeHandoffUnavailable, ValueError):
            self._notice("Gameforge session invalid", "World cookie was rejected before transmission.")
            self._cancel_selenium_handoff(challenge)
            return
        self.log_page.add_login_stage("handoff_verifying")
        logger.info("Gameforge world session obtained; verifying player on server")
        self.accounts_page.set_automatic_login_busy(
            True, "Browser sign-in complete. Waiting for independent server player verification…"
        )
        payload: dict[str, object] = {
            "ticket_id": challenge["ticket_id"], "envelope": envelope,
        }
        if self._automatic_login_sealed_vault is not None:
            # The isolated child already sealed this using Mac Keychain.
            # Never invoke Keychain synchronously in a GUI callback.
            payload["vault"] = self._automatic_login_sealed_vault
        self._request("native_login_complete", account_id=aid, task_payload=payload)

    def _selenium_failure(self, reason: str) -> None:
        self.log_page.add_login_stage("handoff_failed")
        logger.warning("Isolated Gameforge sign-in failed: %s", reason)
        self._notice("Automatic sign-in unsuccessful", reason)
        if self._automatic_login_challenge is not None:
            self._cancel_selenium_handoff(self._automatic_login_challenge)

    def _retry_rejected_handoff_visibly(self) -> bool:
        """Wait until BOTH the API and Selenium workers stop before retry."""
        if not self._automatic_login_pending_visible_retry:
            return False
        if (self._worker is not None or self._selenium_worker is not None
                or self._closing_requested):
            return True
        if (not self._automatic_login_active or self._automatic_login_cancelled
                or self._automatic_login_current is None or self.client is None):
            self._automatic_login_pending_visible_retry = False
            return False
        self._automatic_login_pending_visible_retry = False
        self._automatic_login_challenge = None
        self._request("native_login_start", account_id=self._automatic_login_current)
        return True

    def _selenium_finished(self) -> None:
        self._selenium_watchdog.stop()
        worker = self._selenium_worker
        self._selenium_worker = None
        if worker is not None:
            worker.deleteLater()
        if self._closing_requested:
            return
        if self._automatic_login_cancelled and self._automatic_login_challenge:
            self._cancel_selenium_handoff(self._automatic_login_challenge)
            return
        if self._automatic_login_needs_credentials:
            self._automatic_login_needs_credentials = False
            QTimer.singleShot(0, self._prompt_automatic_login_credentials)
            return
        if self._retry_rejected_handoff_visibly():
            return
        # The Selenium finished signal and HTTP cancellation response can
        # arrive in either order. Advance exactly once after BOTH are idle.
        if self._worker is None and self._automatic_login_pending_advance:
            self._automatic_login_pending_advance = False
            QTimer.singleShot(0, self._advance_automatic_login)

    def _cancel_selenium_handoff(self, challenge: dict[str, object]) -> None:
        if self._automatic_login_cancel_sent:
            return
        aid, ticket = challenge.get("account_id"), challenge.get("ticket_id")
        if isinstance(aid, str) and isinstance(ticket, str):
            if self._worker is not None:
                # The API worker owns the sole request slot. Flush the pending
                # cancel on its finished signal rather than dropping it.
                self._pending_selenium_cancel = dict(challenge)
                return
            self._automatic_login_cancel_sent = True
            self._request("native_login_cancel", account_id=aid,
                          task_payload={"ticket_id": ticket})
        else:
            self._automatic_login_failures += 1
            self._reset_automatic_attempt()
            self._automatic_login_pending_advance = True

    def _reset_automatic_attempt(self) -> None:
        self._automatic_login_current = None
        self._automatic_login_credentials = None
        self._automatic_login_email = None
        self._automatic_login_challenge = None
        self._automatic_login_sealed_vault = None
        self._automatic_login_save_credentials = False
        self._automatic_login_cancel_sent = False
        self._automatic_login_force_visible = False
        self._automatic_login_pending_visible_retry = False
        self._pending_selenium_cancel = None

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

    def _request_server_activity(self, account_id, before, status):
        if self.client is None or self._worker is not None:
            self.log_page.set_server_activity_unavailable(account_id, before, status)
            return
        self._request("server_activity", account_id=account_id,
                      task_payload={"before": before, "status": status})

    def _request(
        self, action: str, *, account_id: str | None = None,
        task_payload: dict[str, object] | None = None,
    ) -> None:
        if self.client is None or self._worker is not None:
            if action == "notification_settings" and task_payload is not None:
                task_payload.get("settings", {}).clear()
                self.appearance_page.set_notification_unavailable(account_id)
            if action == "reviewed_batch":
                for view in self._task_views:
                    view.set_batch_launch_result({"account_ids": [], "submitted": [],
                                                  "blocked": [{"reason": "unavailable"}]})
            if self.client is None:
                self._notice("Not connected", "Connect to a Daedalus backend first.")
            else:
                self._notice("Request in progress", "Another backend request is still running.")
            return
        self._launch(self.client, action, account_id=account_id, task_payload=task_payload)

    def _queue_military_reads(self, account_ids: list[str], kind: str) -> None:
        """One bounded read at a time, even for All accounts."""
        if kind not in {"military_overview", "military_movements"}:
            return
        if self.client is None:
            return
        valid = set(self.military_page.selected_account_ids())
        self._pending_military_reads = [
            (aid, kind) for aid in dict.fromkeys(account_ids[:100])
            if aid in valid
        ]
        self._run_next_military_read()

    def _run_next_military_read(self) -> None:
        if self.client is None or self._worker is not None:
            return
        valid = set(self.military_page.selected_account_ids())
        while self._pending_military_reads:
            aid, kind = self._pending_military_reads.pop(0)
            if aid in valid:
                self._launch(self.client, kind, account_id=aid)
                return

    def _queue_task_cities(self, account_id: str) -> None:
        """Fetch account-bound city choices off-thread, after an active request ends."""
        if self.client is None or self.tasks_page.selected_account_id() != account_id:
            return
        self._pending_task_cities = account_id
        self._run_next_task_cities()

    def _run_next_task_cities(self) -> None:
        if self.client is None or self._worker is not None:
            return
        account_id = self._pending_task_cities
        self._pending_task_cities = None
        if account_id and self.tasks_page.selected_account_id() == account_id:
            self._launch(self.client, "task_cities", account_id=account_id)

    def _queue_task_buildings(self, account_id: str, city_id: int) -> None:
        """Only load current selected city's read-only inventory."""
        if self.client is None or self.tasks_page.selected_account_id() != account_id:
            return
        self._pending_task_buildings = (account_id, city_id)
        self._run_next_task_buildings()

    def _run_next_task_buildings(self) -> None:
        if self.client is None or self._worker is not None:
            return
        scope = self._pending_task_buildings
        self._pending_task_buildings = None
        if scope and self.tasks_page.selected_account_id() == scope[0]:
            self._launch(self.client, "task_buildings", account_id=scope[0],
                         task_payload={"city_id": scope[1]})

    def _queue_construction_preview(
        self, account_id: str, city_id: int, upgrades: list[dict[str, int]],
        supply: dict[str, object] | None = None,
    ) -> None:
        """Prepare a read-only queue for the currently selected account and city."""
        if (self.client is None or self.tasks_page.selected_account_id() != account_id
                or self.tasks_page.selected_task_name() != "constructionList"):
            return
        self._pending_construction_preview = (account_id, city_id, upgrades, supply)
        self._run_next_construction_preview()

    def _run_next_construction_preview(self) -> None:
        if self.client is None or self._worker is not None:
            return
        scope = self._pending_construction_preview
        self._pending_construction_preview = None
        if (scope is not None and self.tasks_page.selected_account_id() == scope[0]
                and self.tasks_page.selected_task_name() == "constructionList"):
            self._launch(
                self.client, "task_construction_preview", account_id=scope[0],
                task_payload={"city_id": scope[1], "upgrades": scope[2], "supply": scope[3]},
            )

    def _queue_workshop(self, account_id: str, city_id: int) -> None:
        """Read eligible upgrade rows for the current account-owned city."""
        if (self.client is None or self.tasks_page.selected_account_id() != account_id
                or self.tasks_page.selected_task_name() != "UpgradeUnits"):
            return
        self._pending_workshop = (account_id, city_id)
        self._run_next_workshop()

    def _run_next_workshop(self) -> None:
        if self.client is None or self._worker is not None:
            return
        scope = self._pending_workshop
        self._pending_workshop = None
        if (scope is not None and self.tasks_page.selected_account_id() == scope[0]
                and self.tasks_page.selected_task_name() == "UpgradeUnits"):
            self._launch(
                self.client, "task_workshop", account_id=scope[0],
                task_payload={"city_id": scope[1]},
            )

    def _queue_trainables(
        self, account_id: str, city_id: int, train_troops: bool,
    ) -> None:
        """Read real, scoped barracks/shipyard catalog for the selected city."""
        if (self.client is None or self.tasks_page.selected_account_id() != account_id
                or self.tasks_page.selected_task_name() != "trainArmy"):
            return
        self._pending_trainables = (account_id, city_id, train_troops)
        self._run_next_trainables()

    def _run_next_trainables(self) -> None:
        if self.client is None or self._worker is not None:
            return
        scope = self._pending_trainables
        self._pending_trainables = None
        if (scope is not None and self.tasks_page.selected_account_id() == scope[0]
                and self.tasks_page.selected_task_name() == "trainArmy"):
            self._launch(
                self.client, "task_trainables", account_id=scope[0],
                task_payload={"city_id": scope[1], "train_troops": scope[2]},
            )

    def _queue_market(self, account_id: str, city_id: int,
                      resource_type: int, side: str) -> None:
        """Get account-scoped live quotes without starting a transaction."""
        if (self.client is None or self.tasks_page.selected_account_id() != account_id
                or self.tasks_page.selected_task_name() not in {"buyResources", "sellResources"}):
            return
        self._pending_market = (account_id, city_id, resource_type, side)
        self._run_next_market()

    def _run_next_market(self) -> None:
        if self.client is None or self._worker is not None:
            return
        scope = self._pending_market
        self._pending_market = None
        if (scope is not None and self.tasks_page.selected_account_id() == scope[0]
                and self.tasks_page.selected_task_name() in {"buyResources", "sellResources"}):
            self._launch(
                self.client, "task_market", account_id=scope[0],
                task_payload={"city_id": scope[1], "resource_type": scope[2],
                              "side": scope[3]},
            )

    def _queue_academies(self, account_id: str) -> None:
        """Fetch academy research readiness for the selected account."""
        if (self.client is None or self.tasks_page.selected_account_id() != account_id
                or self.tasks_page.selected_task_name() != "research"):
            return
        self._pending_academies = account_id
        self._run_next_academies()

    def _run_next_academies(self) -> None:
        if self.client is None or self._worker is not None:
            return
        account_id = self._pending_academies
        self._pending_academies = None
        if (account_id and self.tasks_page.selected_account_id() == account_id
                and self.tasks_page.selected_task_name() == "research"):
            self._launch(self.client, "task_academies", account_id=account_id)

    def _queue_taverns(self, account_id: str) -> None:
        if (self.client is None or self.tasks_page.selected_account_id() != account_id
                or self.tasks_page.selected_task_name() != "tavernManager"):
            return
        self._pending_taverns = account_id
        self._run_next_taverns()

    def _run_next_taverns(self) -> None:
        if self.client is None or self._worker is not None:
            return
        account_id = self._pending_taverns
        self._pending_taverns = None
        if (account_id and self.tasks_page.selected_account_id() == account_id
                and self.tasks_page.selected_task_name() == "tavernManager"):
            self._launch(self.client, "task_taverns", account_id=account_id)

    def _queue_miracles(self, account_id: str) -> None:
        if (self.client is None or self.tasks_page.selected_account_id() != account_id
                or self.tasks_page.selected_task_name() != "activateMiracle"):
            return
        self._pending_miracles = account_id
        self._run_next_miracles()

    def _run_next_miracles(self) -> None:
        if self.client is None or self._worker is not None:
            return
        account_id = self._pending_miracles
        self._pending_miracles = None
        if (account_id and self.tasks_page.selected_account_id() == account_id
                and self.tasks_page.selected_task_name() == "activateMiracle"):
            self._launch(self.client, "task_miracles", account_id=account_id)

    def _queue_shrine(self, account_id: str) -> None:
        if (self.client is None or self.tasks_page.selected_account_id() != account_id
                or self.tasks_page.selected_task_name() != "activateShrine"):
            return
        self._pending_shrine = account_id
        self._run_next_shrine()

    def _run_next_shrine(self) -> None:
        if self.client is None or self._worker is not None:
            return
        account_id = self._pending_shrine
        self._pending_shrine = None
        if (account_id and self.tasks_page.selected_account_id() == account_id
                and self.tasks_page.selected_task_name() == "activateShrine"):
            self._launch(self.client, "task_shrine", account_id=account_id)

    def _queue_piracy(self, account_id: str) -> None:
        if (self.client is None or self.tasks_page.selected_account_id() != account_id
                or self.tasks_page.selected_task_name() != "autoPirate"):
            return
        self._pending_piracy = account_id
        self._run_next_piracy()

    def _run_next_piracy(self) -> None:
        if self.client is None or self._worker is not None:
            return
        account_id = self._pending_piracy
        self._pending_piracy = None
        if (account_id and self.tasks_page.selected_account_id() == account_id
                and self.tasks_page.selected_task_name() == "autoPirate"):
            self._launch(self.client, "task_piracy", account_id=account_id)

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
            logger.info("Connected to Daedalus API")
            self._success_notice(
                "Connected to Daedalus",
                "Secure connection verified. You can now open Overview or Accounts.",
            )
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
                    self._pending_task_cities = None
                    self._pending_military_reads.clear()
                    self.military_page.reset_backend_context()
                    self._pending_task_buildings = None
                    self._pending_workshop = None
                    self._pending_trainables = None
                    self._pending_market = None
                    self._pending_academies = None
                    self._pending_taverns = None
                    self._pending_miracles = None
                    self._pending_shrine = None
                    self._pending_piracy = None
                    self._pending_construction_preview = None
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
            self._recovery_followup = ("recovery_index", "")
        elif action == "accounts":
            self._show_accounts(payload)
            logger.info("Accounts refreshed")
            # Session and worker presence require separate authoritative reads.
            self._recovery_followup = ("connected_accounts", "")
        elif action == "extension_settings":
            self.appearance_page.set_extension_status(payload)
        elif action == "release_status":
            self.appearance_page.set_release_status(payload)
        elif action == "notification_settings":
            assert isinstance(payload, dict)
            self.appearance_page.set_notification_result(payload)
        elif action == "administrative_status":
            assert isinstance(payload, dict)
            self.appearance_page.set_admin_status(payload)
        elif action == "recovery_index":
            assert isinstance(payload, dict)
            self.accounts_page.set_recovery_status(payload)
        elif action in {
            "recovery_policy", "recovery_bulk", "recovery_pause",
            "recovery_resume", "recovery_import",
        }:
            if action == "recovery_bulk":
                results = payload.get("results", []) if isinstance(payload, dict) else []
                saved = sum(r.get("status") == "saved" for r in results if isinstance(r, dict))
                self._notice("Recovery policy updated", f"{saved} accounts updated; review skipped accounts.")
            else:
                self._notice("Recovery settings updated",
                             "Refresh the account recovery panel to review current status.")
            self._recovery_followup = ("recovery_index", "")
        elif action == "recovery_jobs":
            if isinstance(payload, dict):
                jobs = payload.get("jobs")
                receipts = payload.get("receipts")
                job_rows = jobs if isinstance(jobs, list) else []
                record_rows = receipts if isinstance(receipts, list) else []
                # User-facing summaries never print raw stored configuration.
                safe = [
                    f"{row.get('task','Job')}: "
                    f"{row.get('desired_state','unknown')} "
                    f"({'auto eligible' if row.get('restart_class') == 'continuous' else 'review needed'})"
                    for row in job_rows if isinstance(row, dict)
                ]
                self._notice(
                    "Saved jobs",
                    ("\n".join(safe[:15]) if safe else "No persisted managed jobs yet.")
                    + f"\n{len(record_rows)} recovery receipts.",
                )
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
            self.log_page.add_login_stage("backend_handoff_ready")
            logger.info("One-time Mac browser login prepared; no game action started")
        elif action == "native_login_complete":
            assert isinstance(payload, dict)
            automatic_result = (
                self._automatic_login_active
                and payload.get("account_id") == self._automatic_login_current
            )
            if automatic_result:
                # The server stores a client-sealed login only after verifying
                # the world cookie and player. Never write plaintext passwords
                # from a MainWindow callback.
                if (self._automatic_login_save_credentials
                        and payload.get("vault_saved") is not True):
                    self._notice(
                        "Automatic login not backed up",
                        "The session was verified, but saving the encrypted login "
                        "did not complete. Unlock Mac Keychain before next sign-in.",
                    )
                self._automatic_login_successes += 1
                if payload.get("status") in {"worker_recovered_verified", "worker_started_verified"}:
                    self._automatic_login_worker_recovered += 1
                    self.log_page.add_login_stage("handoff_verified")
                    logger.info("Gameforge session verified; existing worker reconnected")
                else:
                    self._automatic_login_bound_sessions += 1
                    self.log_page.add_login_stage("handoff_saved")
                    logger.info("Gameforge session verified and saved; no worker connected")
                self._reset_automatic_attempt()
                self._automatic_login_pending_advance = True
            if payload.get("status") in {"worker_recovered_verified", "worker_started_verified"}:
                account_id = payload.get("account_id")
                if isinstance(account_id, str):
                    self._show_verified_worker_immediately(account_id)
                self._success_notice(
                    "Game worker connected",
                    "Server independently verified the exact player and attached "
                    "an authenticated IkaBot worker. Warehouse reports are available.",
                )
            else:
                self._notice(
                    "Game session saved; worker unavailable",
                    "The server verified and saved the cookie, but could not attach "
                    "a game worker. Warehouse reports are not yet available. "
                    "Check backend startup and Activity diagnostics.",
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
            assert payload is None or isinstance(payload, list)
            self.accounts_page.set_connected_ids(payload)
            logger.info("IkaBot existing-session status refreshed")
            self._recovery_followup = ("recovery_index", "")
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
        elif action in {"military_overview", "military_movements"}:
            assert isinstance(payload, dict)
            worker = self._worker
            account_id = getattr(worker, "account_id", None)
            if isinstance(account_id, str):
                self.military_page.set_result(account_id, action, payload)
        elif action == "server_activity":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(payload, dict) and isinstance(request, dict):
                self.log_page.set_server_activity(payload, request["before"], request["status"])
        elif action == "task_shipment_preview":
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_shipment_preview(payload, request["nonce"])
        elif action == "task_island_destinations":
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_island_destinations(payload, request["nonce"])
        elif action == "task_cities":
            assert isinstance(payload, dict)
            self.tasks_page.set_cities(payload["account_id"], payload["cities"])
        elif action == "task_piracy":
            assert isinstance(payload, dict)
            self.tasks_page.set_pirate_fortresses(payload)
        elif action == "task_shrine":
            assert isinstance(payload, dict)
            self.tasks_page.set_shrine(payload)
        elif action == "task_miracles":
            assert isinstance(payload, dict)
            self.tasks_page.set_miracles(payload)
        elif action == "task_taverns":
            assert isinstance(payload, dict)
            self.tasks_page.set_taverns(payload)
        elif action == "task_academies":
            assert isinstance(payload, dict)
            self.tasks_page.set_academies(payload)
        elif action == "task_market":
            assert isinstance(payload, dict)
            self.tasks_page.set_market_quotes(payload)
        elif action == "task_trainables":
            assert isinstance(payload, dict)
            self.tasks_page.set_trainable_units(payload)
        elif action == "task_workshop":
            assert isinstance(payload, dict)
            self.tasks_page.set_workshop_upgrades(payload)
        elif action == "task_buildings":
            assert isinstance(payload, dict)
            self.tasks_page.set_buildings(payload["account_id"], payload["city_id"],
                                          payload["buildings"])
        elif action == "task_vacation_preview":
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_vacation_preview(payload, request["nonce"])
        elif action in {"task_attack_inventory", "task_attack_preview"}:
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                if action == "task_attack_inventory":
                    self.tasks_page.set_attack_inventory(payload, request["nonce"])
                else:
                    self.tasks_page.set_attack_preview(payload, request["nonce"])
        elif action == "task_grind_preview":
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_grind_preview(payload, request["nonce"])
        elif action == "task_training_preview":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(payload, dict) and isinstance(request, dict):
                self.tasks_page.set_training_preview(payload, request["nonce"])
        elif action == "task_station_preview":
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_station_preview(payload, request["nonce"])
        elif action in {"task_build_options", "task_build_preview"}:
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                if action == "task_build_options":
                    self.tasks_page.set_build_options(payload, request["nonce"])
                else:
                    self.tasks_page.set_build_preview(payload, request["nonce"])
        elif action == "task_layout_preview":
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_layout_preview(payload, request["nonce"])
        elif action == "task_worker_preview":
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_worker_preview(payload, request["nonce"])
        elif action == "task_donation_preview":
            assert isinstance(payload, dict)
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_donation_preview(payload, request["nonce"])
        elif action == "task_construction_preview":
            assert isinstance(payload, dict)
            self.tasks_page.set_construction_preview(payload)
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
        elif action in {"task_start_batch", "reviewed_batch"}:
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
                self._success_notice(
                    "Automation requests received",
                    f"Received {count} account-scoped receipts; review their status.",
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

    def _show_verified_worker_immediately(self, account_id: str) -> None:
        """Render green Session/Worker as soon as authoritative IPC has attested.

        The encrypted handoff receipt is returned only after the server probes
        its worker's current world/player. Avoid waiting for a full sign-in
        cohort to finish, while the subsequent backend refresh remains truth.
        """
        visible = [dict(row) for row in self.accounts_page._accounts]
        if not any(row.get("id") == account_id for row in visible):
            return
        for row in visible:
            if row.get("id") == account_id:
                row["session_status"] = "authenticated"
        self._show_accounts(visible)
        attached = set(self.accounts_page._connected_ids or ())
        attached.add(account_id)
        self.accounts_page.set_connected_ids(sorted(attached))

    def _show_accounts(self, data: object) -> None:
        assert isinstance(data, list)
        # Server metadata is displayed immediately; per-account Keychain reads
        # happen only in the killable login subprocess, never in the Qt loop.
        cached_emails = {
            str(row["id"]): row["email"] for row in self.accounts_page._accounts
            if isinstance(row.get("id"), str) and isinstance(row.get("email"), str)
        }
        visible = [dict(raw) for raw in data]
        for account in visible:
            if not account.get("email") and account.get("id") in cached_emails:
                account["email"] = cached_emails[account["id"]]
        self.accounts_page.set_accounts(visible)
        self.appearance_page.set_admin_accounts(visible)
        self.warehouses_page.set_accounts(visible)
        self.military_page.set_accounts(visible)
        self.log_page.set_accounts(visible)
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
        if action == "extension_settings":
            self.appearance_page.set_extension_unavailable(getattr(self._worker, "account_id", None))
        if action == "release_status":
            self.appearance_page.set_release_unavailable()
        if action == "notification_settings":
            aid = getattr(self._worker, "account_id", None)
            if isinstance(aid, str):
                self.appearance_page.set_notification_unavailable(aid)
        if action == "administrative_status":
            aid = getattr(self._worker, "account_id", None)
            if isinstance(aid, str):
                self.appearance_page.set_admin_unavailable(aid)
        # Never reuse a recovery refresh across a failed or changed backend.
        self._recovery_followup = None
        if action == "native_login_start":
            self._pending_native_login_challenge = None
        if (action in {"native_login_start", "native_login_complete", "native_login_cancel"}
                and self._automatic_login_active and self._automatic_login_current):
            self.log_page.add_login_stage("handoff_failed")
            if (action == "native_login_complete" and not self._automatic_login_force_visible
                    and not self._automatic_login_cancelled
                    and error != "Game world is unreachable from the Daedalus server; saved sessions will retry when connectivity recovers"):
                # The first one-use server ticket is already consumed. Never
                # replay its envelope: request a fresh ticket *after* this API
                # worker finishes, and force the next child to open visible Chrome.
                self._automatic_login_force_visible = True
                self._automatic_login_pending_visible_retry = True
                self.log_page.add_login_stage("server_rejected_headless")
                logger.warning("Server declined headless cookie handoff; visible recovery queued")
                self.accounts_page.set_automatic_login_busy(
                    True, "Server rejected the headless session. Opening visible Chrome for recovery…",
                )
            else:
                self._automatic_login_failures += 1
                self._reset_automatic_attempt()
                self._automatic_login_pending_advance = True
        if action in {"military_overview", "military_movements"}:
            worker = self._worker
            account_id = getattr(worker, "account_id", None)
            if isinstance(account_id, str):
                self.military_page.set_unavailable(account_id, action)
        if action == "server_activity":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.log_page.set_server_activity_unavailable(getattr(self._worker, "account_id", None),
                                                              request["before"], request["status"])
        if action == "task_shipment_preview":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_shipment_unavailable(request["nonce"])
        if action == "task_island_destinations":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_island_destinations_unavailable(
                    getattr(self._worker, "account_id", None), request["nonce"])
        if action == "task_cities":
            worker = self._worker
            account_id = getattr(worker, "account_id", None)
            if isinstance(account_id, str):
                self.tasks_page.set_cities_unavailable(account_id)
        if action == "task_piracy":
            account_id = getattr(self._worker, "account_id", None)
            if isinstance(account_id, str):
                self.tasks_page.set_pirate_fortresses_unavailable(account_id)
        if action == "task_shrine":
            account_id = getattr(self._worker, "account_id", None)
            if isinstance(account_id, str):
                self.tasks_page.set_shrine_unavailable(account_id)
        if action == "task_miracles":
            account_id = getattr(self._worker, "account_id", None)
            if isinstance(account_id, str):
                self.tasks_page.set_miracles_unavailable(account_id)
        if action == "task_taverns":
            account_id = getattr(self._worker, "account_id", None)
            if isinstance(account_id, str):
                self.tasks_page.set_taverns_unavailable(account_id)
        if action == "task_academies":
            account_id = getattr(self._worker, "account_id", None)
            if isinstance(account_id, str):
                self.tasks_page.set_academies_unavailable(account_id)
        if action == "task_market":
            worker = self._worker
            account_id = getattr(worker, "account_id", None)
            request = getattr(worker, "task_payload", None)
            city_id = request.get("city_id") if isinstance(request, dict) else None
            resource_type = request.get("resource_type") if isinstance(request, dict) else None
            side = request.get("side") if isinstance(request, dict) else None
            if (isinstance(account_id, str) and type(city_id) is int
                    and type(resource_type) is int and isinstance(side, str)):
                self.tasks_page.set_market_unavailable(account_id, city_id, resource_type, side)
        if action == "task_trainables":
            worker = self._worker
            account_id = getattr(worker, "account_id", None)
            request = getattr(worker, "task_payload", None)
            city_id = request.get("city_id") if isinstance(request, dict) else None
            train_troops = request.get("train_troops") if isinstance(request, dict) else None
            if (isinstance(account_id, str) and type(city_id) is int
                    and type(train_troops) is bool):
                self.tasks_page.set_trainable_units_unavailable(account_id, city_id, train_troops)
        if action == "task_workshop":
            worker = self._worker
            account_id = getattr(worker, "account_id", None)
            request = getattr(worker, "task_payload", None)
            city_id = request.get("city_id") if isinstance(request, dict) else None
            if isinstance(account_id, str) and type(city_id) is int:
                self.tasks_page.set_workshop_unavailable(account_id, city_id)
        if action == "task_buildings":
            worker = self._worker
            account_id = getattr(worker, "account_id", None)
            request = getattr(worker, "task_payload", None)
            city_id = request.get("city_id") if isinstance(request, dict) else None
            if isinstance(account_id, str) and type(city_id) is int:
                self.tasks_page.set_buildings_unavailable(account_id, city_id)
        if action == "task_vacation_preview":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_vacation_unavailable(request["nonce"])
        if action in {"task_attack_inventory", "task_attack_preview"}:
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_attack_unavailable(request["nonce"])
        if action == "task_grind_preview":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_grind_unavailable(request["nonce"])
        if action == "task_training_preview":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_training_unavailable(request["nonce"])
        if action == "task_station_preview":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_station_unavailable(request["nonce"])
        if action in {"task_build_options", "task_build_preview"}:
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_build_unavailable(request["nonce"])
        if action == "task_layout_preview":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_layout_preview_unavailable(request["nonce"])
        if action == "task_worker_preview":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_worker_preview_unavailable(request["nonce"])
        if action == "task_donation_preview":
            request = getattr(self._worker, "task_payload", None)
            if isinstance(request, dict):
                self.tasks_page.set_donation_preview_unavailable(request["nonce"])
        if action == "task_construction_preview":
            worker = self._worker
            account_id = getattr(worker, "account_id", None)
            request = getattr(worker, "task_payload", None)
            city_id = request.get("city_id") if isinstance(request, dict) else None
            if isinstance(account_id, str) and type(city_id) is int:
                self.tasks_page.set_construction_preview_unavailable(account_id, city_id)
        if action == "task_preflight":
            worker = self._worker
            request = getattr(worker, "task_payload", None)
            generation = request.get("generation") if isinstance(request, dict) else None
            if generation is None or generation == self.tasks_page._selection_generation:
                self.tasks_page.set_preflight_unavailable()
        if action in {"task_start_batch", "reviewed_batch", "task_start"}:
            for view in self._task_views:
                view.finish_launch()
        if action in {"task_start_batch", "reviewed_batch"}:
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
                "Warehouse refresh unavailable: no independently authenticated "
                "game workers. If the game world is unreachable from the server, "
                "saved sessions will be retried automatically. "
                "Any earlier report is stale."
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
                # A failed reconnect must not hide an existing authorized session,
                # but the user must not confuse it with successful new credentials.
                self.connection_page.set_connected(True)
                self.connection_page.status_label.setText(
                    "New connection failed. The previously verified backend remains connected."
                )
        # APIWorker exports only bounded, nonsecret error classes. Keep the
        # reason visible to the owner instead of a generic warning, but never
        # copy an arbitrary server response or browser trace into the log.
        logger.warning("Backend %s request failed (%s)", action, _safe_api_failure(error))
        if action not in {"assistance_pending", "task_preflight", "task_cities",
                          "task_buildings", "task_construction_preview", "task_workshop",
                          "task_trainables", "task_market", "task_academies",
                          "task_taverns", "task_miracles", "task_shrine", "task_piracy",
                          "military_overview", "military_movements"}:
            if action.startswith("native_login_"):
                known_reason = str(error) if str(error) in {
                    "A Gameforge email is required for first-time account binding",
                    "This worker is busy or has an uncertain task; reconcile it before login",
                    "Running or uncertain tasks must be reconciled before login",
                    "Server did not verify the exact game account; login was not accepted",
                    "Gameforge email differs from the existing account binding",
                    "Another worker owns this game account",
                    "Browser handoff is expired or already consumed",
                    "Game world is unreachable from the Daedalus server; saved sessions will retry when connectivity recovers",
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
        if self._closing_requested:
            return
        if self._retry_rejected_handoff_visibly():
            return
        pending_cancel, self._pending_selenium_cancel = self._pending_selenium_cancel, None
        if pending_cancel is not None:
            self._cancel_selenium_handoff(pending_cancel)
            return
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
            self._run_next_military_read()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_task_cities()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_task_buildings()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_construction_preview()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_workshop()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_trainables()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_market()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_academies()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_taverns()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_miracles()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_shrine()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_piracy()
        if self._worker is None and not self._automatic_login_active:
            self._run_next_preflight()

    def _notice(self, title: str, message: str) -> None:
        # Fluent InfoBarManager stacks TOP_RIGHT notifications automatically.
        # Default 2-second auto-dismiss made important errors unreadable.
        InfoBar.warning(
            title, message, parent=self, position=InfoBarPosition.TOP_RIGHT,
            duration=120_000, isClosable=True,
        )

    def _success_notice(self, title: str, message: str) -> None:
        InfoBar.success(
            title, message, parent=self, position=InfoBarPosition.TOP_RIGHT,
            duration=120_000, isClosable=True,
        )

    def abort_browser_login(self) -> None:
        """Also invoked by macOS application Quit, not just window Close."""
        self._closing_requested = True
        self._selenium_watchdog.stop()
        worker = self._selenium_worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait(2000)

    def closeEvent(self, event) -> None:
        self._assistance_poll.stop()
        self._closing_requested = True
        self._selenium_watchdog.stop()
        self._automatic_login_cancelled = True
        self._automatic_login_queue.clear()
        self._automatic_login_report = None
        if self._selenium_worker is not None and self._selenium_worker.isRunning():
            # The child process group is forcibly killed (including Chrome).
            # Its supervisory QThread only reads the local pipe and should
            # finish promptly. Never wait on ChromeDriver itself.
            self._selenium_worker.cancel()
            if not self._selenium_worker.wait(2000):
                # Keep Qt responsive and automatically retry closing after
                # the supervisor exits; do not require another Cmd+Q.
                event.ignore()
                self._selenium_worker.finished.connect(
                    lambda: QTimer.singleShot(0, self.close)
                )
                return
        if self._worker is not None and self._worker.isRunning():
            # API requests may be in flight; never block Qt for 9 seconds.
            # Once the bounded HTTP request finishes, close automatically.
            event.ignore()
            self._worker.finished.connect(lambda: QTimer.singleShot(0, self.close))
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
