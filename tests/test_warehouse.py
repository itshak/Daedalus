"""Synthetic warehouse markup and mock existing IkaBot session."""

import pytest

from daedalus.warehouse import (
    WarehouseParseError,
    fetch_warehouse,
    parse_amount,
    parse_warehouse_html,
)


def test_exact_tooltip_overrides_rounded_visible_value():
    markup = (
        '<span id="js_plunderable_wood">2.97M'
        '<div class="tooltip">2,970,123</div></span>'
        '<span id="js_plunderable_wine">17.254</span>'
        '<span id="js_plunderable_marble">0</span>'
        '<span id="js_plunderable_crystal">5,123</span>'
        '<span id="js_plunderable_sulfur">999</span>'
        '<span id="js_capacity_wood">1,000,000</span>'
    )
    values = parse_warehouse_html(markup)
    assert values.unsecured == {
        "wood": 2970123, "wine": 17254, "marble": 0, "glass": 5123, "sulfur": 999
    }
    assert values.capacity == 1000000


def test_partial_values_remain_unknown_not_zero():
    values = parse_warehouse_html('<span id="js_plunderable_wood">0</span>')
    assert values.unsecured["wood"] == 0
    assert values.unsecured["glass"] is None
    assert values.capacity is None


def test_html_with_no_values_is_not_interpreted_as_zero():
    with pytest.raises(WarehouseParseError, match="No unsecured"):
        parse_warehouse_html("<html>Login required</html>")


@pytest.mark.parametrize("text, expected", [
    ("0", 0),
    ("12 345", 12345),
    ("12.345", 12345),
    ("12,345", 12345),
    ("2.97M", 2970000),
    ("4K", 4000),
    ("1,1B", 1100000000),
])
def test_amount_parser(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["-4", "2,22", "unknown", "12/34", ""])
def test_invalid_amounts_are_rejected(text):
    with pytest.raises(WarehouseParseError):
        parse_amount(text)


def test_conflicting_resource_spans_are_rejected():
    with pytest.raises(WarehouseParseError, match="Conflicting"):
        parse_warehouse_html(
            '<span id="js_plunderable_wine">10</span>'
            '<span id="js_plunderable_wine">12</span>'
        )


def test_uses_existing_session_get_without_login():
    class FakeSession:
        def __init__(self):
            self.calls = []

        def get(self, url, *, noIndex):
            self.calls.append((url, noIndex))
            return '<span id="js_plunderable_wine">2,000</span>'

    session = FakeSession()
    snapshot = fetch_warehouse(session, account_id="example", city_id=123, city_name="Athens")
    assert session.calls == [("view=warehouse&cityId=123", True)]
    assert snapshot.resources.unsecured["wine"] == 2000
    assert snapshot.resources.unsecured["wood"] is None
    assert snapshot.account_id == "example"
    assert snapshot.city_name == "Athens"
    assert snapshot.captured_at.endswith("+00:00")


def test_rejects_bad_city_id_before_get():
    class BombSession:
        def get(self, *args, **kwargs):
            raise AssertionError("No network call should happen")

    with pytest.raises(ValueError, match="positive integer"):
        fetch_warehouse(BombSession(), account_id="example", city_id=0, city_name="Athens")
