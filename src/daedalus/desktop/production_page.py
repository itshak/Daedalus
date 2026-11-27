"""Globally scoped production inventory and independently reviewed allocations."""
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CaptionLabel, CheckBox, ComboBox, PrimaryPushButton, PushButton, SpinBox

from daedalus.account_display import account_player_names
from daedalus.desktop.design_system import PageHeading
from daedalus.desktop.pages import _populate, _table
from daedalus.production_inventory import validate_production_inventory


class ProductionPage(QWidget):
    refresh_requested = Signal(list)
    preview_requested = Signal(dict)
    start_requested = Signal(list)
    history_requested = Signal(list)
    reconciliation_requested = Signal(dict)
    reconcile_confirmed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("production_page")
        self._accounts = {}
        self._cities = {}
        self._results = {}
        self._unavailable = set()
        self._loading = False
        self._busy = False
        self._reviews = []
        self._excluded = set()
        self._overrides = {}
        self._target_keys = []
        self._history = []
        self._reconciliation = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 22)
        layout.addWidget(PageHeading("Production", "Current city workforce and resource capacity"))
        toolbar = QHBoxLayout()
        self.resource_combo = ComboBox()
        self.resource_combo.setAccessibleName("Production resource or workforce section")
        for key, text in (("all", "All resources"), ("wood", "Wood"), ("wine", "Wine"),
                          ("marble", "Marble"), ("crystal", "Crystal"), ("sulfur", "Sulfur"),
                          ("academy", "Academy scientists"), ("temple", "Temple priests")):
            self.resource_combo.addItem(text, userData=key)
        self.resource_combo.currentIndexChanged.connect(self._resource_changed)
        toolbar.addWidget(self.resource_combo, 1)
        self.refresh_button = PrimaryPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_button)
        self.history_button = PushButton("Execution history")
        self.history_button.clicked.connect(self._request_history)
        toolbar.addWidget(self.history_button)
        layout.addLayout(toolbar)
        self.status = CaptionLabel("Use free citizens first; other production may release workers.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = _table(["Account", "City", "Resource", "Current", "Normal capacity",
                             "Extra capacity", "Free citizens"])
        self.table.setAccessibleName("Production workforce inventory")
        layout.addWidget(self.table, 1)
        policy = QHBoxLayout()
        self.both_priority = ComboBox()
        for key, text in (("", "Choose priority"), ("wood", "Wood first"), ("luxury", "Luxury first")):
            self.both_priority.addItem(text, userData=key)
        self.both_priority.setAccessibleName("Both-resource priority")
        self.both_priority.currentIndexChanged.connect(self._resource_changed)
        policy.addWidget(self.both_priority)
        self.mode = ComboBox()
        for key, text in (("maximum", "Maximum"), ("percentage", "Percentage"), ("exact", "Exact workers")):
            self.mode.addItem(text, userData=key)
        self.mode.setAccessibleName("Production target")
        self.amount = SpinBox()
        self.amount.setRange(0, 2_000_000)
        self.amount.setValue(100)
        self.amount.setAccessibleName("Target amount")
        self.overcharge = CheckBox("Include extra workers")
        self.available_only = CheckBox("Use only available population")
        self.fallback = CheckBox("Allow reviewed full donor release")
        self.fallback.setToolTip("Only if available citizens or target capacity are unknown; restore unused donor workers.")
        self.available_only.toggled.connect(lambda checked: self.fallback.setChecked(False) if checked else None)
        self.mode.currentIndexChanged.connect(self._update_controls)
        self.available_only.toggled.connect(self._update_controls)
        for widget in (self.mode, self.amount, self.overcharge, self.available_only, self.fallback):
            policy.addWidget(widget)
        layout.addLayout(policy)
        self.targets = _table(["Include", "Account", "City", "Exact override (optional)"])
        self.targets.setAccessibleName("Cities for reviewed allocation")
        self.targets.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.targets.itemChanged.connect(self._target_changed)
        layout.addWidget(self.targets, 1)
        controls = QHBoxLayout()
        self.preview_button = PrimaryPushButton("Preview selected cities")
        self.preview_button.clicked.connect(self._preview)
        self.confirm_button = PrimaryPushButton("Confirm and start")
        self.confirm_button.clicked.connect(self._confirm)
        self.cancel_button = PushButton("Cancel review")
        self.cancel_button.clicked.connect(self._discard_review)
        for widget in (self.preview_button, self.confirm_button, self.cancel_button):
            controls.addWidget(widget)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.review_table = _table(["Account", "City", "Target before → after", "Donor before → after", "Release", "Shortfall"])
        self.review_table.setAccessibleName("Reviewed production impact")
        layout.addWidget(self.review_table, 1)
        self._update_controls()

    def _resource_changed(self):
        self._excluded.clear()
        self._overrides.clear()
        if self.resource_combo.currentData() == "all":
            self.mode.setCurrentIndex(0)
            self.fallback.setChecked(False)
        self._discard_review()
        self._render()

    def _discard_review(self):
        self._reviews = []
        self.review_table.setRowCount(0)
        self._update_controls()

    def _update_controls(self, *_):
        resource = self.resource_combo.currentData()
        both = resource == "all"
        self.both_priority.setVisible(both)
        self.both_priority.setEnabled(not self._busy and not self._reviews and not self._loading)
        editing = not self._loading and not self._busy and not self._reviews and (
            resource in {"wood", "wine", "marble", "crystal", "sulfur"} or both and bool(self.both_priority.currentData()))
        self.mode.setEnabled(editing and not both)
        self.amount.setEnabled(editing and self.mode.currentData() != "maximum")
        if self.mode.currentData() == "percentage":
            self.amount.setMaximum(100)
        else:
            self.amount.setMaximum(2_000_000)
        self.overcharge.setEnabled(editing)
        self.available_only.setEnabled(editing)
        self.fallback.setEnabled(editing and not both and not self.available_only.isChecked())
        self.targets.setVisible(resource in {"wood", "wine", "marble", "crystal", "sulfur"} or both and bool(self.both_priority.currentData()))
        self.targets.setEnabled(editing)
        self.preview_button.setEnabled(editing and bool(self._target_keys))
        self.confirm_button.setEnabled(not self._busy and bool(self._reviews))
        self.cancel_button.setEnabled(not self._busy and bool(self._reviews))
        self.review_table.setVisible(bool(self._reviews))
        self.resource_combo.setEnabled(not self._busy)
        self.refresh_button.setEnabled(not self._busy and not self._loading)
        self.history_button.setEnabled(not self._busy and not self._loading and bool(self._accounts))

    def _target_changed(self, item):
        if not 0 <= item.row() < len(self._target_keys):
            return
        key = self._target_keys[item.row()]
        if item.column() == 0:
            if item.checkState() == Qt.Checked:
                self._excluded.discard(key)
            else:
                self._excluded.add(key)
        elif item.column() == 3:
            self._overrides[key] = item.text().strip()

    def _render_targets(self, names):
        resource = self.resource_combo.currentData()
        self._target_keys = [key for key, result in self._results.items()
                             if resource in ("all", "wood") or resource == result["luxury"]]
        self.targets.blockSignals(True)
        try:
            self.targets.setRowCount(len(self._target_keys))
            for i, key in enumerate(self._target_keys):
                aid, _cid = key
                selected = QTableWidgetItem()
                selected.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                selected.setCheckState(Qt.Unchecked if key in self._excluded else Qt.Checked)
                self.targets.setItem(i, 0, selected)
                for column, value in ((1, names[aid]), (2, self._cities[key]),
                                      (3, self._overrides.get(key, ""))):
                    item = QTableWidgetItem(value)
                    if column != 3 or resource == "all":
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.targets.setItem(i, column, item)
        finally:
            self.targets.blockSignals(False)
        self._update_controls()

    def _preview(self):
        from daedalus.production_inventory import validate_priority_draft

        if not self.preview_button.isEnabled():
            return
        grouped = {}
        resource = self.resource_combo.currentData()
        mode = self.mode.currentData()
        for key in self._target_keys:
            if key in self._excluded:
                continue
            aid, cid = key
            override = "" if resource == "all" else self._overrides.get(key, "")
            if override and (not override.isascii() or not override.isdecimal() or len(override) > 7):
                self.status.setText("Enter a valid exact override.")
                return
            draft = {"resource": resource, "mode": "exact" if override else mode,
                     "amount": int(override) if override else None if mode == "maximum" else self.amount.value(),
                     "overcharge": self.overcharge.isChecked(),
                     "available_only": self.available_only.isChecked(),
                     "allow_fallback": self.fallback.isChecked() and not self.available_only.isChecked()}
            if resource == "all":
                draft.update(resource="wood" if self.both_priority.currentData() == "wood" else self._results[key]["luxury"],
                             mode="maximum", amount=None, allow_fallback=False, fill_both=True)
            grouped.setdefault(aid, []).append({"city_id": cid, "draft": draft})
        try:
            if not grouped or len(grouped) > 32:
                raise ValueError("Choose 1 to 32 accounts")
            for rows in grouped.values():
                validate_priority_draft(rows[0]["city_id"], rows)
        except ValueError:
            self.status.setText("Invalid allocation. Choose at most 16 cities per account, and valid amounts.")
            return
        self._busy = True
        self.status.setText("Preparing fresh account-scoped review…")
        self._update_controls()
        self.preview_requested.emit(grouped)

    def set_reviews(self, reviews):
        self._busy = False
        self._reviews = []
        rows = []
        names = account_player_names([{k: row.get(k) for k in ("id", "player", "world")}
                                      for row in self._accounts.values()])
        for review in reviews:
            aid = review["account_id"]
            if aid not in self.eligible_ids():
                self.set_review_unavailable()
                return
            self._reviews.append(review)
            for plan in review["plans"]:
                key = (aid, plan["city_id"])
                if key not in self._results:
                    self.set_review_unavailable()
                    return
                target = "unknown" if plan["target_after"] is None else str(plan["target_after"])
                donor = "unknown" if plan["donor_after"] is None else str(plan["donor_after"])
                rows.append([names[aid], self._cities[key],
                             f'{plan["resource"]}: {plan["target_before"]} → {target}',
                             f'{plan["donor_before"]} → {donor}', plan["donor_release"], plan["shortfall"]])
        _populate(self.review_table, rows)
        self.status.setText(f"Review {len(rows)} cities in {len(reviews)} accounts. No assignments started.")
        self._update_controls()

    def set_review_unavailable(self):
        self._busy = False
        self._discard_review()
        self.status.setText("Review or dispatch unavailable. Check Activity before retrying.")

    def _confirm(self):
        if not self.confirm_button.isEnabled():
            return
        if any(r["deadline"] <= time.monotonic() for r in self._reviews):
            self._discard_review()
            self.status.setText("Review expired; prepare a new preview.")
            return
        count = sum(len(r["plans"]) for r in self._reviews)
        if QMessageBox.question(self, "Confirm production allocation",
                f"Apply the reviewed allocation to {count} cities in {len(self._reviews)} accounts? "
                "Other production may be reduced as shown. Check Activity for results.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        entries = [{"account_id": r["account_id"], "task": "modifyProduction",
                    "preview_id": r["preview_id"]} for r in self._reviews]
        self._busy = True
        self._update_controls()
        self.start_requested.emit(entries)

    def set_launch_result(self, result):
        self._busy = False
        self._discard_review()
        if result.get("blocked"):
            self.status.setText("Batch blocked; no account launched. Prepare a fresh review.")
        elif result.get("halted"):
            self.status.setText("Dispatch unconfirmed. Check Activity before retrying.")
        else:
            self.status.setText(f'Received {len(result.get("submitted", []))} account launch receipts. Check per-city results.')
        self._update_controls()

    def _request_history(self):
        if not self.history_button.isEnabled():
            return
        self._busy = True
        self._update_controls()
        self.history_requested.emit(list(self._accounts))

    def set_history(self, result):
        self._busy = False
        self._history = result
        self._update_controls()
        names = account_player_names([{k: row.get(k) for k in ("id", "player", "world")}
                                      for row in self._accounts.values()])
        lines, pending = [], []
        for item in result:
            aid = item.get("account_id")
            if aid not in names:
                continue
            if item.get("error"):
                lines.append(f"{names[aid]}: unavailable")
                continue
            for run in item["runs"]:
                status = "running or needs review" if run["status"] == "prepared" else run["status"]
                lines.append(f'{names[aid]} · {status} · {run["run_id"]}')
                for city in run["cities"]:
                    city_name = self._cities.get((aid, city["city_id"]), str(city["city_id"]))
                    lines.append(f'  {city_name} · {city["resource"]}: {city["status"]}')
                    for stage in city["stages"]:
                        observed = stage.get("observed")
                        counts = f' (wood {observed["resource"]}, luxury {observed["tradegood"]})' if observed else ""
                        lines.append(f'    {stage["stage"]}: {stage["value"]} · {stage["status"]}{counts}')
                    if city["result"]:
                        r = city["result"]
                        lines.append(f'    Verified: target {r["target"]}, other resource {r["donor"]}, shortfall {r["shortfall"]}')
                if run["status"] == "prepared" and aid in self.eligible_ids():
                    pending.append((aid, run["run_id"]))
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Production execution history")
        dialog.setText("Actual receipts; pending assignments are never automatically retried.")
        dialog.setDetailedText("\n".join(lines) or "No production receipts")
        dialog.setStandardButtons(QMessageBox.Close)
        reconcile = dialog.addButton("Review actual allocations", QMessageBox.ActionRole) if pending else None
        dialog.exec()
        if reconcile is not None and dialog.clickedButton() is reconcile:
            labels = [f"{names[aid]} · {run}" for aid, run in pending]
            selected, accepted = QInputDialog.getItem(self, "Reconcile production",
                "Choose a stopped or interrupted run", labels, 0, False)
            if accepted and selected in labels:
                aid, run = pending[labels.index(selected)]
                if aid not in self.eligible_ids():
                    return
                self._busy = True
                self._update_controls()
                self.reconciliation_requested.emit({"account_id": aid, "run_id": run})

    def set_reconciliation(self, review):
        self._busy = False
        self._update_controls()
        if review["account_id"] not in self.eligible_ids():
            return
        lines = [f'{r["city_name"]}: wood {r["resource"]}, {r["luxury"]} {r["tradegood"]}'
                 for r in review["observations"]]
        if QMessageBox.question(self, "Review actual allocations",
            "\n".join(lines) + "\n\nAcknowledge these counts and clear the production fence? "
            "This does not change any workers. Any new assignment requires a fresh review.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self._busy = True
        self._update_controls()
        self.reconcile_confirmed.emit({"account_id": review["account_id"], "run_id": review["run_id"],
                                      "preview_id": review["preview_id"]})

    def set_reconciled(self, result):
        self._busy = False
        self._update_controls()
        self.status.setText("Production fence cleared. No workers were changed.")

    def set_accounts(self, accounts):
        self._accounts = {row["id"]: dict(row) for row in accounts if isinstance(row.get("id"), str)}
        self._cities.clear()
        self._results.clear()
        self._unavailable.clear()
        self._busy = False
        self._history = []
        self._reconciliation = None
        self._excluded.clear()
        self._overrides.clear()
        self._discard_review()
        self.finish_refresh()
        self._render()

    def refresh(self):
        if self._loading or self._busy:
            return
        self._loading = True
        self._discard_review()
        self.refresh_button.setEnabled(False)
        self._cities.clear()
        self._results.clear()
        self._unavailable = {(aid, None) for aid, row in self._accounts.items() if row.get("enabled") is not True}
        self._render()
        self.refresh_requested.emit(self.eligible_ids())

    def finish_refresh(self):
        self._loading = False
        self._update_controls()

    def eligible_ids(self):
        return [aid for aid, row in self._accounts.items() if row.get("enabled") is True]

    def set_cities(self, aid, cities):
        if aid not in self.eligible_ids() or not isinstance(cities, list) or len(cities) > 500:
            return []
        valid = {}
        for city in cities:
            if (not isinstance(city, dict) or type(city.get("id")) is not int
                    or not 0 < city["id"] < 10**12 or city["id"] in valid
                    or not isinstance(city.get("name"), str)):
                self.set_unavailable(aid)
                return []
            valid[city["id"]] = city["name"]
        for cid, name in valid.items():
            self._cities[aid, cid] = name
        self._render()
        return list(valid)

    def set_result(self, aid, cid, data):
        if aid not in self.eligible_ids() or (aid, cid) not in self._cities:
            return
        try:
            if not isinstance(data, dict) or data.get("account_id") != aid:
                raise ValueError("Production identity mismatch")
            clean = validate_production_inventory(cid, {k: v for k, v in data.items() if k != "account_id"})
        except ValueError:
            self.set_unavailable(aid, cid)
            return
        self._results[aid, cid] = clean
        self._unavailable.discard((aid, cid))
        self._render()

    def set_unavailable(self, aid, cid=None):
        if aid in self._accounts:
            if cid is not None:
                self._results.pop((aid, cid), None)
            self._unavailable.add((aid, cid))
            self._render()

    def _render(self):
        names = account_player_names([{k: row.get(k) for k in ("id", "player", "world")}
                                      for row in self._accounts.values()])
        selected = self.resource_combo.currentData() or "all"
        rows = []
        for (aid, cid), city in self._cities.items():
            data = self._results.get((aid, cid))
            if data is None:
                rows.append([names[aid], city, "Unavailable" if (aid, cid) in self._unavailable else "Loading…",
                             None, None, None, None])
                continue
            luxury = data["luxury"]
            if selected in ("academy", "temple"):
                kinds = [selected]
            elif selected == "all":
                kinds = ["resource", "tradegood"]
            elif selected == "wood":
                kinds = ["resource"]
            else:
                kinds = ["tradegood"] if selected == luxury else []
            for kind in kinds:
                site = data["sites"][kind]
                label = "Wood" if kind == "resource" else luxury.capitalize() if kind == "tradegood" else kind.capitalize()
                if site["available"]:
                    rows.append([names[aid], city, label, site["current"], site["maximum"], site["extra"], data["free_citizens"]])
                else:
                    rows.append([names[aid], city, label, "Absent" if site["reason"] == "building_absent" else "Unavailable",
                                 None, None, data["free_citizens"]])
        for aid, cid in sorted(self._unavailable, key=lambda v: (v[0], v[1] or 0)):
            if cid is None and aid in names:
                rows.append([names[aid], "Unavailable", None, None, None, None, None])
        _populate(self.table, rows)
        self._render_targets(names)
        self.status.setText(f"{len(self._results)} city observations · Unknown values are not zero.")
