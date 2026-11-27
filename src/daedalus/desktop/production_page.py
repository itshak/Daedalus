"""Read-only, globally scoped production inventory workspace."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ComboBox, PrimaryPushButton

from daedalus.account_display import account_player_names
from daedalus.desktop.design_system import PageHeading
from daedalus.desktop.pages import _populate, _table
from daedalus.production_inventory import validate_production_inventory


class ProductionPage(QWidget):
    refresh_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("production_page")
        self._accounts = {}
        self._cities = {}
        self._results = {}
        self._unavailable = set()
        self._loading = False
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
        self.resource_combo.currentIndexChanged.connect(self._render)
        toolbar.addWidget(self.resource_combo, 1)
        self.refresh_button = PrimaryPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_button)
        layout.addLayout(toolbar)
        self.status = CaptionLabel("Read-only · Assignment controls are not enabled yet.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = _table(["Account", "City", "Resource", "Current", "Normal capacity",
                             "Extra capacity", "Free citizens"])
        self.table.setAccessibleName("Production workforce inventory")
        layout.addWidget(self.table, 1)

    def set_accounts(self, accounts):
        self._accounts = {row["id"]: dict(row) for row in accounts if isinstance(row.get("id"), str)}
        self._cities.clear()
        self._results.clear()
        self._unavailable.clear()
        self.finish_refresh()
        self._render()

    def refresh(self):
        if self._loading:
            return
        self._loading = True
        self.refresh_button.setEnabled(False)
        self._cities.clear()
        self._results.clear()
        self._unavailable = {(aid, None) for aid, row in self._accounts.items() if row.get("enabled") is not True}
        self._render()
        self.refresh_requested.emit(self.eligible_ids())

    def finish_refresh(self):
        self._loading = False
        self.refresh_button.setEnabled(True)

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
        self.status.setText(f"{len(self._results)} city observations · Read-only; unknown values are not zero.")
