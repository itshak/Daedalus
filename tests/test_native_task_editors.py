"""Offline, synthetic native automation editors; no game access or dispatch."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication

from daedalus.desktop.native_controls import (
    DonationPoliciesEditor,
    MapAreaEditor,
    ResourceAmountsEditor,
    ResourceLimitsEditor,
    ShipmentRoutesEditor,
    WorkshopUpgradesEditor,
)
from daedalus.desktop.task_page import TasksPage

CITIES = [
    {"id": 101, "name": "Athens", "coords": "12:13"},
    {"id": 102, "name": "Sparta", "coords": "12:15"},
    {"id": 103, "name": "Olympia", "coords": "12:13"},
]


@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def page(app):
    widget = TasksPage()
    widget.set_accounts([{
        "id": "alpha", "world": "s301-en", "player": "TestPlayer",
        "enabled": True,
    }])
    yield widget
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def set_native(page, task, fields):
    page.set_capabilities([{"name": task, "kind": "background_task",
                            "config_fields": fields}], enabled=True)
    page.set_cities("alpha", CITIES)


def field(name, kind="json", *, required=False, default=None):
    result = {"name": name, "type": kind, "required": required}
    if default is not None:
        result["default"] = default
    return result


def test_shipments_are_a_verifiable_route_matrix_not_json(app):
    editor = ShipmentRoutesEditor()
    try:
        assert not editor.add_button.isEnabled()
        with pytest.raises(ValueError, match="Add at least one"):
            editor.to_config()
        editor.set_cities(CITIES)
        editor.add_route()
        from_city = editor.table.cellWidget(0, 0)
        to_city = editor.table.cellWidget(0, 1)
        amounts = editor.table.cellWidget(0, 2)
        from_city.setCurrentIndex(1)
        to_city.setCurrentIndex(2)
        with pytest.raises(ValueError, match="nonzero"):
            editor.to_config()
        amounts.setValue(6000)
        assert editor.to_config() == [{
            "from": 101, "to": 102, "resources": [6000, 0, 0, 0, 0]
        }]
        to_city.setCurrentIndex(1)
        with pytest.raises(ValueError, match="same city"):
            editor.to_config()
        editor.set_cities([{"id": 303, "name": "Different world"}])
        assert editor.table.rowCount() == 0
        assert not editor.add_button.isEnabled()
    finally:
        editor.close()
        editor.deleteLater()


def test_retention_and_transport_amount_controls(app):
    limits = ResourceLimitsEditor()
    amounts = ResourceAmountsEditor()
    try:
        with pytest.raises(ValueError, match="at least one resource"):
            limits.to_config()
        limits.values[0].setValue(0)
        limits.values[1].setValue(5000)
        assert limits.to_config() == [0, 5000, -1, -1, -1]
        with pytest.raises(ValueError, match="Select at least one resource"):
            amounts.to_config(ignore_allowed=True)
        amounts.values[0].setValue(0)
        assert amounts.to_config(ignore_allowed=True) == [0, None, None, None, None]
        with pytest.raises(ValueError, match="positive"):
            amounts.to_config(ignore_allowed=False)
        amounts.values[2].setValue(800)
        assert amounts.to_config(ignore_allowed=False) == [0, 0, 800, 0, 0]
    finally:
        for widget in (limits, amounts):
            widget.close()
            widget.deleteLater()


def test_donation_policies_use_actual_account_city_rows(app):
    widget = DonationPoliciesEditor()
    try:
        widget.set_cities(CITIES)
        assert widget.table.rowCount() == 3
        with pytest.raises(ValueError, match="Choose at least one"):
            widget.to_config(1)
        kind = widget.table.cellWidget(0, 1)
        amount = widget.table.cellWidget(0, 2)
        kind.setCurrentIndex(1)
        assert amount.isEnabled()
        amount.setValue(75)
        assert widget.to_config(1) == {
            "101": {"donation_type": "resource", "percentage": 75}
        }
        widget.update_method(3)
        amount.setValue(10000)
        assert widget.to_config(3)["101"]["percentage"] == 10000
        widget.set_cities([])
        assert widget.table.rowCount() == 0
        with pytest.raises(ValueError, match="Choose at least one"):
            widget.to_config(3)
    finally:
        widget.close()
        widget.deleteLater()


def test_map_area_has_bounded_optional_native_controls(app):
    widget = MapAreaEditor()
    try:
        assert widget.to_config() is None
        widget.enabled.setChecked(True)
        widget.x.setValue(50)
        widget.y.setValue(70)
        widget.radius.setValue(20)
        assert widget.to_config() == ([50, 70], 20)
        widget.x.setValue(999)
        assert widget.x.value() == 100
    finally:
        widget.close()
        widget.deleteLater()


def test_send_resources_native_editor_serializes_only_verified_city_ids(page):
    set_native(page, "sendResources", [
        field("routes", required=True), field("useFreighters", "boolean", default=False),
    ])
    routes = page._form_inputs["routes"]
    assert isinstance(routes, ShipmentRoutesEditor)
    routes.add_route()
    routes.table.cellWidget(0, 0).setCurrentIndex(1)
    routes.table.cellWidget(0, 1).setCurrentIndex(2)
    routes.table.cellWidget(0, 2).setValue(300)
    config = page._form_config()
    assert config["routes"] == [{
        "from": 101, "to": 102, "resources": [300, 0, 0, 0, 0]
    }]
    assert config["useFreighters"] is False
    page.set_cities_unavailable("alpha")
    with pytest.raises(ValueError, match="Add at least one"):
        page._form_config()


def test_consolidation_has_source_city_checkboxes_destination_and_resource_matrix(page):
    set_native(page, "consolidateResources", [
        field("limits", required=True),
        field("sourceCityIds", required=True),
        field("destinationCityId", required=True),
        field("intervalInHours", "integer", default=1),
        field("shipType", "integer", default=1),
    ])
    assert isinstance(page._form_inputs["limits"], ResourceLimitsEditor)
    page._form_inputs["limits"].values[0].setValue(200)
    page._form_inputs["sourceCityIds"].item(0).setCheckState(Qt.Checked)
    page._form_inputs["destinationCityId"].setCurrentIndex(2)
    config = page._form_config()
    assert config["limits"] == [200, -1, -1, -1, -1]
    assert config["sourceCityIds"] == ["101"]
    assert config["destinationCityId"] == 102
    assert config["shipType"] == 1
    page._form_inputs["destinationCityId"].setCurrentIndex(1)
    with pytest.raises(ValueError, match="Destination cannot"):
        page._form_config()


def test_shrine_gods_are_native_source_verified_multichoices(page):
    set_native(page, "activateShrine", [
        field("godids", required=True), field("mode", required=True),
        field("times", "integer", default=1), field("selected_gods"),
        field("wait_time", "integer", default=43200),
    ])
    gods = page._form_inputs["godids"]
    assert [gods.item(i).text() for i in range(gods.count())] == [
        "Pan", "Dionysus", "Tyche", "Plutus", "Theia", "Hephaestus"
    ]
    gods.item(0).setCheckState(Qt.Checked)
    gods.item(5).setCheckState(Qt.Checked)
    page._form_inputs["mode"].setCurrentIndex(0)
    assert page._form_config()["godids"] == [1, 6]
    assert "selected_gods" not in page._form_config()
    page._form_inputs["mode"].setCurrentIndex(1)
    assert "times" not in page._form_config()


def test_island_search_uses_real_own_island_coordinates_and_not_raw_json(page):
    set_native(page, "searchForIslandSpaces", [
        field("time", "integer", required=True),
        field("islandList"), field("fights", "text", default="n"),
    ])
    islands = page._form_inputs["islandList"]
    assert islands.count() == 2  # shared island deduplicated
    assert islands.item(0).text().startswith("12:13")
    islands.item(0).setCheckState(Qt.Checked)
    page._form_inputs["time"].setValue(15)
    config = page._form_config()
    assert config["islandList"] == ["12:13"]
    assert config["time"] == 15


def test_auto_pirate_mode_switch_only_submits_visible_schedule_controls(page):
    set_native(page, "autoPirate", [
        field("pirateCount", required=True),
        field("pirateSchedule", "boolean", default=False),
        field("pirateMissionChoice"),
        field("pirateMissionDayChoice"),
        field("pirateMissionNightChoice"),
        field("dayStart", "integer", default=10),
        field("dayEnd", "integer", default=18),
        field("nightStart", "integer", default=19),
        field("nightEnd", "integer", default=9),
        field("autoConvert", "text", default="n"),
        field("convertPerMission", "integer", default=0),
        field("maxRandomWaitingTime", "integer", default=0),
        field("piracyCities"),
    ])
    page._form_inputs["pirateCount"].setValue(3)
    page._form_inputs["pirateMissionChoice"].setCurrentIndex(1)
    config = page._form_config()
    assert config["pirateCount"] == 3
    assert config["pirateMissionChoice"] == 2
    assert "pirateMissionDayChoice" not in config
    page._form_inputs["pirateSchedule"].setChecked(True)
    page._form_inputs["pirateMissionDayChoice"].setCurrentIndex(0)
    page._form_inputs["pirateMissionNightChoice"].setCurrentIndex(1)
    scheduled = page._form_config()
    assert "pirateMissionChoice" not in scheduled
    assert scheduled["pirateMissionDayChoice"] == 1
    assert scheduled["pirateMissionNightChoice"] == 2


def test_donation_policy_and_map_editor_use_no_json_fields(page):
    set_native(page, "donationBot", [
        field("cities_dict", required=True),
        field("waiting_time", "integer", default=1440),
        field("donate_method", "integer", default=1),
        field("cities_ids"),
    ])
    donation = page._form_inputs["cities_dict"]
    assert isinstance(donation, DonationPoliciesEditor)
    donation.table.cellWidget(0, 1).setCurrentIndex(1)
    assert page._form_config()["cities_dict"]["101"]["donation_type"] == "resource"
    page.set_capabilities([{"name": "dumpWorld", "kind": "background_task",
                            "config_fields": [
                                field("waiting_time", "number", default=1.5),
                                field("coords"), field("radius"),
                                field("shallow", "boolean", default=False),
                                field("non_empty_islands", "boolean", default=False),
                                field("show_progress", "boolean", default=False),
                            ]}], enabled=True)
    area = page._form_inputs["coords"]
    assert isinstance(area, MapAreaEditor)
    area.enabled.setChecked(True)
    area.x.setValue(9)
    area.y.setValue(17)
    assert page._form_config()["coords"] == [9, 17]
    page._form_inputs["shallow"].setChecked(True)
    with pytest.raises(ValueError, match="cannot be limited"):
        page._form_config()


def test_workshop_editor_loads_real_unit_levels_and_refuses_cross_city_data(app):
    widget = WorkshopUpgradesEditor()
    try:
        seen = []
        widget.city_requested.connect(seen.append)
        widget.set_cities(CITIES)
        assert widget.table.rowCount() == 0
        widget.city_picker.setCurrentIndex(1)
        assert seen == [101]
        with pytest.raises(ValueError, match="load its verified unit levels"):
            widget.to_config()
        units = [
            {"unit_id": "12", "name": "Swordsman", "upgrade_type": "offensive",
             "description": "Attack", "current_level": 3, "max_level": 15},
            {"unit_id": "12", "name": "Swordsman", "upgrade_type": "defensive",
             "description": "Defense", "current_level": 6, "max_level": 15},
        ]
        widget.set_workshop_data(102, units, 15)
        assert widget.table.rowCount() == 0
        widget.set_workshop_data(101, units, 15)
        assert widget.table.rowCount() == 2
        with pytest.raises(ValueError, match="Select 1 to 50"):
            widget.to_config()
        target = widget.table.cellWidget(0, 4)
        target.setValue(7)
        widget.table.item(0, 0).setCheckState(Qt.Checked)
        assert widget.to_config() == [{
            "city_id": 101, "upgrades": [{
                "unitId": "12", "upgradeType": "offensive", "target": 7
            }],
        }]
        widget.city_picker.setCurrentIndex(2)
        assert seen == [101, 102]
        with pytest.raises(ValueError, match="load its verified"):
            widget.to_config()
        widget.set_unavailable(101)  # late error for a different city
        assert "Reading" in widget.description.text()
        widget.set_unavailable(102)
        assert "No verified" in widget.description.text()
    finally:
        widget.close()
        widget.deleteLater()


def test_upgrade_units_is_prepared_from_actual_unit_choices_not_untrusted_json(page):
    requests = []
    page.workshop_requested.connect(
        lambda account_id, city_id: requests.append((account_id, city_id))
    )
    set_native(page, "UpgradeUnits", [field("jobs", required=True)])
    widget = page._form_inputs["jobs"]
    assert isinstance(widget, WorkshopUpgradesEditor)
    widget.city_picker.setCurrentIndex(1)
    assert requests == [("alpha", 101)]
    page.set_workshop_upgrades({
        "account_id": "beta", "city_id": 101, "workshop_level": 12,
        "upgrades": [],
    })
    assert widget.table.rowCount() == 0
    page.set_workshop_upgrades({
        "account_id": "alpha", "city_id": 101, "workshop_level": 12,
        "upgrades": [{
            "unit_id": "99", "name": "Ram", "upgrade_type": "offensive",
            "description": "Attack", "current_level": 5, "max_level": 12,
        }],
    })
    assert widget.table.rowCount() == 1
    widget.table.cellWidget(0, 4).setValue(6)
    widget.table.item(0, 0).setCheckState(Qt.Checked)
    assert page._form_config()["jobs"] == [{
        "city_id": 101, "upgrades": [{
            "unitId": "99", "upgradeType": "offensive", "target": 6,
        }],
    }]
    page.set_cities_unavailable("alpha")
    with pytest.raises(ValueError, match="load its verified"):
        page._form_config()
