"""Synthetic warehouse data tests preserve old filtering and export behavior."""

import csv
import io
import json

from daedalus.reporting import report_csv, report_json, report_txt, rows_for_warehouse


def sample():
    account = {"id": "alpha", "label": "Primary", "world": "s301-en"}
    cities = [
        {
            "city_id": 12,
            "city_name": "Athens",
            "captured_at": "2026-11-18T10:00:00+00:00",
            "resources": {
                "unsecured": {"wood": 150_000, "wine": 80_000, "marble": 0, "glass": 0, "sulfur": 0},
                "capacity": 500_000,
            },
        },
        {
            "city_id": 13,
            "city_name": "Ephesus",
            "resources": {"unsecured": {"wood": 12_000, "wine": None}, "capacity": None},
        },
    ]
    return account, cities


def test_filter_220k_uses_sum_across_goods():
    account, cities = sample()
    rows = rows_for_warehouse(account, cities, only_220k=True)
    assert len(rows) == 1
    assert rows[0]["city"] == "Athens"
    assert rows[0]["incomplete"] is False
    assert rows[0]["wood"] == 150_000


def test_unknown_values_are_not_silently_zeroed():
    account, cities = sample()
    rows = rows_for_warehouse(account, cities)
    assert rows[1]["marble"] is None
    assert rows[1]["capacity"] is None
    assert rows[1]["incomplete"] is True
    assert rows[0]["marble"] == 0


def test_csv_and_json_export_round_trip_unicode():
    account, cities = sample()
    cities[0]["city_name"] = "Éphesos"
    rows = rows_for_warehouse(account, cities)
    text_csv = report_csv(rows)
    parsed = list(csv.DictReader(io.StringIO(text_csv)))
    assert parsed[0]["city"] == "Éphesos"
    assert parsed[0]["wood"] == "150000"
    assert parsed[1]["wine"] == ""
    parsed_json = json.loads(report_json(rows))
    assert parsed_json[0]["city"] == "Éphesos"
    assert parsed_json[1]["glass"] is None


def test_missing_resources_untouched_and_not_fabricated():
    account = {"id": "test", "world": "s301-en"}
    snapshots = [{"city_name": "Empty", "resources": {}}]
    rows = rows_for_warehouse(account, snapshots)
    assert all(rows[0][k] is None for k in ("wood", "wine", "marble", "glass", "sulfur"))
    assert rows[0]["incomplete"] is True
    assert rows_for_warehouse(account, snapshots, only_220k=True) == []


def test_text_export_groups_islands_without_turning_unknown_resources_into_zero():
    account, cities = sample()
    cities[0]["island"] = "10:20"
    cities[1]["island"] = "10:20"
    cities[1]["city_name"] = "Éphesos"
    rows = rows_for_warehouse(account, cities)
    text = report_txt(rows)
    assert text.count("Island 10:20") == 1
    assert text.index("Athens") < text.index("Éphesos")
    assert "marble: 0" in text
    assert "glass: —" in text
    assert "wine: —" in text
    assert "capacity: —" in text
    assert "password" not in text


def test_missing_or_malformed_island_is_unknown_and_csv_json_stay_compatible():
    account, cities = sample()
    cities[0]["island"] = "not-an-island-or-token"
    cities[1]["island"] = "3:4"
    rows = rows_for_warehouse(account, cities)
    assert rows[0]["island"] is None
    assert rows[1]["island"] == "3:4"
    assert "Unknown" in report_txt(rows)
    csv_rows = list(csv.DictReader(io.StringIO(report_csv(rows))))
    assert csv_rows[0]["island"] == ""
    assert csv_rows[1]["island"] == "3:4"
    json_rows = json.loads(report_json(rows))
    assert json_rows[0]["island"] is None
