"""Account-bound native editors for reviewed IkaBot operation parameters.

These widgets never send game requests or make up IDs/quantities. Their
constructors are empty until a verified city snapshot is supplied. The
controller and existing-session IkaBot planner independently revalidate the
result before starting any task.
"""

from __future__ import annotations

import uuid

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CheckBox, ComboBox, PushButton, SpinBox

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
    """Owned origins and verified owned or external destination choices."""

    changed = Signal()
    lookup_requested = Signal(int, int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._cities: list[dict[str, object]] = []
        self._external: list[dict[str, object]] = []
        self._lookup_nonce: str | None = None
        self._lookup_coords: tuple[int, int] | None = None
        search = QHBoxLayout()
        self.x = _amount(minimum=1, value=1, label="Island X coordinate")
        self.y = _amount(minimum=1, value=1, label="Island Y coordinate")
        for label, field in (("Island X", self.x), ("Y", self.y)):
            field.setMaximum(100)
            search.addWidget(QLabel(label))
            search.addWidget(field)
            field.valueChanged.connect(self._cancel_lookup)
        self.lookup_button = PushButton("Find external cities")
        self.lookup_button.clicked.connect(self._lookup)
        search.addWidget(self.lookup_button)
        self.clear_external_button = PushButton("Clear external cities")
        self.clear_external_button.clicked.connect(self._invalidate_external)
        search.addWidget(self.clear_external_button)
        layout.addLayout(search)
        self.lookup_note = QLabel("Optional: find another player's city by island coordinates.")
        self.lookup_note.setWordWrap(True)
        layout.addWidget(self.lookup_note)
        self._rows: list[tuple[ComboBox, ComboBox, list[SpinBox]]] = []
        self.table = _table(("From city", "To city", *_RESOURCES))
        self.table.setMinimumHeight(148)
        self.table.setAccessibleName("Resource routes and five resource amounts")
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
        note = QLabel("External recipients are verified again before sending. External shipments require manual recovery.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self._controls()

    def _controls(self) -> None:
        self.add_button.setEnabled(bool(self._cities) and (len(self._cities) >= 2 or bool(self._external)) and len(self._rows) < 20)
        self.remove_button.setEnabled(bool(self._rows))
        self.lookup_button.setEnabled(bool(self._cities))
        self.clear_external_button.setEnabled(bool(self._external))

    def set_cities(self, cities: list[dict[str, object]]) -> None:
        # On account/session refresh the previous row IDs must be discarded.
        self.table.setRowCount(0)
        self._rows.clear()
        self._cities = list(cities)
        self._invalidate_external()
        self._controls()
        self.changed.emit()

    def add_route(self) -> None:
        if not self._cities or (len(self._cities) < 2 and not self._external) or len(self._rows) >= 20:
            return
        row = len(self._rows)
        self.table.insertRow(row)
        source = _city_picker(self._cities, f"Route {row + 1} source city")
        destination = _city_picker(self._destination_choices(), f"Route {row + 1} destination city")
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
        external = {row["id"]: row for row in self._external}
        ids = {city["id"] for city in self._cities}
        total: dict[int, list[int]] = {}
        for source, destination, fields in self._rows:
            origin = source.currentData()
            target = destination.currentData()
            if type(origin) is not int or origin not in ids:
                raise ValueError("Choose a verified source city for every route")
            if type(target) is not int or (target not in ids and target not in external):
                raise ValueError("Choose a verified destination city for every route")
            if origin == target:
                raise ValueError("A shipment cannot send resources to the same city")
            amounts = [field.value() for field in fields]
            if not any(amounts):
                raise ValueError("Enter a nonzero amount for every shipment")
            total[origin] = [x + y for x, y in zip(total.get(origin, [0] * 5), amounts)]
            if any(x > _MAX_AMOUNT for x in total[origin]):
                raise ValueError("Combined resource amount exceeds the safe limit")
            route = {"from": origin, "to": target, "resources": amounts}
            if target not in ids:
                route.update(island=external[target]["island"], recipient=external[target]["recipient"])
            routes.append(route)
        return routes

    def _destination_choices(self):
        return self._cities + [
            {"id": row["id"], "name": f"{row['name']} — {row['owner']}",
             "coords": row["coords"]}
            for row in self._external if row["id"] not in {c["id"] for c in self._cities}
        ]

    def _refresh_destinations(self):
        choices = self._destination_choices()
        for _, picker, _ in self._rows:
            current = picker.currentData()
            with QSignalBlocker(picker):
                picker.clear()
                picker.addItem("Choose a city")
                for city in choices:
                    title = str(city["name"])
                    coords = str(city.get("coords") or "")
                    picker.addItem(f"{title} ({coords})" if coords else title, userData=city["id"])
                picker.setCurrentIndex(next((i+1 for i,c in enumerate(choices) if c["id"] == current), 0))
        self._controls()
        self.changed.emit()

    def _cancel_lookup(self, *_args):
        self._lookup_nonce = None
        self._lookup_coords = None
        self.lookup_note.setText("Search another island; verified destinations remain available until refreshed or cleared.")

    def _invalidate_external(self, *_args):
        self._lookup_nonce = None
        self._lookup_coords = None
        self._external = []
        self.lookup_note.setText("Optional: find another player's city by island coordinates.")
        self._refresh_destinations()

    def _lookup(self):
        self._cancel_lookup()
        coords = f"{self.x.value()}:{self.y.value()}"
        # A refreshed island must be selected again. Other island drafts survive.
        self._external = [r for r in self._external if r["coords"] != coords]
        if len({r["coords"] for r in self._external}) >= 10:
            self.lookup_note.setText("Clear external cities before searching more than ten islands.")
            self._refresh_destinations()
            return
        self._refresh_destinations()
        self._lookup_nonce = str(uuid.uuid4())
        self._lookup_coords = (self.x.value(), self.y.value())
        self.lookup_note.setText("Looking up cities on the selected island…")
        self.lookup_requested.emit(*self._lookup_coords, self._lookup_nonce)

    def set_external(self, result, nonce):
        if nonce != self._lookup_nonce or self._lookup_coords != (result.get("x"), result.get("y")):
            return
        self._lookup_nonce = None
        owned = {c["id"] for c in self._cities}
        coords = f"{result['x']}:{result['y']}"
        rows = [{**r, "coords": coords} for r in result["cities"] if r["id"] not in owned]
        # If a city appears at a different island, never silently retarget an
        # existing route; remove the old selection before adding the new record.
        found = {r["id"] for r in rows}
        self._external = [r for r in self._external if r["id"] not in found]
        self._refresh_destinations()
        self._external.extend(rows)
        self.lookup_note.setText(f"{len(self._external)} eligible external cities across searched islands. Choose a destination in each route.")
        self._refresh_destinations()

    def lookup_failed(self, nonce):
        if nonce == self._lookup_nonce:
            self._lookup_nonce = None
            self.lookup_note.setText("Island lookup unavailable. Check coordinates and retry.")

    def summary(self):
        self.to_config()
        return "\n".join(
            source.currentText() + " → " + dest.currentText() + ": " +
            ", ".join(f"{name} {field.value():,}" for name, field in zip(_RESOURCES, fields) if field.value())
            for source, dest, fields in self._rows
        )


class ExternalDestinationEditor(QWidget):
    """A single receiving city, optionally verified on another player's island."""

    changed = Signal()
    lookup_requested = Signal(int, int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cities = []
        self._external = []
        self._nonce = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.picker = _city_picker([], "Receiving city")
        self.picker.currentIndexChanged.connect(self.changed.emit)
        layout.addWidget(self.picker)
        search = QHBoxLayout()
        self.x = _amount(minimum=1, value=1, label="Island X coordinate")
        self.y = _amount(minimum=1, value=1, label="Island Y coordinate")
        for label, field in (("X", self.x), ("Y", self.y)):
            field.setMaximum(100)
            field.valueChanged.connect(self._invalidate)
            search.addWidget(QLabel(label))
            search.addWidget(field)
        self.lookup_button = PushButton("Find external cities")
        self.lookup_button.clicked.connect(self._lookup)
        search.addWidget(self.lookup_button)
        layout.addLayout(search)
        self.note = QLabel("External shipments require manual recovery.")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

    def set_cities(self, cities):
        self._cities = list(cities)
        self._invalidate()

    def _refresh(self):
        prior = self.picker.currentData()
        with QSignalBlocker(self.picker):
            self.picker.clear()
            self.picker.addItem("Choose a city")
            for city in self._cities:
                self.picker.addItem(str(city["name"]), userData=city["id"])
            for city in self._external:
                self.picker.addItem(f"{city['name']} — {city['owner']} ({self.x.value()}:{self.y.value()})",
                                    userData=city["id"])
            self.picker.setCurrentIndex(next((i for i in range(1,self.picker.count())
                                              if self.picker.itemData(i) == prior), 0))
        self.lookup_button.setEnabled(bool(self._cities))
        self.changed.emit()

    def _invalidate(self, *_args):
        self._nonce = None
        self._external = []
        self.note.setText("External shipments require manual recovery.")
        self._refresh()

    def _lookup(self):
        self._invalidate()
        self._nonce = str(uuid.uuid4())
        self.note.setText("Looking up cities…")
        self.lookup_requested.emit(self.x.value(), self.y.value(), self._nonce)

    def set_external(self, result, nonce):
        if nonce != self._nonce or (result.get("x"),result.get("y")) != (self.x.value(),self.y.value()):
            return
        self._nonce = None
        owned = {c["id"] for c in self._cities}
        self._external = [r for r in result["cities"] if r["id"] not in owned]
        self.note.setText(f"{len(self._external)} eligible external cities. Choose the receiving city.")
        self._refresh()

    def lookup_failed(self, nonce):
        if nonce == self._nonce:
            self._nonce = None
            self.note.setText("Island lookup unavailable.")

    def to_config(self):
        selected = self.picker.currentData()
        if selected in {c["id"] for c in self._cities}:
            return {"destination_city": selected}
        for row in self._external:
            if row["id"] == selected:
                return {"destination_city": selected, "island": row["island"], "recipient": row["recipient"]}
        raise ValueError("Choose an actual receiving city")


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
            value = kind.currentData()
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
        city_id = self.city_picker.currentData()
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
        layout.addWidget(QLabel("Additional owned cities"))
        self.additional = QListWidget()
        self.additional.setMaximumHeight(100)
        self.additional.setAccessibleName("Additional recruitment cities")
        self.additional.itemChanged.connect(self.changed.emit)
        layout.addWidget(self.additional)
        options = QHBoxLayout()
        all_button = PushButton("Select all cities")
        all_button.clicked.connect(self._all_cities)
        options.addWidget(all_button)
        options.addWidget(QLabel("Total cycles"))
        self.cycles = _amount(minimum=1, value=1, label="Training repetitions including first cycle")
        self.cycles.setMaximum(10)
        self.cycles.valueChanged.connect(self.changed.emit)
        options.addWidget(self.cycles)
        layout.addLayout(options)
        self._rounds = []
        self.round_picker = ComboBox()
        self.round_picker.setAccessibleName("Training round")
        self.round_picker.addItem("Round 1")
        self._round_index = 0
        self.round_picker.currentIndexChanged.connect(self._switch_round)
        rounds = QHBoxLayout()
        rounds.addWidget(self.round_picker)
        self.add_round = PushButton("Add round")
        self.remove_round = PushButton("Remove round")
        self.add_round.clicked.connect(self._add_round)
        self.remove_round.clicked.connect(self._remove_round)
        rounds.addWidget(self.add_round)
        rounds.addWidget(self.remove_round)
        layout.addLayout(rounds)
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
        self._cities = list(cities)
        self._reset_rounds()
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
        self._populate_additional()
        self.description.setText("Choose a city with barracks or a shipyard.")
        self.changed.emit()

    def _populate_additional(self):
        with QSignalBlocker(self.additional):
            self.additional.clear()
            for city in self._cities:
                if city["id"] == self.city_picker.currentData():
                    continue
                item = QListWidgetItem(str(city["name"]))
                item.setData(Qt.UserRole, city["id"])
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.additional.addItem(item)

    def _all_cities(self):
        for i in range(self.additional.count()):
            self.additional.item(i).setCheckState(Qt.Checked if i < 31 else Qt.Unchecked)

    def _reset_rounds(self):
        self._rounds = [{}]
        self._round_index = 0
        with QSignalBlocker(self.round_picker):
            self.round_picker.clear()
            self.round_picker.addItem("Round 1")
            self.round_picker.setCurrentIndex(0)
        self.remove_round.setEnabled(False)
        self.add_round.setEnabled(False)

    def _save_round(self):
        if not self._snapshot:
            return
        self._rounds[self._round_index] = {
            u["unit_type_id"]: self.table.cellWidget(i, 2).value()
            for i, u in enumerate(self._snapshot["units"])}

    def _load_round(self):
        if not self._snapshot:
            return
        for i, unit in enumerate(self._snapshot["units"]):
            field = self.table.cellWidget(i, 2)
            with QSignalBlocker(field):
                field.setValue(self._rounds[self._round_index].get(unit["unit_type_id"], 0))
        self.changed.emit()

    def _switch_round(self, index):
        if 0 <= index < len(self._rounds):
            self._save_round()
            self._round_index = index
            self._load_round()

    def _add_round(self):
        if not self._snapshot or len(self._rounds) >= 10:
            return
        self._save_round()
        self._rounds.append({})
        self.round_picker.addItem(f"Round {len(self._rounds)}")
        self.round_picker.setCurrentIndex(len(self._rounds)-1)
        self.add_round.setEnabled(len(self._rounds)<10)
        self.remove_round.setEnabled(True)

    def _remove_round(self):
        if len(self._rounds) <= 1:
            return
        self._rounds.pop(self._round_index)
        self._round_index = min(self._round_index, len(self._rounds)-1)
        with QSignalBlocker(self.round_picker):
            self.round_picker.clear()
            for i in range(len(self._rounds)):
                self.round_picker.addItem(f"Round {i+1}")
            self.round_picker.setCurrentIndex(self._round_index)
        self._load_round()
        self.remove_round.setEnabled(len(self._rounds)>1)
        self.add_round.setEnabled(True)

    def _reset_selection(self, *_args: object) -> None:
        self._reset_rounds()
        self._populate_additional()
        self._loaded = None
        self._snapshot = None
        self.table.setRowCount(0)
        city_id = self.city_picker.currentData()
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
        self._reset_rounds()
        self.add_round.setEnabled(True)
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
        self._reset_rounds()
        self._loaded = None
        self._snapshot = None
        self.table.setRowCount(0)
        self.description.setText(
            "No verified recruitable units for this city and fleet type. "
            "Check the game session, barracks or shipyard."
        )
        self.changed.emit()

    def reviewed_draft(self):
        from daedalus.training_contract import training_draft

        if self._snapshot is None or self._loaded != self._selected:
            raise ValueError("Choose a city and load its actual recruitable units")
        self._save_round()
        rounds = [[{"unit_type_id": uid, "cantidad": count}
                   for uid, count in group.items() if count] for group in self._rounds]
        return training_draft({"city_ids": [self._selected[0], *[
            self.additional.item(i).data(Qt.UserRole) for i in range(self.additional.count())
            if self.additional.item(i).checkState() == Qt.Checked]],
            "train_troops": self._selected[1], "rounds": rounds, "cycles": self.cycles.value()})

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
        city_id = self.city_picker.currentData()
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


class TavernCitiesEditor(QWidget):
    """Per-city real wine, consumption and happiness; adjustable check frequency."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from qfluentwidgets import CheckBox

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.all_cities = CheckBox("Manage all cities with taverns")
        self.all_cities.setChecked(True)
        self.all_cities.stateChanged.connect(self._scope_changed)
        layout.addWidget(self.all_cities)
        self.table = _table((
            "Manage", "City", "Current wine", "Wine / hour",
            "Population", "Satisfaction",
        ))
        self.table.setMinimumHeight(200)
        self.table.setAccessibleName("Account cities with real tavern and wine state")
        self.table.itemChanged.connect(self.changed.emit)
        layout.addWidget(self.table)
        policy = QHBoxLayout()
        policy.addWidget(QLabel("Repeat"))
        self.interval = _amount(label="Hours between tavern balance checks")
        self.interval.setRange(0, 24)
        self.interval.setValue(2)
        self.interval.setSpecialValueText("Once now")
        self.interval.valueChanged.connect(self.changed.emit)
        policy.addWidget(self.interval)
        policy.addWidget(QLabel("Notifications"))
        self.notifications = ComboBox()
        self.notifications.addItems(["Every change", "Only errors", "None"])
        self.notifications.setCurrentIndex(1)
        self.notifications.setAccessibleName("Tavern manager notifications")
        self.notifications.currentIndexChanged.connect(self.changed.emit)
        policy.addWidget(self.notifications)
        policy.addStretch(1)
        layout.addLayout(policy)
        self.description = QLabel(
            "Loading wine, population and tavern servings from the account."
        )
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self._taverns: list[dict[str, object]] | None = None

    def _scope_changed(self, *_args: object) -> None:
        self.table.setEnabled(not self.all_cities.isChecked())
        self.changed.emit()

    def set_taverns(self, rows: list[dict[str, object]]) -> None:
        self._taverns = list(rows)
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(rows))
            for row, city in enumerate(rows):
                checkbox = QTableWidgetItem("")
                checkbox.setData(Qt.UserRole, city["city_id"])
                checkbox.setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
                    if city["has_tavern"] else Qt.ItemIsEnabled
                )
                checkbox.setCheckState(Qt.Unchecked)
                self.table.setItem(row, 0, checkbox)
                population = (
                    f'{city["population"]:,} / {city["capacity"]:,}'
                    if city["population"] is not None and city["capacity"] is not None
                    else "Unavailable"
                )
                for col, value in (
                    (1, city["city_name"]),
                    (2, f'{city["wine"]:,}'),
                    (3, city["wine_per_hour"] if city["wine_per_hour"] is not None
                     else "Unavailable"),
                    (4, population),
                    (5, city["satisfaction"] if city["satisfaction"] is not None
                     else "Unavailable"),
                ):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row, col, item)
        self.description.setText(
            f"{len(rows)} owned cities inspected. "
            "Tavern equilibrium changes wine servings according to current population "
            "and satisfaction; check before approving recurring game changes."
        )
        self._scope_changed()

    def set_unavailable(self) -> None:
        self._taverns = None
        self.table.setRowCount(0)
        self.description.setText(
            "Could not read the account's tavern and wine levels. No schedule is ready."
        )
        self.changed.emit()

    def to_config(self) -> dict[str, object]:
        if self._taverns is None:
            raise ValueError("Load real tavern and wine status for the account")
        if self.all_cities.isChecked():
            ids = None
            if not any(city["has_tavern"] for city in self._taverns):
                raise ValueError("No actual taverns are available in this account")
        else:
            ids = [
                str(self._taverns[row]["city_id"])
                for row in range(len(self._taverns))
                if self._taverns[row]["has_tavern"]
                and self.table.item(row, 0).checkState() == Qt.Checked
            ]
            if not ids:
                raise ValueError("Choose at least one city with a real tavern")
        return {
            "cities_ids": ids,
            "run_hours": self.interval.value(),
            "notification_mode": self.notifications.currentIndex() + 1,
        }


class MiracleTempleEditor(QWidget):
    """Select an actual owned temple/wonder instead of an invented god choice."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = _table((
            "Wonder", "Temple city", "Wonder level", "Now", "Cooldown remaining",
        ))
        self.table.setMinimumHeight(195)
        self.table.setAccessibleName("Real account-owned miracles and cooldowns")
        self.table.itemSelectionChanged.connect(self.changed.emit)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        row.addWidget(QLabel("Activations to schedule"))
        self.iterations = _amount(minimum=1, value=1,
                                  label="Total wonder activations")
        self.iterations.setMaximum(100)
        self.iterations.valueChanged.connect(self.changed.emit)
        row.addWidget(self.iterations)
        row.addStretch(1)
        layout.addLayout(row)
        self.description = QLabel(
            "Loading current temple miracles from this game account."
        )
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self._wonders: list[dict[str, object]] | None = None

    def set_miracles(self, wonders: list[dict[str, object]]) -> None:
        self._wonders = list(wonders)
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(wonders))
            for row, miracle in enumerate(wonders):
                seconds = miracle["available_in_seconds"]
                cooldown = (f"{seconds // 3600} h {(seconds % 3600) // 60} min"
                            if seconds else "None")
                for column, value in (
                    (0, miracle["wonder_name"]),
                    (1, miracle["temple_city"]),
                    (2, miracle["level"]),
                    (3, "Ready" if miracle["available"] else "Waiting"),
                    (4, cooldown),
                ):
                    cell = QTableWidgetItem(str(value))
                    cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row, column, cell)
            self.table.clearSelection()
        self.description.setText(
            f"{len(wonders)} real miracle types from your own temples. "
            "Select one row. IkaBot will check wonder eligibility again at launch "
            "and wait for cooldown before each later activation."
        )
        self.changed.emit()

    def set_unavailable(self) -> None:
        self._wonders = None
        self.table.setRowCount(0)
        self.description.setText(
            "Temple and wonder information unavailable for this account."
        )
        self.changed.emit()

    def to_config(self) -> dict[str, object]:
        if self._wonders is None:
            raise ValueError("Load actual owned miracles before selecting")
        row = self.table.currentRow()
        if row < 0 or row >= len(self._wonders):
            raise ValueError("Select one real wonder temple from the table")
        return {
            "wonder": self._wonders[row]["wonder"],
            "iterations": self.iterations.value(),
        }


class OlympusShrineEditor(QWidget):
    """Verified Shrine of Olympus + selected gods, favour budget and repeat policy."""

    changed = Signal()

    _GODS = (
        (1, "Pan", "Wood"), (2, "Dionysus", "Wine"),
        (3, "Tyche", "Marble"), (4, "Plutus", "Gold"),
        (5, "Theia", "Crystal"), (6, "Hephaestus", "Sulfur"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.shrine_label = QLabel("Reading this account's Shrine of Olympus…")
        self.shrine_label.setWordWrap(True)
        layout.addWidget(self.shrine_label)
        self.table = _table(("Activate", "God", "Bonus", "Favour cost"))
        self.table.setMinimumHeight(160)
        self.table.setAccessibleName("Select Shrine of Olympus blessings")
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(self._GODS))
            for index, (god_id, god, resource) in enumerate(self._GODS):
                toggle = QTableWidgetItem("")
                toggle.setData(Qt.UserRole, god_id)
                toggle.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                toggle.setCheckState(Qt.Unchecked)
                self.table.setItem(index, 0, toggle)
                for col, value in ((1, god), (2, resource), (3, "100")):
                    item = QTableWidgetItem(value)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(index, col, item)
        self.table.itemChanged.connect(self._selection_changed)
        layout.addWidget(self.table)
        schedule = QHBoxLayout()
        schedule.addWidget(QLabel("Activation schedule"))
        self.mode = ComboBox()
        self.mode.addItems([
            "Activate N times", "Repeat automatically (engine 72 h interval)",
            "Activate N times, then repeat automatically",
        ])
        self.mode.setAccessibleName("Olympus blessing schedule")
        self.mode.currentIndexChanged.connect(self._selection_changed)
        schedule.addWidget(self.mode, 2)
        self.count = _amount(minimum=1, value=1, label="Number of initial activations")
        self.count.setMaximum(10)
        self.count.valueChanged.connect(self.changed.emit)
        schedule.addWidget(self.count, 1)
        layout.addLayout(schedule)
        self.summary = QLabel("No gods selected.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self._shrine: dict[str, object] | None = None
        self._loaded = False

    def _selection_changed(self, *_args: object) -> None:
        chosen = [
            self.table.item(i, 0).data(Qt.UserRole)
            for i in range(self.table.rowCount())
            if self.table.item(i, 0).checkState() == Qt.Checked
        ]
        cost = 100 * len(chosen)
        favor = self._shrine.get("favor") if self._shrine else None
        current = f"{favor:,}" if type(favor) is int else "Unknown"
        self.summary.setText(
            f"Favour required per cycle: {cost:,}. Current favour: {current}. "
            + ("Waiting for enough favour is handled by IkaBot."
               if cost else "Choose gods to activate.")
        )
        self.count.setEnabled(self.mode.currentIndex() != 1)
        self.changed.emit()

    def set_shrine(self, shrine: dict[str, object] | None) -> None:
        self._loaded = True
        self._shrine = shrine
        if shrine is None:
            self.shrine_label.setText(
                "This account has no Shrine of Olympus. Activation is not possible."
            )
        else:
            self.shrine_label.setText(
                f"Shrine of Olympus: {shrine['city_name']} "
                f"(building position {shrine['position']})."
            )
        self._selection_changed()

    def set_unavailable(self) -> None:
        self._loaded = False
        self._shrine = None
        self.shrine_label.setText(
            "Could not verify an actual Shrine of Olympus for this account."
        )
        self._selection_changed()

    def to_config(self) -> dict[str, object]:
        if not self._loaded or self._shrine is None:
            raise ValueError("An actual owned Shrine of Olympus is required")
        gods = [
            self.table.item(i, 0).data(Qt.UserRole)
            for i in range(self.table.rowCount())
            if self.table.item(i, 0).checkState() == Qt.Checked
        ]
        if not gods:
            raise ValueError("Select at least one Shrine god")
        mode = self.mode.currentIndex() + 1
        if mode not in (1, 2, 3):
            raise ValueError("Choose a valid Shrine schedule")
        return {
            "godids": gods, "mode": mode,
            "times": 0 if mode == 2 else self.count.value(),
        }


class PiracyMissionsEditor(QWidget):
    """Available pirate fortress missions, real durations and optional day/night policy."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from qfluentwidgets import CheckBox

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.addWidget(QLabel("Pirate fortress city"))
        self.city = ComboBox()
        self.city.setAccessibleName("Real own pirate fortress")
        top.addWidget(self.city, 2)
        top.addWidget(QLabel("Number of missions"))
        self.count = _amount(minimum=1, value=1, label="Piracy mission count")
        self.count.setMaximum(100000)
        top.addWidget(self.count, 1)
        layout.addLayout(top)
        self.schedule = CheckBox("Use separate day/night missions")
        layout.addWidget(self.schedule)
        self.main_mission = ComboBox()
        self.main_mission.setAccessibleName("Piracy mission with actual fortress eligibility")
        self.day_mission = ComboBox()
        self.day_mission.setAccessibleName("Day piracy mission")
        self.night_mission = ComboBox()
        self.night_mission.setAccessibleName("Night piracy mission")
        layout.addWidget(QLabel("Default mission"))
        layout.addWidget(self.main_mission)
        day = QHBoxLayout()
        day.addWidget(QLabel("Day mission"))
        day.addWidget(self.day_mission)
        self.day_start = _amount(value=10, label="Day schedule starts, game hour")
        self.day_end = _amount(value=18, label="Day schedule ends, game hour")
        for label, field in (("From", self.day_start), ("Until", self.day_end)):
            field.setMaximum(23)
            day.addWidget(QLabel(label))
            day.addWidget(field)
        layout.addLayout(day)
        night = QHBoxLayout()
        night.addWidget(QLabel("Night mission"))
        night.addWidget(self.night_mission)
        self.night_start = _amount(value=19, label="Night schedule starts, game hour")
        self.night_end = _amount(value=9, label="Night schedule ends, game hour")
        for label, field in (("From", self.night_start), ("Until", self.night_end)):
            field.setMaximum(23)
            night.addWidget(QLabel(label))
            night.addWidget(field)
        layout.addLayout(night)
        extras = QHBoxLayout()
        self.convert = CheckBox("Convert capture points automatically")
        extras.addWidget(self.convert)
        self.convert_all = CheckBox("Convert all available points")
        extras.addWidget(self.convert_all)
        self.convert_amount = _amount(
            value=0, label="Number of capture points converted after each mission"
        )
        extras.addWidget(self.convert_amount)
        layout.addLayout(extras)
        waiting = QHBoxLayout()
        waiting.addWidget(QLabel("Maximum random extra wait"))
        self.waiting = _amount(value=0, label="Extra random waiting between missions")
        self.waiting.setMaximum(3600)
        self.waiting.setSuffix(" seconds")
        waiting.addWidget(self.waiting)
        waiting.addStretch(1)
        layout.addLayout(waiting)
        self.note = QLabel(
            "Loading real pirate fortresses and mission eligibility from this account."
        )
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self._fortresses: list[dict[str, object]] | None = None
        self.city.currentIndexChanged.connect(self._city_changed)
        self.schedule.stateChanged.connect(self._mode_changed)
        self.convert.stateChanged.connect(self._mode_changed)
        self.convert_all.stateChanged.connect(self._mode_changed)
        for field in (self.count, self.waiting, self.day_start, self.day_end,
                      self.night_start, self.night_end, self.convert_amount):
            field.valueChanged.connect(self.changed.emit)
        for mission in (self.main_mission, self.day_mission, self.night_mission):
            mission.currentIndexChanged.connect(self.changed.emit)
        self._mode_changed()

    def _mode_changed(self, *_args: object) -> None:
        scheduled = self.schedule.isChecked()
        self.main_mission.setEnabled(not scheduled)
        for widget in (self.day_mission, self.night_mission,
                       self.day_start, self.day_end, self.night_start, self.night_end):
            widget.setEnabled(scheduled)
        converting = self.convert.isChecked()
        self.convert_all.setEnabled(converting)
        self.convert_amount.setEnabled(converting and not self.convert_all.isChecked())
        self.changed.emit()

    def _city_changed(self, *_args: object) -> None:
        idx = self.city.currentIndex()
        chosen = (
            self._fortresses[idx - 1]
            if self._fortresses is not None and 1 <= idx <= len(self._fortresses)
            else None
        )
        missions = chosen["missions"] if chosen is not None else []
        for picker in (self.main_mission, self.day_mission, self.night_mission):
            with QSignalBlocker(picker):
                picker.clear()
                picker.addItem("Choose mission")
                for mission in missions:
                    secs = mission["duration_seconds"]
                    picker.addItem(
                        f'Mission {mission["number"]}: {secs // 3600}h {(secs % 3600) // 60}m '
                        f'{secs % 60}s', userData=mission["number"],
                    )
                picker.setCurrentIndex(0)
        self.note.setText(
            f'{chosen["city_name"]}: fortress level {chosen["fortress_level"]}, '
            f'{len(missions)} actual eligible missions. Select one or two missions.'
            if chosen is not None else
            "Select a real fortress city to see its available capture missions."
        )
        self.changed.emit()

    def set_fortresses(self, fortresses: list[dict[str, object]]) -> None:
        self._fortresses = list(fortresses)
        with QSignalBlocker(self.city):
            self.city.clear()
            self.city.addItem("Choose own fortress")
            for fortress in self._fortresses:
                self.city.addItem(
                    f'{fortress["city_name"]} (level {fortress["fortress_level"]})',
                    userData=fortress["city_id"],
                )
            self.city.setCurrentIndex(0)
        self._city_changed()

    def set_unavailable(self) -> None:
        self._fortresses = None
        with QSignalBlocker(self.city):
            self.city.clear()
            self.city.addItem("Fortress data unavailable")
        self._city_changed()
        self.note.setText(
            "Real pirate fortress data could not be verified for this account."
        )

    def to_config(self) -> dict[str, object]:
        idx = self.city.currentIndex()
        if (self._fortresses is None or idx <= 0
                or idx > len(self._fortresses)):
            raise ValueError("Choose a real owned pirate fortress")
        city = self._fortresses[idx - 1]
        supported = {mission["number"] for mission in city["missions"]}
        if not supported:
            raise ValueError("Fortress cannot run any pirate missions")
        scheduled = self.schedule.isChecked()
        main = self.main_mission.currentData()
        day = self.day_mission.currentData()
        night = self.night_mission.currentData()
        missions = [day, night] if scheduled else [main]
        if any(type(mission) is not int or mission not in supported for mission in missions):
            raise ValueError("Choose mission levels supported by this fortress")
        result: dict[str, object] = {
            "pirateCount": self.count.value(),
            "pirateSchedule": scheduled,
            "pirateMissionChoice": None if scheduled else main,
            "pirateMissionDayChoice": day if scheduled else None,
            "pirateMissionNightChoice": night if scheduled else None,
            "dayStart": self.day_start.value() if scheduled else None,
            "dayEnd": self.day_end.value() if scheduled else None,
            "nightStart": self.night_start.value() if scheduled else None,
            "nightEnd": self.night_end.value() if scheduled else None,
            "autoConvert": "y" if self.convert.isChecked() else "n",
            "convertPerMission": (
                "all" if self.convert.isChecked() and self.convert_all.isChecked()
                else self.convert_amount.value() if self.convert.isChecked() else 0
            ),
            "maxRandomWaitingTime": self.waiting.value(),
            "piracyCities": [{"id": city["city_id"]}],
        }
        return result


class BarbarianWavesEditor(QWidget):
    """Named troop inventory and editable wave columns; never display engine IDs."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.note = QLabel("Load actual troops for the origin city first.")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.table = _table(("Setting / troop", "Available"))
        self.table.setAccessibleName("Attack wave settings and available troop quantities")
        self.table.setMinimumHeight(185)
        layout.addWidget(self.table)
        self.add_button = PushButton("Add wave")
        self.remove_button = PushButton("Remove last wave")
        self.add_button.clicked.connect(self.add_wave)
        self.remove_button.clicked.connect(self.remove_wave)
        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.units = []
        self.waves = []
        self.loaded = False
        self.ship_limit = 0
        self._controls()

    def _controls(self):
        self.add_button.setEnabled(self.loaded and bool(self.units) and len(self.waves) < 8)
        self.remove_button.setEnabled(len(self.waves) > 1)

    def clear(self):
        self.loaded = False
        self.units = []
        self.waves = []
        self.ship_limit = 0
        self.table.setRowCount(0)
        self.table.setColumnCount(2)
        self.note.setText("Load actual troops for the origin city first.")
        self._controls()
        self.changed.emit()

    def set_inventory(self, result):
        self.clear()
        self.loaded = True
        self.units = result["units"]
        self.ship_limit = result["available_ships"]
        self.note.setText(f"Available transport ships: {self.ship_limit:,}. "
                          "Add up to eight ordered waves. An optional looting wave must be last.")
        self.table.setRowCount(3 + len(self.units))
        for i, label in enumerate(("Battle round", "Loot ships", "Final looting wave")):
            self.table.setItem(i, 0, QTableWidgetItem(label))
        for i, unit in enumerate(self.units, 3):
            self.table.setItem(i, 0, QTableWidgetItem(unit["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(f"{unit['available']:,}"))
        if self.units:
            self.add_wave()
        self._controls()

    def add_wave(self):
        if not self.loaded or not self.units or len(self.waves) >= 8:
            return
        n = len(self.waves)
        col = n + 2
        self.table.setColumnCount(col + 1)
        self.table.setHorizontalHeaderItem(col, QTableWidgetItem(f"Wave {n+1}"))
        round_field = _amount(minimum=1, value=n+1, label=f"Wave {n+1} battle round")
        round_field.setMaximum(100)
        if not n:
            round_field.setEnabled(False)
        ships = _amount(label=f"Wave {n+1} loot ships")
        ships.setMaximum(self.ship_limit)
        loot = CheckBox()
        loot.setAccessibleName(f"Wave {n+1} is final looting wave")
        loot.setEnabled(n > 0)
        for i, field in enumerate((round_field, ships, loot)):
            self.table.setCellWidget(i, col, field)
        round_field.valueChanged.connect(self.changed.emit)
        ships.valueChanged.connect(self.changed.emit)
        def loot_changed(_state):
            if loot.isChecked():
                ships.setValue(0)
            ships.setEnabled(not loot.isChecked())
            self.changed.emit()
        loot.stateChanged.connect(loot_changed)
        fields = []
        for i, unit in enumerate(self.units, 3):
            amount = _amount(label=f"Wave {n+1}: {unit['name']}")
            amount.setMaximum(unit["available"])
            amount.valueChanged.connect(self.changed.emit)
            self.table.setCellWidget(i, col, amount)
            fields.append(amount)
        self.waves.append((round_field, ships, loot, fields))
        self._controls()
        self.changed.emit()

    def remove_wave(self):
        if len(self.waves) <= 1:
            return
        self.waves.pop()
        self.table.setColumnCount(len(self.waves) + 2)
        self._controls()
        self.changed.emit()

    def to_config(self):
        if not self.loaded or not self.waves:
            raise ValueError("Load actual troops before planning the attack")
        result = []
        totals = {}
        previous = 0
        for i, (round_field, ships, loot, fields) in enumerate(self.waves):
            if round_field.value() <= previous or (loot.isChecked() and i != len(self.waves)-1):
                raise ValueError("Use increasing battle rounds; looting must be the final wave")
            previous = round_field.value()
            units = {u["unit_id"]: w.value() for u, w in zip(self.units, fields) if w.value()}
            if not units:
                raise ValueError("Select at least one troop in every wave")
            for uid, amount in units.items():
                totals[uid] = totals.get(uid, 0) + amount
            result.append({"round": previous, "ships": ships.value(), "loot": loot.isChecked(), "units": units})
        if any(totals.get(u["unit_id"], 0) > u["available"] for u in self.units):
            raise ValueError("Combined waves exceed available troops")
        return result
