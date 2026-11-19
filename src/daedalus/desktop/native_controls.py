"""Account-bound native editors for reviewed IkaBot operation parameters.

These widgets never send game requests or make up IDs/quantities. Their
constructors are empty until a verified city snapshot is supplied. The
controller and existing-session IkaBot planner independently revalidate the
result before starting any task.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QHeaderView, QLabel, QTableWidget, QVBoxLayout, QWidget
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
