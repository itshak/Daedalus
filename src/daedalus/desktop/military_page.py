"""Source-backed military dashboards for troop, fleet, and movement inspection.

No action on this page can launch recruitment, attacks, transports, or other
game mutations. All data arrives via authenticated Daedalus read endpoints.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    Pivot,
    PrimaryPushButton,
    SubtitleLabel,
)

from daedalus.account_display import account_player_names
from daedalus.desktop.design_system import PageHeading
from daedalus.desktop.pages import _populate, _table


class MilitaryPage(QWidget):
    """One compact, account-aware workspace for IkaBot's read-only CLI views."""

    refresh_requested = Signal(list, str)
    _MODES = ("troops", "fleet", "movements")
    _TABLE_HEADERS = (
        ["Account", "City", "Unit", "Count"],
        ["Account", "City", "Ship", "Count"],
        ["Account", "Origin", "Destination", "Mission", "Arrival", "Troops", "Ships"],
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("military_page")
        self._accounts: list[dict[str, object]] = []
        self._cache: dict[tuple[str, str], dict[str, object]] = {}
        self._failures: set[tuple[str, str]] = set()
        self._mode = "troops"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 22)
        layout.setSpacing(9)
        layout.addWidget(PageHeading(
            "Military", "Inspect current troops, fleets and movements without issuing orders."
        ))
        scope = QHBoxLayout()
        scope.setSpacing(10)
        scope.addWidget(BodyLabel("Accounts"))
        self.account_combo = ComboBox(self)
        self.account_combo.setAccessibleName("Military account scope")
        self.account_combo.currentIndexChanged.connect(self._render)
        scope.addWidget(self.account_combo, 1)
        self.refresh_button = PrimaryPushButton("Refresh")
        self.refresh_button.setAccessibleName("Read current military data for selected accounts")
        self.refresh_button.clicked.connect(self.refresh)
        scope.addWidget(self.refresh_button)
        layout.addLayout(scope)

        self.tabs = Pivot(self)
        self.tabs.setAccessibleName("Military inventory category")
        for i, (name, label) in enumerate(zip(self._MODES, ("Troops", "Fleet", "Movements"))):
            self.tabs.addItem(
                routeKey=name, text=label,
                onClick=lambda _checked=False, i=i: self._select_mode(i),
            )
        self.tabs.setCurrentItem("troops")
        layout.addWidget(self.tabs)

        self.headline = SubtitleLabel("Troops by city")
        layout.addWidget(self.headline)
        self.status = CaptionLabel(
            "Choose an account or All accounts, then refresh to read current game data."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.stack = QStackedWidget(self)
        self.tables = [_table(headers) for headers in self._TABLE_HEADERS]
        for table, name in zip(self.tables, self._MODES):
            table.setAccessibleName(f"Read-only {name} by verified account")
            table.setSortingEnabled(True)
            header = table.horizontalHeader()
            header.setStretchLastSection(False)
            if name == "movements":
                for column in (0, 1, 2, 3):
                    header.setSectionResizeMode(column, QHeaderView.Stretch)
                for column in (4, 5, 6):
                    table.setColumnWidth(column, 88)
            else:
                for column in (0, 1, 2):
                    header.setSectionResizeMode(column, QHeaderView.Stretch)
                table.setColumnWidth(3, 105)
            self.stack.addWidget(table)
        layout.addWidget(self.stack, 1)
        self.note = CaptionLabel(
            "Read-only · Unavailable accounts are not counted as zero."
        )
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self._render()

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        """Account IDs always come from the authorized backend account catalog."""
        prior = self.account_combo.currentData() if self.account_combo.count() else "__all__"
        self._accounts = [
            dict(item) for item in accounts
            if isinstance(item, dict) and isinstance(item.get("id"), str)
            and item.get("enabled") is True
        ]
        live = {str(row["id"]) for row in self._accounts}
        self._cache = {key: value for key, value in self._cache.items() if key[0] in live}
        self._failures = {key for key in self._failures if key[0] in live}
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        self.account_combo.addItem(f"All accounts ({len(live)})", userData="__all__")
        labels = account_player_names(self._accounts)
        for item in self._accounts:
            label = labels[str(item["id"])]
            world = str(item.get("world") or "")[:24]
            # Duplicate player names already include a world and account suffix.
            if world and f" · {world} (" not in label:
                label = f"{label} · {world}"
            self.account_combo.addItem(label, userData=item["id"])
        selection = self.account_combo.findData(prior)
        self.account_combo.setCurrentIndex(max(0, selection))
        self.account_combo.blockSignals(False)
        self._render()

    def selected_account_ids(self) -> list[str]:
        selected = self.account_combo.currentData()
        if selected == "__all__":
            return [str(item["id"]) for item in self._accounts]
        return [selected] if selected in {
            str(item["id"]) for item in self._accounts
        } else []

    def select_account(self, account_id: str) -> None:
        index = self.account_combo.findData(account_id)
        if index >= 0:
            self.account_combo.setCurrentIndex(index)

    def reset_backend_context(self) -> None:
        """Never reuse data from another URL, session or account roster."""
        self._cache.clear()
        self._failures.clear()
        self._render()

    def _select_mode(self, index: int) -> None:
        self._mode = self._MODES[index]
        self.tabs.setCurrentItem(self._mode)
        self.stack.setCurrentIndex(index)
        self._render()

    def refresh(self) -> None:
        ids = self.selected_account_ids()
        if not ids:
            self.status.setText("No enabled accounts. Configure an account first.")
            return
        request_kind = "military_overview" if self._mode != "movements" else "military_movements"
        self._failures.difference_update({(aid, request_kind) for aid in ids})
        for aid in ids:
            self._cache.pop((aid, request_kind), None)
        self.status.setText(f"Refreshing {len(ids)} account(s) from authenticated game sessions…")
        self._render(preserve_pending=True)
        self.refresh_requested.emit(ids, request_kind)

    def set_result(self, account_id: str, kind: str, result: dict[str, object]) -> None:
        if account_id not in {str(a["id"]) for a in self._accounts}:
            return
        if kind not in {"military_overview", "military_movements"}:
            return
        if result.get("account_id") != account_id:
            return
        self._cache[(account_id, kind)] = result
        self._failures.discard((account_id, kind))
        self._render()

    def set_unavailable(self, account_id: str, kind: str) -> None:
        if account_id not in {str(a["id"]) for a in self._accounts}:
            return
        self._cache.pop((account_id, kind), None)
        self._failures.add((account_id, kind))
        self._render()

    def _render(self, *_args: object, preserve_pending: bool = False) -> None:
        labels = account_player_names(self._accounts)
        selected = self.selected_account_ids()
        kind = "military_movements" if self._mode == "movements" else "military_overview"
        loaded = [aid for aid in selected if (aid, kind) in self._cache]
        failed = [aid for aid in selected if (aid, kind) in self._failures]
        rows: list[list[object]] = []
        headline = {"troops": "Troops by city", "fleet": "Ships by city",
                    "movements": "Current movements"}[self._mode]
        self.headline.setText(headline)
        for aid in loaded:
            data = self._cache[(aid, kind)]
            if self._mode != "movements":
                for city in data.get("cities", []):
                    for unit in city.get(self._mode, []):
                        rows.append([
                            labels[aid], city["city_name"], unit["unit"],
                            f'{unit["amount"]:,}',
                        ])
            else:
                for movement in data.get("movements", []):
                    status = ("Hostile · " if movement["hostile"] else "")
                    status += ("Returning · " if movement["returning"] else "")
                    status += movement["mission"] or "Unknown mission"
                    remaining = int(movement["seconds_remaining"])
                    eta = (f"{remaining // 3600}h {(remaining // 60) % 60}m"
                           if remaining >= 60 else f"{remaining}s")
                    rows.append([
                        labels[aid],
                        movement["origin"], movement["destination"],
                        status, eta,
                        f'{movement["troops"]:,}', f'{movement["ships"]:,}',
                    ])
        table = self.tables[self._MODES.index(self._mode)]
        table.setSortingEnabled(False)
        _populate(table, rows)
        table.setSortingEnabled(True)
        if selected:
            suffix = (f"{len(loaded)}/{len(selected)} accounts loaded"
                      + (f", {len(failed)} unavailable" if failed else ""))
            if rows:
                self.status.setText(f"{len(rows)} {self._mode} entries · {suffix}.")
            elif loaded:
                self.status.setText(
                    f"No {self._mode} reported for loaded accounts · {suffix}. "
                    "Accounts not yet loaded are unknown, not zero."
                )
            elif not preserve_pending:
                self.status.setText(
                    f"Refresh to load {len(selected)} account(s)"
                    + ("; a previous read was unavailable." if failed else ".")
                )
        else:
            self.status.setText("No enabled accounts are configured.")
        self.refresh_button.setEnabled(bool(selected))
