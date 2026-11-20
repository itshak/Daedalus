"""Account-bound native editors for reviewed IkaBot operation parameters.

These widgets never send game requests or make up IDs/quantities. Their
constructors are empty until a verified city snapshot is supplied. The
controller and existing-session IkaBot planner independently revalidate the
result before starting any task.
"""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import ComboBox, PushButton, SpinBox

_RESOURCES = ("Wood", "Wine", "Marble", "Crystal", "Sulfur")
_MAX_AMOUNT = 1_000_000_000


def _table(columns: tuple[str, ...]) -> QTableWidget:
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(list(columns))
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    return table


def _amount(*, minimum: int = 0, value: int = 0, label: str = "") -> SpinBox:
    field = SpinBox()
    field.setRange(minimum, _MAX_AMOUNT)
    field.setValue(value)
    field.setAccessibleName(label)
    field.setMinimumWidth(92)
    field.setToolTip(label)
    return field


def _city_picker(cities: list[dict[str, object]], label: str) -> ComboBox:
    picker = ComboBox()
    picker.setAccessibleName(label)
    picker.addItem("Choose a city")
    for city in cities:
        coords = str(city.get("coords") or "")
        title = str(city["name"])
        picker.addItem(f"{title} ({coords})" if coords else title, userData=city["id"])
    picker.setCurrentIndex(0)
    return picker


class ResourceLimitsEditor(QWidget):
    """The five IkaBot consolidateResources limits; -1 means keep *all*."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.values: list[SpinBox] = []
        for name in _RESOURCES:
            field = _amount(minimum=-1, value=-1, label=f"{name} to retain in every source city")
            field.setSpecialValueText("Keep all — do not send")
            field.valueChanged.connect(self.changed.emit)
            layout.addRow(name, field)
            self.values.append(field)

    def to_config(self) -> list[int]:
        result = [field.value() for field in self.values]
        if all(value == -1 for value in result):
            raise ValueError("Choose an amount to retain for at least one resource")
        return result


class ShipmentRoutesEditor(QWidget):
    """One or more account-local routes; destination outside the account requires expert import."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._cities: list[dict[str, object]] = []
        self._rows: list[tuple[ComboBox, ComboBox, list[SpinBox]]] = []
        self.table = _table(("From city", "To city", *_RESOURCES))
        self.table.setMinimumHeight(148)
        self.table.setAccessibleName("Account-local resource routes and five resource amounts")
        layout.addWidget(self.table)
        row = QHBoxLayout()
        self.add_button = PushButton("Add route")
        self.add_button.clicked.connect(self.add_route)
        self.remove_button = PushButton("Remove selected")
        self.remove_button.clicked.connect(self.remove_selected)
        row.addWidget(self.add_button)
        row.addWidget(self.remove_button)
        row.addStretch(1)
        layout.addLayout(row)
        note = QLabel("Only your own cities are shown. External destinations require "
                      "a separately verified island and destination city.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self._controls()

    def _controls(self) -> None:
        self.add_button.setEnabled(len(self._cities) >= 2 and len(self._rows) < 20)
        self.remove_button.setEnabled(bool(self._rows))

    def set_cities(self, cities: list[dict[str, object]]) -> None:
        # On account/session refresh the previous row IDs must be discarded.
        self.table.setRowCount(0)
        self._rows.clear()
        self._cities = list(cities)
        self._controls()
        self.changed.emit()

    def add_route(self) -> None:
        if len(self._cities) < 2 or len(self._rows) >= 20:
            return
        row = len(self._rows)
        self.table.insertRow(row)
        source = _city_picker(self._cities, f"Route {row + 1} source city")
        destination = _city_picker(self._cities, f"Route {row + 1} destination city")
        source.currentIndexChanged.connect(self.changed.emit)
        destination.currentIndexChanged.connect(self.changed.emit)
        self.table.setCellWidget(row, 0, source)
        self.table.setCellWidget(row, 1, destination)
        values = []
        for col, resource in enumerate(_RESOURCES, start=2):
            amount = _amount(label=f"Route {row + 1} {resource} to send")
            amount.valueChanged.connect(self.changed.emit)
            self.table.setCellWidget(row, col, amount)
            values.append(amount)
        self._rows.append((source, destination, values))
        self._controls()
        self.changed.emit()

    def remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        self._rows.pop(row)
        self.table.removeRow(row)
        self._controls()
        self.changed.emit()

    def to_config(self) -> list[dict[str, object]]:
        if not self._rows:
            raise ValueError("Add at least one shipment route between your cities")
        routes: list[dict[str, object]] = []
        ids = {city["id"] for city in self._cities}
        total: dict[int, list[int]] = {}
        for source, destination, fields in self._rows:
            origin = source.currentData(Qt.UserRole)
            target = destination.currentData(Qt.UserRole)
            if type(origin) is not int or origin not in ids:
                raise ValueError("Choose a verified source city for every route")
            if type(target) is not int or target not in ids:
                raise ValueError("Choose a verified destination city for every route")
            if origin == target:
                raise ValueError("A shipment cannot send resources to the same city")
            amounts = [field.value() for field in fields]
            if not any(amounts):
                raise ValueError("Enter a nonzero amount for every shipment")
            total[origin] = [x + y for x, y in zip(total.get(origin, [0] * 5), amounts)]
            if any(x > _MAX_AMOUNT for x in total[origin]):
                raise ValueError("Combined resource amount exceeds the safe limit")
            routes.append({"from": origin, "to": target, "resources": amounts})
        return routes


class DonationPoliciesEditor(QWidget):
    """Per-city island donation policies from IkaBot donationBot.prepare_*."""

    changed = Signal()

    _TYPE_CHOICES = (
        ("No donation", None),
        ("Forest (wood)", "resource"),
        ("Luxury resource", "tradegood"),
        ("Both island projects", "both"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = _table(("City", "Donate to", "Policy amount"))
        self.table.setMinimumHeight(145)
        self.table.setAccessibleName("City donation policies")
        layout.addWidget(self.table)
        note = QLabel("Policy amount means storage % to keep, production % to give, "
                      "or fixed quantity, depending on the donation method above.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self._rows: list[tuple[int, ComboBox, SpinBox]] = []

    def set_cities(self, cities: list[dict[str, object]]) -> None:
        self.table.setRowCount(0)
        self._rows.clear()
        for index, city in enumerate(cities[:100]):
            self.table.insertRow(index)
            city_label = QLabel(str(city["name"]))
            city_label.setAccessibleName(f"Donation city {city['name']}")
            self.table.setCellWidget(index, 0, city_label)
            kind = ComboBox()
            kind.setAccessibleName(f"Donation project for {city['name']}")
            for label, value in self._TYPE_CHOICES:
                kind.addItem(label, userData=value)
            kind.setCurrentIndex(0)
            amount = _amount(value=80, label=f"Donation policy amount for {city['name']}")
            amount.setRange(0, _MAX_AMOUNT)
            amount.setEnabled(False)
            kind.currentIndexChanged.connect(lambda _index, amount=amount, kind=kind:
                                             self._donation_choice_changed(kind, amount))
            amount.valueChanged.connect(self.changed.emit)
            self.table.setCellWidget(index, 1, kind)
            self.table.setCellWidget(index, 2, amount)
            self._rows.append((city["id"], kind, amount))
        self.changed.emit()

    def _donation_choice_changed(self, kind: ComboBox, amount: SpinBox) -> None:
        amount.setEnabled(kind.currentIndex() != 0)
        self.changed.emit()

    def update_method(self, method: int) -> None:
        default = {1: 80, 2: 50, 3: 10000}.get(method, 80)
        upper = 100 if method in (1, 2) else _MAX_AMOUNT
        for _city_id, _kind, amount in self._rows:
            amount.setRange(0, upper)
            amount.setValue(default)
        self.changed.emit()

    def to_config(self, method: int) -> dict[str, dict[str, object]]:
        if method not in (1, 2, 3):
            raise ValueError("Choose a supported donation policy")
        result: dict[str, dict[str, object]] = {}
        for city_id, kind, amount in self._rows:
            value = kind.currentData(Qt.UserRole)
            if value is None:
                continue
            if method in (1, 2) and amount.value() > 100:
                raise ValueError("Percentage cannot exceed 100")
            result[str(city_id)] = {"donation_type": value, "percentage": amount.value()}
        if not result:
            raise ValueError("Choose at least one city and donation project")
        return result


class ResourceAmountsEditor(QWidget):
    """Five engine resource_config values with None = omit the resource."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.values: list[SpinBox] = []
        for name in _RESOURCES:
            value = _amount(minimum=-1, value=-1, label=f"{name} shipping policy amount")
            value.setSpecialValueText("Ignore resource")
            value.valueChanged.connect(self.changed.emit)
            layout.addRow(name, value)
            self.values.append(value)

    def to_config(self, *, ignore_allowed: bool = True) -> list[int | None]:
        values = [field.value() for field in self.values]
        if ignore_allowed:
            result = [None if value == -1 else value for value in values]
        else:
            result = [0 if value == -1 else value for value in values]
        if ignore_allowed and all(value is None for value in result):
            raise ValueError("Select at least one resource to retain or send")
        if not ignore_allowed and not any(value > 0 for value in result):
            raise ValueError("Enter a positive resource amount to send")
        return result


class MapAreaEditor(QWidget):
    """Optional bounded world-map center and radius, no raw coordinate JSON."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from qfluentwidgets import CheckBox

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.enabled = CheckBox("Limit scan to area")
        self.enabled.stateChanged.connect(self._toggle)
        layout.addWidget(self.enabled)
        self.x = _amount(label="Island map X coordinate")
        self.y = _amount(label="Island map Y coordinate")
        self.radius = _amount(value=15, label="Island map radius")
        for label, field, maximum in (("X", self.x, 100), ("Y", self.y, 100),
                                      ("Radius", self.radius, 200)):
            field.setMaximum(maximum)
            field.valueChanged.connect(self.changed.emit)
            layout.addWidget(QLabel(label))
            layout.addWidget(field)
        self._toggle()

    def _toggle(self, *_args: object) -> None:
        active = self.enabled.isChecked()
        for widget in (self.x, self.y, self.radius):
            widget.setEnabled(active)
        self.changed.emit()

    def to_config(self) -> tuple[list[int], int] | None:
        if not self.enabled.isChecked():
            return None
        return [self.x.value(), self.y.value()], self.radius.value()


class WorkshopUpgradesEditor(QWidget):
    """Real workshop units and target levels, collected from IkaBot view data."""

    changed = Signal()
    city_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        city_row = QHBoxLayout()
        city_row.addWidget(QLabel("City with a workshop"))
        self.city_picker = ComboBox()
        self.city_picker.setAccessibleName("Choose the actual workshop city")
        self.city_picker.currentIndexChanged.connect(self._select_city)
        city_row.addWidget(self.city_picker, 1)
        layout.addLayout(city_row)
        self.table = _table(("Upgrade", "Unit", "Type", "Current level", "Target level"))
        self.table.setMinimumHeight(210)
        self.table.setAccessibleName("Verified unit upgrade targets")
        self.table.itemChanged.connect(self.changed.emit)
        layout.addWidget(self.table)
        self.description = QLabel("Choose an account city to read its actual workshop upgrades.")
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self._scope_city_id: int | None = None
        self._loaded_city_id: int | None = None
        self._units: list[dict[str, object]] = []
        self.set_cities([])

    def set_cities(self, cities: list[dict[str, object]]) -> None:
        self._scope_city_id = None
        self._loaded_city_id = None
        self._units = []
        self.table.setRowCount(0)
        with QSignalBlocker(self.city_picker):
            self.city_picker.clear()
            self.city_picker.addItem("Choose a verified city")
            for city in cities:
                name = str(city["name"])
                coords = str(city.get("coords") or "")
                self.city_picker.addItem(
                    f"{name} ({coords})" if coords else name,
                    userData=city["id"],
                )
            self.city_picker.setCurrentIndex(0)
        self.description.setText("Choose a city; IkaBot will list only existing workshop upgrades.")
        self.changed.emit()

    def _select_city(self, *_args: object) -> None:
        self.table.setRowCount(0)
        self._units = []
        self._loaded_city_id = None
        city_id = self.city_picker.currentData(Qt.UserRole)
        self._scope_city_id = city_id if type(city_id) is int else None
        self.description.setText(
            "Reading actual workshop unit levels…" if self._scope_city_id else
            "Choose an actual city to see its workshop."
        )
        self.changed.emit()
        if self._scope_city_id:
            self.city_requested.emit(self._scope_city_id)

    def set_workshop_data(self, city_id: int, choices: list[dict[str, object]],
                          workshop_level: int) -> None:
        if city_id != self._scope_city_id:
            return
        self._loaded_city_id = city_id
        self._units = list(choices)
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(self._units))
            for row, unit in enumerate(self._units):
                current = unit["current_level"]
                maximum = unit["max_level"]
                choice = QTableWidgetItem("")
                choice.setData(Qt.UserRole, (unit["unit_id"], unit["upgrade_type"]))
                choice.setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
                    if current < maximum else Qt.ItemIsEnabled
                )
                choice.setCheckState(Qt.Unchecked)
                self.table.setItem(row, 0, choice)
                for column, value in (
                    (1, unit["name"]), (2, unit["description"]),
                    (3, current),
                ):
                    label = QTableWidgetItem(str(value))
                    label.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row, column, label)
                target = _amount(
                    minimum=current, value=current,
                    label=f"Target {unit['name']} {unit['description']} level",
                )
                target.setMaximum(maximum)
                target.setEnabled(current < maximum)
                target.valueChanged.connect(self.changed.emit)
                self.table.setCellWidget(row, 4, target)
        self.description.setText(
            f"{len(choices)} actual upgrade options loaded. Workshop level {workshop_level}. "
            "Select units and target levels. IkaBot checks workshop eligibility again at launch."
        )
        self.changed.emit()

    def set_unavailable(self, city_id: int) -> None:
        if city_id != self._scope_city_id:
            return
        self._loaded_city_id = None
        self._units = []
        self.table.setRowCount(0)
        self.description.setText(
            "No verified workshop information for this city. "
            "Reconnect the account or choose another city."
        )
        self.changed.emit()

    def to_config(self) -> list[dict[str, object]]:
        city_id = self._scope_city_id
        if city_id is None or self._loaded_city_id != city_id:
            raise ValueError("Choose a workshop city and load its verified unit levels")
        jobs = []
        for row, unit in enumerate(self._units):
            cell = self.table.item(row, 0)
            if cell is None or cell.checkState() != Qt.Checked:
                continue
            target = self.table.cellWidget(row, 4)
            if not isinstance(target, SpinBox) or not target.isEnabled():
                raise ValueError("Chosen workshop upgrade is unavailable")
            if not unit["current_level"] < target.value() <= unit["max_level"]:
                raise ValueError("Choose a higher target level for each unit")
            jobs.append({
                "unitId": unit["unit_id"],
                "upgradeType": unit["upgrade_type"], "target": target.value(),
            })
        if not 0 < len(jobs) <= 50:
            raise ValueError("Select 1 to 50 actual unit upgrades")
        return [{"city_id": city_id, "upgrades": jobs}]


class TrainableUnitsEditor(QWidget):
    """Actual barracks/shipyard catalog and quantity plan, without raw JSON."""

    changed = Signal()
    city_requested = Signal(int, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        selector = QHBoxLayout()
        selector.addWidget(QLabel("Recruit"))
        self.mode = ComboBox()
        self.mode.addItems(["Land units", "Warships"])
        self.mode.setAccessibleName("Training: troops or ships")
        self.mode.setCurrentIndex(0)
        self.mode.currentIndexChanged.connect(self._reset_selection)
        selector.addWidget(self.mode)
        selector.addWidget(QLabel("In city"))
        self.city_picker = ComboBox()
        self.city_picker.setAccessibleName("Choose barracks or shipyard city")
        self.city_picker.currentIndexChanged.connect(self._reset_selection)
        selector.addWidget(self.city_picker, 1)
        layout.addLayout(selector)
        self.table = _table(("Unit", "Real per-unit costs", "Quantity"))
        self.table.setMinimumHeight(240)
        self.table.setAccessibleName("Available recruitable units and quantities")
        layout.addWidget(self.table)
        self.description = QLabel(
            "Choose a city and training mode to load actual IkaBot unit options."
        )
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self._selected: tuple[int, bool] | None = None
        self._loaded: tuple[int, bool] | None = None
        self._snapshot: dict[str, object] | None = None
        self.set_cities([])

    def set_cities(self, cities: list[dict[str, object]]) -> None:
        self._selected = None
        self._loaded = None
        self._snapshot = None
        self.table.setRowCount(0)
        with QSignalBlocker(self.city_picker):
            self.city_picker.clear()
            self.city_picker.addItem("Choose verified city")
            for city in cities:
                coords = str(city.get("coords") or "")
                text = str(city["name"])
                self.city_picker.addItem(
                    f"{text} ({coords})" if coords else text, userData=city["id"]
                )
            self.city_picker.setCurrentIndex(0)
        self.description.setText("Choose a city with barracks or a shipyard.")
        self.changed.emit()

    def _reset_selection(self, *_args: object) -> None:
        self._loaded = None
        self._snapshot = None
        self.table.setRowCount(0)
        city_id = self.city_picker.currentData(Qt.UserRole)
        train_troops = self.mode.currentIndex() == 0
        self._selected = (city_id, train_troops) if type(city_id) is int else None
        self.description.setText(
            "Reading live recruiting options from the game…" if self._selected else
            "Choose a city with barracks or a shipyard."
        )
        self.changed.emit()
        if self._selected is not None:
            self.city_requested.emit(*self._selected)

    def set_trainables(self, snapshot: dict[str, object]) -> None:
        scope = (snapshot.get("city_id"), snapshot.get("train_troops"))
        if scope != self._selected:
            return
        units = snapshot.get("units")
        if not isinstance(units, list):
            return
        self._snapshot = snapshot
        self._loaded = self._selected
        self.table.setRowCount(len(units))
        for row, unit in enumerate(units):
            name = QTableWidgetItem(str(unit["local_name"]))
            name.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 0, name)
            costs = unit.get("costs", {})
            price = ", ".join(
                f"{key.capitalize()} {value:g}" for key, value in costs.items()
                if isinstance(value, (int, float)) and value > 0
            )
            price_cell = QTableWidgetItem(price or "No listed cost")
            price_cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 1, price_cell)
            quantity = _amount(label=f"Train {unit['local_name']} quantity")
            quantity.setMaximum(100000)
            quantity.valueChanged.connect(self.changed.emit)
            self.table.setCellWidget(row, 2, quantity)
        self.description.setText(
            f"{len(units)} actual unit types. "
            f"Free citizens: {snapshot['free_citizens']:,}. "
            "Costs are from this game's unit catalog and revalidated at launch."
        )
        self.changed.emit()

    def set_unavailable(self, city_id: int, train_troops: bool) -> None:
        if self._selected != (city_id, train_troops):
            return
        self._loaded = None
        self._snapshot = None
        self.table.setRowCount(0)
        self.description.setText(
            "No verified recruitable units for this city and fleet type. "
            "Check the game session, barracks or shipyard."
        )
        self.changed.emit()

    def to_config(self) -> dict[str, object]:
        if self._snapshot is None or self._loaded != self._selected:
            raise ValueError("Choose a city and load its actual recruitable units")
        units = self._snapshot["units"]
        selected = []
        spent: dict[str, float] = {key: 0 for key in (
            "wood", "wine", "marble", "crystal", "sulfur", "citizens",
        )}
        for row, unit in enumerate(units):
            quantity = self.table.cellWidget(row, 2)
            if not isinstance(quantity, SpinBox):
                raise TypeError("Training quantities unavailable")
            amount = quantity.value()
            if amount == 0:
                continue
            selected.append({"unit_type_id": unit["unit_type_id"], "cantidad": amount})
            for resource in spent:
                spent[resource] += unit["costs"].get(resource, 0) * amount
        if not 0 < len(selected) <= 50:
            raise ValueError("Enter a positive quantity for at least one actual unit")
        stocks = [*self._snapshot["available"], self._snapshot["free_citizens"]]
        for resource, amount in zip(spent, stocks):
            if spent[resource] > amount:
                raise ValueError(
                    f"Not enough {resource} in the selected city for this training plan"
                )
        return {
            "city": dict(self._snapshot["city"]),
            "tranings": [selected], "trainTroops": self._snapshot["train_troops"],
            "replicate": "n", "countRepeat": 0,
            "cityTrainings": [], "units": [],
        }


class MarketOffersEditor(QWidget):
    """Live IkaBot market offer selection and safe listing-price form."""

    changed = Signal()
    market_requested = Signal(int, int, str)

    def __init__(self, parent: QWidget | None = None, *, buying: bool) -> None:
        super().__init__(parent)
        self._buying = buying
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        selectors = QHBoxLayout()
        selectors.addWidget(QLabel("Trading-post city"))
        self.city_picker = ComboBox()
        self.city_picker.setAccessibleName("Market city")
        selectors.addWidget(self.city_picker, 2)
        selectors.addWidget(QLabel("Resource"))
        self.resource = ComboBox()
        for name in _RESOURCES:
            self.resource.addItem(name)
        self.resource.setCurrentIndex(0)
        self.resource.setAccessibleName("Market resource")
        selectors.addWidget(self.resource, 1)
        self.mode = ComboBox()
        if buying:
            self.mode.addItem("Buy from existing offers")
        else:
            self.mode.addItems(["Sell to existing buyers", "Create a market offer"])
        self.mode.setAccessibleName("Market transaction type")
        selectors.addWidget(self.mode, 1)
        layout.addLayout(selectors)
        self.table = _table(("Choose", "Market city", "Player", "Available", "Gold per unit"))
        self.table.setMinimumHeight(210)
        self.table.setAccessibleName("Source-verified live market quotes")
        self.table.itemChanged.connect(self.changed.emit)
        layout.addWidget(self.table)
        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Quantity"))
        self.amount = _amount(minimum=1, value=1, label="Total resource quantity to trade")
        self.amount.valueChanged.connect(self.changed.emit)
        bottom.addWidget(self.amount)
        bottom.addWidget(QLabel("Offer price"))
        self.price = _amount(minimum=1, value=1, label="Gold per resource for new listing")
        self.price.valueChanged.connect(self.changed.emit)
        self.price.setEnabled(False)
        bottom.addWidget(self.price)
        bottom.addStretch(1)
        layout.addLayout(bottom)
        self.description = QLabel("Choose a city and resource; market quotes come from IkaBot.")
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self._selected: tuple[int, int, str] | None = None
        self._loaded: tuple[int, int, str] | None = None
        self._snapshot: dict[str, object] | None = None
        self._offers: list[object] = []
        self.city_picker.currentIndexChanged.connect(self._refresh_selection)
        self.resource.currentIndexChanged.connect(self._refresh_selection)
        self.mode.currentIndexChanged.connect(self._refresh_selection)
        self.set_cities([])

    def set_cities(self, cities: list[dict[str, object]]) -> None:
        self._selected = None
        self._loaded = None
        self._snapshot = None
        self._offers = []
        self.table.setRowCount(0)
        with QSignalBlocker(self.city_picker):
            self.city_picker.clear()
            self.city_picker.addItem("Choose a city")
            for city in cities:
                coords = str(city.get("coords") or "")
                name = str(city["name"])
                self.city_picker.addItem(
                    f"{name} ({coords})" if coords else name, userData=city["id"]
                )
            self.city_picker.setCurrentIndex(0)
        self.description.setText(
            "Choose an actual account city with a trading post to load offers."
        )
        self.price.setEnabled(False)
        self.changed.emit()

    def _refresh_selection(self, *_args: object) -> None:
        self._loaded = None
        self._snapshot = None
        self._offers = []
        self.table.setRowCount(0)
        city_id = self.city_picker.currentData(Qt.UserRole)
        resource_type = self.resource.currentIndex()
        side = ("buy" if self._buying else
                "sell_to_offers" if self.mode.currentIndex() == 0 else "create_offer")
        self._selected = (
            (city_id, resource_type, side)
            if type(city_id) is int and 0 <= resource_type <= 4 else None
        )
        self.price.setEnabled(False)
        self.description.setText(
            "Loading actual IkaBot marketplace offers or price bounds…"
            if self._selected else "Choose a real city with a trading post."
        )
        self.changed.emit()
        if self._selected is not None:
            self.market_requested.emit(*self._selected)

    def set_quotes(self, snapshot: dict[str, object]) -> None:
        scope = (
            snapshot.get("city_id"), snapshot.get("resource_type"), snapshot.get("side")
        )
        if scope != self._selected:
            return
        offers = snapshot.get("offers")
        if not isinstance(offers, list):
            return
        self._loaded = self._selected
        self._snapshot = snapshot
        self._offers = list(offers)
        listing = scope[2] == "create_offer"
        self.table.setVisible(not listing)
        self.price.setVisible(listing)
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(self._offers))
            for row, offer in enumerate(self._offers):
                if isinstance(offer, dict):
                    city_name, player = offer["ciudadDestino"], offer["jugadorAComprar"]
                    amount, price = offer["amountAvailable"], offer["precio"]
                else:
                    city_name, player, amount, price = offer[:4]
                checkbox = QTableWidgetItem("")
                checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                checkbox.setCheckState(Qt.Unchecked)
                self.table.setItem(row, 0, checkbox)
                for column, value in (
                    (1, city_name), (2, player), (3, f"{amount:,}"), (4, f"{price:,}")
                ):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row, column, item)
        if listing:
            lower, upper = snapshot["price_min"], snapshot["price_max"]
            self.price.setRange(lower, upper)
            self.price.setValue(lower)
            self.price.setEnabled(True)
            self.description.setText(
                f"Current allowed price: {lower:,}–{upper:,} gold per unit. "
                f"Own stock: {snapshot['city']['availableResources'][scope[1]]:,}. "
                f"Already offered: {snapshot['currently_on_sale']:,}; "
                f"market capacity: {snapshot['sell_market_capacity']:,}."
            )
        else:
            self.description.setText(
                f"{len(self._offers)} actual offers. Select sellers/buyers and a quantity. "
                "Prices are rechecked by IkaBot before execution."
            )
        self.changed.emit()

    def set_unavailable(self, city_id: int, resource_type: int, side: str) -> None:
        if self._selected != (city_id, resource_type, side):
            return
        self._snapshot = None
        self._loaded = None
        self._offers.clear()
        self.table.setRowCount(0)
        self.price.setEnabled(False)
        self.description.setText(
            "Authenticated market data is unavailable for this city/resource. "
            "No transaction has been prepared."
        )
        self.changed.emit()

    def to_config(self) -> dict[str, object]:
        if self._snapshot is None or self._loaded != self._selected:
            raise ValueError("Choose a trading-post city and load real market offers")
        _city, resource_type, side = self._loaded
        snapshot = self._snapshot
        amount = self.amount.value()
        if side == "create_offer":
            stock = snapshot["city"]["availableResources"][resource_type]
            if amount > stock:
                raise ValueError("Selling quantity exceeds actual city stock")
            price = self.price.value()
            if not snapshot["price_min"] <= price <= snapshot["price_max"]:
                raise ValueError("The new offer price is outside the market's allowed range")
            return {
                "mode": "create_offer", "amount_to_sell": amount,
                "price": price, "resource_type": resource_type,
                "sell_market_capacity": snapshot["sell_market_capacity"],
                "city": snapshot["city"],
            }
        chosen = [
            self._offers[row] for row in range(len(self._offers))
            if self.table.item(row, 0) is not None
            and self.table.item(row, 0).checkState() == Qt.Checked
        ]
        if not 0 < len(chosen) <= 50:
            raise ValueError("Select 1 to 50 actual market quotes")
        if side == "buy":
            available = sum(offer["amountAvailable"] for offer in chosen)
            if amount > available:
                raise ValueError("Buying quantity exceeds selected live offers")
            return {"city": snapshot["city"], "offers": chosen, "amount_to_buy": amount}
        available = min(
            snapshot["city"]["availableResources"][resource_type],
            sum(offer[2] for offer in chosen),
        )
        if amount > available:
            raise ValueError("Selling quantity exceeds actual stock or buyer offers")
        return {
            "mode": "sell_to_offers", "amount_to_sell": amount,
            "offers": chosen, "resource_type": resource_type,
            "city_to_buy_from": snapshot["city"],
        }


class AcademyResearchEditor(QWidget):
    """Owned academies, current crystal/cooldown and experiment mode controls."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = _table((
            "Use", "Academy city", "Crystal on hand", "Cooldown", "Ready now",
        ))
        self.table.setMinimumHeight(195)
        self.table.setAccessibleName("Actual academy research eligibility table")
        self.table.itemChanged.connect(self.changed.emit)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        row.addWidget(QLabel("Experiments"))
        self.count = _amount(label="Number of crystal experiments in one city")
        self.count.setRange(0, 10000)
        self.count.setValue(0)
        self.count.setSpecialValueText("Automatic (all selected cities)")
        self.count.valueChanged.connect(self.changed.emit)
        row.addWidget(self.count)
        row.addStretch(1)
        layout.addLayout(row)
        self.description = QLabel(
            "Loading current academy and crystal information; no experiments started."
        )
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self._academies: list[dict[str, object]] | None = None

    def set_academies(self, academies: list[dict[str, object]]) -> None:
        self._academies = list(academies)
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(academies))
            for row, academy in enumerate(academies):
                checkbox = QTableWidgetItem("")
                checkbox.setData(Qt.UserRole, academy["city_id"])
                checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                checkbox.setCheckState(Qt.Unchecked)
                self.table.setItem(row, 0, checkbox)
                for col, value in (
                    (1, academy["city_name"]),
                    (2, f'{academy["crystal"]:,}'),
                    (3, "Cooling down" if academy["cooldown"] else "None"),
                    (4, "Yes" if academy["can_experiment_now"] else "Not yet"),
                ):
                    cell = QTableWidgetItem(str(value))
                    cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row, col, cell)
        self.description.setText(
            f"{len(academies)} verified academy cities. Each experiment needs at "
            "least 300,000 crystal and has an approximately four-hour cooldown. "
            "Manual experiments use exactly one city; automatic can use several."
        )
        self.changed.emit()

    def set_unavailable(self) -> None:
        self._academies = None
        self.table.setRowCount(0)
        self.description.setText(
            "Academy information is unavailable for this account. "
            "No research settings can be reviewed yet."
        )
        self.changed.emit()

    def to_config(self) -> dict[str, object]:
        if self._academies is None:
            raise ValueError("Load actual academies for the selected account")
        chosen = [
            self._academies[row] for row in range(len(self._academies))
            if self.table.item(row, 0) is not None
            and self.table.item(row, 0).checkState() == Qt.Checked
        ]
        if not chosen:
            raise ValueError("Choose at least one real academy")
        count = self.count.value()
        if count > 0 and len(chosen) != 1:
            raise ValueError("Fixed experiment counts require exactly one academy")
        if count > 0 and chosen[0]["crystal"] < 300000:
            raise ValueError("A manual experiment requires at least 300,000 crystal")
        return {
            "cities_ids": [str(row["city_id"]) for row in chosen],
            "qty": count if count > 0 else None,
        }
