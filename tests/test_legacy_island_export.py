"""Golden legacy island clipboard format from private itshak/ikabot.

The reference is src/ikabot/report.py::format_text_islands and its synthetic
tests/test_report.py fixture. Deliberately assert the complete string, not
only presence of headers: tabs, commas, blank lines and final newline matter.
"""

import csv
import io
import json

from daedalus.reporting import report_csv, report_json, report_txt_islands, rows_for_warehouse


def make_rows():
    return [
        {
            "account": "xiaomi", "city": "Ариэль", "island": "98:9",
            "island_resource": "wine", "world": "s53-ru",
            "wood": 146_483, "wine": 2_970_183, "marble": 1_055_874,
            "glass": 3_120_000, "sulfur": 0, "capacity": 3_947_218,
        },
        {
            "account": "xiaomi", "city": "Иерусалим", "island": "98:7",
            "island_resource": "glass", "world": "s53-ru",
            "wood": 100, "wine": 200, "marble": 300,
            "glass": 400, "sulfur": 500, "capacity": 1_000,
        },
        {
            "account": "another account", "city": "Тирош", "island": "98:7",
            "island_resource": "glass", "world": "s53-ru",
            "wood": 10, "wine": 20, "marble": 30,
            "glass": 40, "sulfur": 50, "capacity": 100,
        },
    ]


def test_exact_legacy_island_text_matches_original_fixture_byte_for_byte():
    expected = (
        "===== 98:9 (Вино) =====\n"
        "\n"
        "Ариэль (3,947,218)\n"
        "============\n"
        "Лес:\t146,483\n"
        "Вино:\t2,970,183\n"
        "Мрам:\t1,055,874\n"
        "Хруст:\t3,120,000\n"
        "Сера:\t0\n"
        "\n"
        "===== 98:7 (Хруст) =====\n"
        "\n"
        "Иерусалим (1,000)\n"
        "============\n"
        "Лес:\t100\n"
        "Вино:\t200\n"
        "Мрам:\t300\n"
        "Хруст:\t400\n"
        "Сера:\t500\n"
        "\n"
        "Тирош (100)\n"
        "============\n"
        "Лес:\t10\n"
        "Вино:\t20\n"
        "Мрам:\t30\n"
        "Хруст:\t40\n"
        "Сера:\t50\n"
    )
    assert report_txt_islands(make_rows()) == expected
    assert "xiaomi" not in expected
    assert "another account" not in expected


def test_legacy_island_sorting_resource_then_numeric_coords_and_descending_total():
    data = [
        {"city": "s1", "island": "1:1", "island_resource": "sulfur", "wood": 1},
        {"city": "m98", "island": "98:9", "island_resource": "marble", "wood": 1},
        {"city": "m96eleven", "island": "96:11", "island_resource": "marble", "wood": 1},
        {"city": "m96six", "island": "96:6", "island_resource": "marble", "wood": 1},
        {"city": "m96eight", "island": "96:8", "island_resource": "marble", "wood": 1},
        {"city": "w1", "island": "2:1", "island_resource": "wine", "wood": 1},
        {"city": "g1", "island": "3:1", "island_resource": "glass", "wood": 1},
        {"city": "small", "island": "3:1", "island_resource": "glass", "wood": 9},
        {"city": "big", "island": "3:1", "island_resource": "glass", "wood": 500_000},
    ]
    txt = report_txt_islands(data)
    headers = [
        "===== 96:6 (Мрам) =====", "===== 96:8 (Мрам) =====",
        "===== 96:11 (Мрам) =====", "===== 98:9 (Мрам) =====",
        "===== 2:1 (Вино) =====", "===== 3:1 (Хруст) =====",
        "===== 1:1 (Сера) =====",
    ]
    positions = [txt.index(x) for x in headers]
    assert positions == sorted(positions)
    assert txt.index("big (") < txt.index("small (") < txt.index("g1 (")


def test_220k_filter_applies_before_legacy_island_format():
    account = {"id": "alpha", "label": "Primary", "world": "s53-ru"}
    city_data = [
        {"city_name": "keep", "island": "1:2", "island_resource": "wine",
         "resources": {"unsecured": {"wood": 110_000, "wine": 110_000}, "capacity": 1_000}},
        {"city_name": "drop", "island": "1:2", "island_resource": "wine",
         "resources": {"unsecured": {"wood": 15_000}, "capacity": 2_000}},
    ]
    rows = rows_for_warehouse(account, city_data, only_220k=True)
    assert [row["city"] for row in rows] == ["keep"]
    assert "drop" not in report_txt_islands(rows)
    assert "===== 1:2 (Вино) =====" in report_txt_islands(rows)


def test_missing_amount_is_not_falsely_exported_as_zero_and_empty_is_empty():
    assert report_txt_islands([]) == ""
    text = report_txt_islands([{
        "account": "Private account", "city": "Unknown",
        "island": None, "island_resource": "",
        "wood": 0, "wine": None, "marble": None, "glass": None,
        "sulfur": None, "capacity": None,
    }])
    assert text.startswith("===== Unknown =====\n\nUnknown (—)\n")
    assert "Лес:\t0\n" in text
    assert "Вино:\t—\n" in text
    assert "Private account" not in text


def test_new_island_metadata_does_not_break_existing_csv_json_export_schema():
    rows = make_rows()
    # The island resource is needed for exact island headings, but must not
    # quietly introduce an extra key into existing machine-readable exports.
    parsed_json = json.loads(report_json(rows))
    assert "island_resource" not in parsed_json[0]
    parsed_csv = list(csv.DictReader(io.StringIO(report_csv(rows))))
    assert "island_resource" not in parsed_csv[0]
    assert parsed_csv[0]["wood"] == "146483"
    assert "===== 98:9 (Вино) =====" in report_txt_islands(rows)
