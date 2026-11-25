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
    AcademyResearchEditor,
    DonationPoliciesEditor,
    MapAreaEditor,
    MarketOffersEditor,
    MiracleTempleEditor,
    OlympusShrineEditor,
    PiracyMissionsEditor,
    ResourceAmountsEditor,
    ResourceLimitsEditor,
    ShipmentRoutesEditor,
    TavernCitiesEditor,
    TrainableUnitsEditor,
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
    page._form_inputs["intervalInHours"].setValue(1)
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
    editor = page._form_inputs["godids"]
    assert isinstance(editor, OlympusShrineEditor)
    with pytest.raises(ValueError, match="actual owned Shrine"):
        page._form_config()
    page.set_shrine({
        "account_id": "alpha",
        "shrine": {"city_id": 101, "city_name": "Athens", "position": 4, "favor": 310},
    })
    editor.table.item(0, 0).setCheckState(Qt.Checked)
    editor.table.item(5, 0).setCheckState(Qt.Checked)
    assert page._form_config()["godids"] == [1, 6]
    assert "selected_gods" not in page._form_config()
    editor.mode.setCurrentIndex(1)
    assert page._form_config()["times"] == 0


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


def test_auto_pirate_mode_switch_only_submits_verified_missions(page):
    set_native(page, "autoPirate", [
        field("pirateCount", required=True),
        field("pirateSchedule", "boolean", default=False),
        field("pirateMissionChoice"), field("pirateMissionDayChoice"),
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
    editor = page._form_inputs["pirateCount"]
    assert isinstance(editor, PiracyMissionsEditor)
    with pytest.raises(ValueError, match="real owned pirate fortress"):
        page._form_config()
    result = {
        "account_id": "alpha",
        "fortresses": [{
            "city_id": 101, "city_name": "Athens", "fortress_level": 3,
            "missions": [{"number": 1, "duration_seconds": 180},
                         {"number": 2, "duration_seconds": 360}],
        }],
    }
    page.set_pirate_fortresses({**result, "account_id": "beta"})
    with pytest.raises(ValueError, match="real owned pirate fortress"):
        page._form_config()
    page.set_pirate_fortresses(result)
    editor.city.setCurrentIndex(1)
    editor.count.setValue(3)
    editor.main_mission.setCurrentIndex(2)
    config = page._form_config()
    assert config["pirateCount"] == 3
    assert config["pirateMissionChoice"] == 2
    assert config["pirateMissionDayChoice"] is None
    editor.schedule.setChecked(True)
    editor.day_mission.setCurrentIndex(1)
    editor.night_mission.setCurrentIndex(2)
    scheduled = page._form_config()
    assert scheduled["pirateMissionChoice"] is None
    assert scheduled["pirateMissionDayChoice"] == 1
    assert scheduled["pirateMissionNightChoice"] == 2
    assert scheduled["piracyCities"] == [{"id": 101}]
    page.set_pirate_fortresses_unavailable("alpha")
    with pytest.raises(ValueError, match="real owned pirate fortress"):
        page._form_config()


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


TRAINABLE = {
    "account_id": "alpha", "city_id": 101, "train_troops": True,
    "city": {"id": "101", "cityName": "Athens", "pos": "3"},
    "available": [3000, 100, 0, 0, 1000], "free_citizens": 20,
    "units": [
        {"unit_type_id": 301, "local_name": "Swordsman",
         "costs": {"wood": 100, "sulfur": 50, "citizens": 1, "upkeep": 3}},
        {"unit_type_id": 302, "local_name": "Hoplite",
         "costs": {"wood": 200, "sulfur": 70, "citizens": 1}},
    ],
}


def test_unit_recruitment_table_validates_real_city_budget_and_modes(app):
    editor = TrainableUnitsEditor()
    try:
        requested = []
        editor.city_requested.connect(lambda *args: requested.append(args))
        editor.set_cities(CITIES)
        editor.city_picker.setCurrentIndex(1)
        assert requested == [(101, True)]
        with pytest.raises(ValueError, match="load its actual recruitable"):
            editor.to_config()
        editor.set_trainables({**TRAINABLE, "city_id": 102})
        assert editor.table.rowCount() == 0
        editor.set_trainables(TRAINABLE)
        assert editor.table.rowCount() == 2
        first = editor.table.cellWidget(0, 2)
        first.setValue(4)
        plan = editor.to_config()
        assert plan["city"]["id"] == "101"
        assert plan["tranings"] == [[{"unit_type_id": 301, "cantidad": 4}]]
        assert plan["trainTroops"] is True
        assert plan["replicate"] == "n"
        first.setValue(100)
        with pytest.raises(ValueError, match="Not enough wood"):
            editor.to_config()
        editor.mode.setCurrentIndex(1)
        assert requested[-1] == (101, False)
        with pytest.raises(ValueError, match="load its actual recruitable"):
            editor.to_config()
        editor.set_unavailable(101, False)
        assert editor.table.rowCount() == 0
        editor.set_cities([])
        with pytest.raises(ValueError):
            editor.to_config()
    finally:
        editor.close()
        editor.deleteLater()


def test_native_army_task_ignores_outside_account_training_results(page):
    requested = []
    page.trainable_units_requested.connect(
        lambda account_id, city, troops: requested.append((account_id, city, troops))
    )
    set_native(page, "trainArmy", [
        field("city", required=True), field("tranings", required=True),
        field("trainTroops", required=True), field("replicate", required=True),
        field("countRepeat", required=True), field("cityTrainings", required=True),
        field("units", required=True),
    ])
    editor = page._form_inputs["city"]
    assert isinstance(editor, TrainableUnitsEditor)
    editor.city_picker.setCurrentIndex(1)
    assert requested == [("alpha", 101, True)]
    page.set_trainable_units({**TRAINABLE, "account_id": "beta"})
    with pytest.raises(ValueError, match="load its actual recruitable"):
        page._form_config()
    page.set_trainable_units(TRAINABLE)
    editor.table.cellWidget(0, 2).setValue(5)
    config = page._form_config()
    assert config["tranings"][0][0] == {"unit_type_id": 301, "cantidad": 5}
    assert config["city"]["id"] == "101"
    page.set_cities_unavailable("alpha")
    with pytest.raises(ValueError, match="load its actual recruitable"):
        page._form_config()


MARKET_QUOTE = {
    "ciudadDestino": "Marketville", "jugadorAComprar": "Seller",
    "amountAvailable": 300, "tipo": "wood", "precio": 7,
    "destinationCityId": "987", "cityId": "101", "position": "4",
    "type": "444", "resource": "resource",
}
MARKET_BASE = {
    "account_id": "alpha", "city_id": 101, "resource_type": 0,
    "city": {"id": "101", "pos": 4, "rango": 4, "name": "Athens",
             "cityName": "Athens", "availableResources": [1000, 0, 0, 0, 0]},
}


def test_buy_market_uses_checked_real_quotes_with_live_limits(app):
    editor = MarketOffersEditor(buying=True)
    try:
        requested = []
        editor.market_requested.connect(lambda *items: requested.append(items))
        editor.set_cities(CITIES)
        editor.city_picker.setCurrentIndex(1)
        assert requested == [(101, 0, "buy")]
        with pytest.raises(ValueError, match="load real market offers"):
            editor.to_config()
        editor.set_quotes({**MARKET_BASE, "account_id": "beta",
                           "side": "buy", "offers": [MARKET_QUOTE]})
        # Scope-matched replies are already validated by TasksPage, not this widget.
        editor.set_quotes({**MARKET_BASE, "side": "buy", "offers": [MARKET_QUOTE]})
        assert editor.table.rowCount() == 1
        with pytest.raises(ValueError, match="Select 1 to 50"):
            editor.to_config()
        editor.table.item(0, 0).setCheckState(Qt.Checked)
        editor.amount.setValue(200)
        plan = editor.to_config()
        assert plan["amount_to_buy"] == 200
        assert plan["offers"] == [MARKET_QUOTE]
        editor.amount.setValue(301)
        with pytest.raises(ValueError, match="exceeds selected"):
            editor.to_config()
        editor.resource.setCurrentIndex(1)
        assert requested[-1] == (101, 1, "buy")
        with pytest.raises(ValueError, match="load real"):
            editor.to_config()
        editor.set_cities([])
        with pytest.raises(ValueError, match="load real"):
            editor.to_config()
    finally:
        editor.close()
        editor.deleteLater()


def test_sell_market_editor_lists_only_current_quote_or_valid_price(app):
    editor = MarketOffersEditor(buying=False)
    try:
        editor.set_cities(CITIES)
        editor.city_picker.setCurrentIndex(1)
        buyer = ["Marketville", "Buyer", 300, 12, 4, 987]
        editor.set_quotes({**MARKET_BASE, "side": "sell_to_offers",
                           "offers": [buyer], "price_min": None, "price_max": None})
        editor.table.item(0, 0).setCheckState(Qt.Checked)
        editor.amount.setValue(250)
        assert editor.to_config()["offers"] == [buyer]
        editor.amount.setValue(301)
        with pytest.raises(ValueError, match="exceeds actual"):
            editor.to_config()
        editor.mode.setCurrentIndex(1)
        with pytest.raises(ValueError, match="load real"):
            editor.to_config()
        editor.set_quotes({
            **MARKET_BASE, "side": "create_offer", "offers": [],
            "price_min": 5, "price_max": 25,
            "sell_market_capacity": 2000, "currently_on_sale": 100,
        })
        assert not editor.table.isVisible() or editor.table.isHidden()
        assert editor.price.minimum() == 5
        assert editor.price.maximum() == 25
        editor.price.setValue(17)
        editor.amount.setValue(300)
        result = editor.to_config()
        assert result["mode"] == "create_offer"
        assert result["price"] == 17
        assert result["sell_market_capacity"] == 2000
        editor.set_unavailable(101, 0, "create_offer")
        with pytest.raises(ValueError, match="load real"):
            editor.to_config()
    finally:
        editor.close()
        editor.deleteLater()


@pytest.mark.parametrize("name,field_name,side,expected", [
    ("buyResources", "city", "buy", "amount_to_buy"),
    ("sellResources", "mode", "sell_to_offers", "amount_to_sell"),
])
def test_task_market_config_uses_real_quotes_and_account_guard(
    page, name, field_name, side, expected,
):
    requests = []
    page.market_quotes_requested.connect(lambda *args: requests.append(args))
    fields = ([field("city", required=True), field("offers", required=True),
               field("amount_to_buy", required=True)]
              if name == "buyResources" else [
                  field("mode", required=True), field("amount_to_sell", required=True),
                  field("offers"), field("resource_type"), field("city_to_buy_from"),
                  field("price"), field("sell_market_capacity"), field("city"),
              ])
    set_native(page, name, fields)
    editor = page._form_inputs[field_name]
    assert isinstance(editor, MarketOffersEditor)
    editor.city_picker.setCurrentIndex(1)
    assert requests == [("alpha", 101, 0, side)]
    page.set_market_quotes({
        **MARKET_BASE, "side": side, "offers": [MARKET_QUOTE] if name == "buyResources"
        else [["Marketville", "Buyer", 300, 12, 4, 987]],
        "account_id": "beta",
    })
    with pytest.raises(ValueError, match="load real market"):
        page._form_config()
    page.set_market_quotes({
        **MARKET_BASE, "side": side, "offers": [MARKET_QUOTE] if name == "buyResources"
        else [["Marketville", "Buyer", 300, 12, 4, 987]],
    })
    editor.table.item(0, 0).setCheckState(Qt.Checked)
    editor.amount.setValue(200)
    result = page._form_config()
    assert result[expected] == 200
    assert name == "buyResources" or result["mode"] == "sell_to_offers"
    page.set_cities_unavailable("alpha")
    with pytest.raises(ValueError, match="load real market"):
        page._form_config()


ACADEMIES = [
    {"city_id": 101, "city_name": "Athens", "position": 5,
     "crystal": 600000, "cooldown": False, "can_experiment_now": True},
    {"city_id": 102, "city_name": "Sparta", "position": 7,
     "crystal": 100000, "cooldown": True, "can_experiment_now": False},
]


def test_native_academy_table_has_verified_crystal_and_cooldown(app):
    editor = AcademyResearchEditor()
    try:
        with pytest.raises(ValueError, match="Load actual academies"):
            editor.to_config()
        editor.set_academies(ACADEMIES)
        assert editor.table.rowCount() == 2
        assert editor.table.item(0, 2).text() == "600,000"
        assert editor.table.item(1, 3).text() == "Cooling down"
        editor.table.item(0, 0).setCheckState(Qt.Checked)
        assert editor.to_config() == {"cities_ids": ["101"], "qty": None}
        editor.count.setValue(3)
        assert editor.to_config()["qty"] == 3
        editor.table.item(1, 0).setCheckState(Qt.Checked)
        with pytest.raises(ValueError, match="exactly one"):
            editor.to_config()
        editor.table.item(0, 0).setCheckState(Qt.Unchecked)
        with pytest.raises(ValueError, match="300,000 crystal"):
            editor.to_config()
        editor.count.setValue(0)
        assert editor.to_config() == {"cities_ids": ["102"], "qty": None}
        editor.set_unavailable()
        assert editor.table.rowCount() == 0
        with pytest.raises(ValueError, match="Load actual academies"):
            editor.to_config()
    finally:
        editor.close()
        editor.deleteLater()


def test_research_task_uses_real_academy_rows_not_city_json(page):
    requested = []
    page.academies_requested.connect(requested.append)
    set_native(page, "research", [
        field("cities_ids"), field("qty"), field("mode"),
        field("experiments"), field("automatic"),
        field("cities"), field("info"),
    ])
    # Open task form and fetch current game inventory for the selected account.
    editor = page._form_inputs["cities_ids"]
    assert isinstance(editor, AcademyResearchEditor)
    page.set_academies({"account_id": "other", "academies": ACADEMIES})
    with pytest.raises(ValueError, match="Load actual academies"):
        page._form_config()
    page.set_academies({"account_id": "alpha", "academies": ACADEMIES})
    editor.table.item(0, 0).setCheckState(Qt.Checked)
    config = page._form_config()
    assert config["cities_ids"] == ["101"]
    assert config["qty"] is None
    editor.count.setValue(2)
    assert page._form_config()["qty"] == 2
    page.set_academies_unavailable("alpha")
    with pytest.raises(ValueError, match="Load actual academies"):
        page._form_config()


TAVERNS = [
    {"city_id": 101, "city_name": "Athens", "wine": 20000,
     "has_tavern": True, "serving_level": 5, "wine_per_hour": 24,
     "satisfaction": 40, "population": 300, "capacity": 500},
    {"city_id": 102, "city_name": "Sparta", "wine": 4000,
     "has_tavern": False, "serving_level": None, "wine_per_hour": None,
     "satisfaction": None, "population": 200, "capacity": 600},
    {"city_id": 103, "city_name": "Olympia", "wine": 1000,
     "has_tavern": True, "serving_level": 3, "wine_per_hour": 50,
     "satisfaction": -10, "population": 500, "capacity": 600},
]


def test_tavern_editor_displays_actual_wine_and_manages_all_or_selected(app):
    editor = TavernCitiesEditor()
    try:
        with pytest.raises(ValueError, match="Load real tavern"):
            editor.to_config()
        editor.set_taverns(TAVERNS)
        assert editor.table.rowCount() == 3
        assert editor.table.item(0, 2).text() == "20,000"
        assert editor.table.item(2, 5).text() == "-10"
        config = editor.to_config()
        assert config == {
            "cities_ids": None, "run_hours": 2, "notification_mode": 2,
        }
        editor.all_cities.setChecked(False)
        editor.table.item(0, 0).setCheckState(Qt.Checked)
        editor.interval.setValue(0)
        editor.notifications.setCurrentIndex(2)
        assert editor.to_config() == {
            "cities_ids": ["101"], "run_hours": 0, "notification_mode": 3,
        }
        editor.table.item(0, 0).setCheckState(Qt.Unchecked)
        with pytest.raises(ValueError, match="at least one"):
            editor.to_config()
        editor.set_taverns([TAVERNS[1]])
        editor.all_cities.setChecked(True)
        with pytest.raises(ValueError, match="No actual taverns"):
            editor.to_config()
        editor.set_unavailable()
        with pytest.raises(ValueError, match="Load real tavern"):
            editor.to_config()
    finally:
        editor.close()
        editor.deleteLater()


def test_tavern_task_uses_real_city_status_not_optional_json(page):
    requests = []
    page.taverns_requested.connect(requests.append)
    set_native(page, "tavernManager", [
        field("run_hours", required=True), field("cities_ids"),
        field("cities"), field("notification_mode", default=2),
        field("check_now", default=True),
    ])
    editor = page._form_inputs["cities_ids"]
    assert isinstance(editor, TavernCitiesEditor)
    page.set_taverns({"account_id": "beta", "taverns": TAVERNS})
    with pytest.raises(ValueError, match="Load real tavern"):
        page._form_config()
    page.set_taverns({"account_id": "alpha", "taverns": TAVERNS})
    assert page._form_config() == {
        "cities_ids": None, "run_hours": 2, "notification_mode": 2,
    }
    editor.all_cities.setChecked(False)
    editor.table.item(2, 0).setCheckState(Qt.Checked)
    assert page._form_config()["cities_ids"] == ["103"]
    page.set_taverns_unavailable("alpha")
    with pytest.raises(ValueError, match="Load real tavern"):
        page._form_config()


MIRACLES = [
    {"city_id": 101, "temple_city": "Athens",
     "island_id": "123", "wonder": "5",
     "wonder_name": "Temple of Hermes", "level": 5,
     "available": True, "available_in_seconds": 0},
    {"city_id": 102, "temple_city": "Sparta",
     "island_id": "456", "wonder": "1",
     "wonder_name": "Hephaestus' Forge", "level": 4,
     "available": False, "available_in_seconds": 7200},
]


def test_miracle_native_table_shows_owned_temple_level_and_cooldown(app):
    editor = MiracleTempleEditor()
    try:
        with pytest.raises(ValueError, match="Load actual owned miracles"):
            editor.to_config()
        editor.set_miracles(MIRACLES)
        assert editor.table.rowCount() == 2
        assert editor.table.item(1, 4).text() == "2 h 0 min"
        with pytest.raises(ValueError, match="Select one real wonder"):
            editor.to_config()
        editor.table.setCurrentCell(1, 0)
        editor.iterations.setValue(3)
        assert editor.to_config() == {"wonder": "1", "iterations": 3}
        editor.set_unavailable()
        with pytest.raises(ValueError, match="Load actual owned miracles"):
            editor.to_config()
    finally:
        editor.close()
        editor.deleteLater()


def test_activate_miracle_is_real_wonder_table_not_static_fake_names(page):
    set_native(page, "activateMiracle", [
        field("wonder", required=True),
        field("iterations", "integer", required=True, default=1),
        field("island"),
    ])
    editor = page._form_inputs["wonder"]
    assert isinstance(editor, MiracleTempleEditor)
    page.set_miracles({"account_id": "other", "miracles": MIRACLES})
    with pytest.raises(ValueError, match="Load actual"):
        page._form_config()
    page.set_miracles({"account_id": "alpha", "miracles": MIRACLES})
    editor.table.setCurrentCell(0, 0)
    assert page._form_config() == {"wonder": "5", "iterations": 1}
    page.set_miracles_unavailable("alpha")
    with pytest.raises(ValueError, match="Load actual"):
        page._form_config()


def test_olympus_shrine_editor_shows_favor_needed_and_repeat_policy(app):
    editor = OlympusShrineEditor()
    try:
        with pytest.raises(ValueError, match="actual owned Shrine"):
            editor.to_config()
        editor.set_shrine({"city_id": 101, "city_name": "Athens",
                           "position": 4, "favor": 320})
        editor.table.item(0, 0).setCheckState(Qt.Checked)
        editor.table.item(1, 0).setCheckState(Qt.Checked)
        assert "Favour required per cycle: 200" in editor.summary.text()
        assert "320" in editor.summary.text()
        editor.mode.setCurrentIndex(2)
        editor.count.setValue(3)
        assert editor.to_config() == {
            "godids": [1, 2], "mode": 3, "times": 3,
        }
        editor.mode.setCurrentIndex(1)
        assert editor.to_config() == {"godids": [1, 2], "mode": 2, "times": 0}
        assert not editor.count.isEnabled()
        editor.set_shrine({"city_id": 101, "city_name": "Athens",
                           "position": 4, "favor": None})
        assert "Current favour: Unknown" in editor.summary.text()
        editor.set_shrine(None)
        with pytest.raises(ValueError, match="actual owned Shrine"):
            editor.to_config()
        editor.set_unavailable()
        with pytest.raises(ValueError, match="actual owned Shrine"):
            editor.to_config()
    finally:
        editor.close()
        editor.deleteLater()


def test_shrine_task_uses_verified_olympus_snapshot_not_fake_gods(page):
    set_native(page, "activateShrine", [
        field("godids", required=True),
        field("mode", "integer", required=True),
        field("times", "integer", default=1),
        field("selected_gods"), field("wait_time"),
    ])
    editor = page._form_inputs["godids"]
    assert isinstance(editor, OlympusShrineEditor)
    page.set_shrine({"account_id": "beta", "shrine": {
        "city_id": 101, "city_name": "Athens", "position": 4, "favor": 50
    }})
    with pytest.raises(ValueError, match="actual owned Shrine"):
        page._form_config()
    page.set_shrine({"account_id": "alpha", "shrine": {
        "city_id": 101, "city_name": "Athens", "position": 4, "favor": 50
    }})
    editor.table.item(3, 0).setCheckState(Qt.Checked)
    assert page._form_config() == {
        "godids": [4], "mode": 1, "times": 1,
    }
    page.set_shrine_unavailable("alpha")
    with pytest.raises(ValueError, match="actual owned Shrine"):
        page._form_config()


def test_external_city_selection_rejects_stale_lookup_and_preserves_own_origins(app):
    editor = ShipmentRoutesEditor()
    editor.set_cities([{"id": 101, "name": "Home"}])
    editor.x.setValue(50)
    editor.y.setValue(60)
    calls = []
    editor.lookup_requested.connect(lambda *args: calls.append(args))
    editor._lookup()
    result = {"x": 50, "y": 60, "cities": [
        {"id": 999, "recipient": 888, "island": 44, "name": "Town", "owner": "Other"}
    ]}
    editor.set_external(result, "stale")
    assert not editor.add_button.isEnabled()
    editor.set_external(result, calls[0][2])
    assert editor.add_button.isEnabled()
    editor.add_route()
    source, target = editor.table.cellWidget(0, 0), editor.table.cellWidget(0, 1)
    assert source.count() == 2 and target.count() == 3
    source.setCurrentIndex(1)
    target.setCurrentIndex(2)
    editor.table.cellWidget(0, 2).setValue(50)
    assert editor.to_config() == [{"from": 101, "to": 999, "recipient": 888, "island": 44,
                                   "resources": [50, 0, 0, 0, 0]}]
    assert "Town — Other" in editor.summary()
    editor.x.setValue(51)
    assert target.currentIndex() == 0
    with pytest.raises(ValueError):
        editor.to_config()
    editor.close()


def test_shipment_requires_current_capacity_ticket(page, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    set_native(page, "sendResources", [field("routes", required=True), field("useFreighters", "boolean", default=False)])
    page.set_preflight({"account_id": "alpha", "task": "sendResources", "ready": True, "reason": "none"})
    editor = page._form_inputs["routes"]
    editor.add_route()
    editor.table.cellWidget(0,0).setCurrentIndex(1)
    editor.table.cellWidget(0,1).setCurrentIndex(2)
    editor.table.cellWidget(0,2).setValue(50)
    calls = []
    page.shipment_preview_requested.connect(lambda *args: calls.append(args))
    page._request_native_preview()
    assert not page.start_button.isEnabled()
    draft = calls[0][1]
    result = {"account_id": "alpha", "draft": draft, "ready": True, "preview_id": "a"*43,
              "expires_in": 120, "available_ships": 1, "total_ships": 2, "capacity": 100,
              "routes": [{"origin_name": "Athens", "destination_name": "Sparta",
                          "resources": [50,0,0,0,0], "stock": [100]*5,
                          "first_load_limit": 50, "minimum_loads": 1,
                          "destination_space": [100]*5}]}
    page.set_shipment_preview(result, "wrong")
    assert not page.start_button.isEnabled()
    page.set_shipment_preview(result, calls[0][2])
    assert page.start_button.isEnabled()
    launches = []
    page.launch_requested.connect(lambda *args: launches.append(args))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.Yes)
    page.confirm_box.setChecked(True)
    page._start()
    assert launches[0][:3] == ("alpha", "sendResources", {"preview_id": "a"*43})


def test_recurring_external_destination_editor(page):
    from daedalus.engine_registry import inspect_engine
    task = "resourceTransportManager"
    capability = next(c for c in inspect_engine() if c.name == task)
    page.set_capabilities([capability.to_dict()], enabled=True)
    page.set_cities("alpha", CITIES)
    editor = page._form_inputs["destination_city"]
    page._form_inputs["mode"].setCurrentIndex(0)
    calls = []
    page.island_destinations_requested.connect(lambda *args:calls.append(args))
    editor.x.setValue(50)
    editor.y.setValue(60)
    editor._lookup()
    assert calls[-1][:3] == ("alpha", 50, 60)
    result = {"account_id":"alpha","x":50,"y":60,"cities":[
        {"id":999,"recipient":888,"island":44,"name":"Town","owner":"Other"}
    ]}
    page.set_island_destinations(result, "stale")
    assert editor.picker.count() == 4
    page.set_island_destinations(result, calls[-1][3])
    editor.picker.setCurrentIndex(4)
    assert editor.to_config() == {"destination_city":999,"island":44,"recipient":888}
    page._form_inputs["origin_cities"].item(0).setCheckState(Qt.Checked)
    page._form_inputs["send_mode"].setCurrentIndex(0)
    page._form_inputs["resource_config"].values[0].setValue(50)
    config = page._form_config()
    assert config["origin_cities"] == [101]
    assert config["recipient"] == 888
    editor.x.setValue(51)
    with pytest.raises(ValueError):
        editor.to_config()
