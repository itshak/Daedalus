"""Validated fixed tavern observations and one-shot review drafts."""


def validate_serving_options(value, current, wine):
    if value is None:
        return None
    if (not isinstance(value, list) or not 1 <= len(value) <= 151
            or any(not isinstance(row, list) or len(row) != 2
                   or type(row[0]) is not int or not 0 <= row[0] <= 150
                   or type(row[1]) is not int or not 0 <= row[1] <= 10**9 for row in value)):
        raise ValueError("Invalid tavern serving options")
    levels = dict(value)
    if len(levels) != len(value) or current not in levels or levels[current] != wine:
        raise ValueError("Inconsistent tavern serving options")
    return value


def fixed_tavern_review(rows, percentage):
    if type(percentage) is not int or not 0 <= percentage <= 100:
        raise ValueError("Choose a percentage from 0 to 100")
    result = []
    for row in rows:
        current, wine = row["serving_level"], row["wine_per_hour"]
        options = validate_serving_options(row.get("serving_options"), current, wine)
        if options is None:
            raise ValueError("Serving choices unavailable for a selected tavern")
        levels = dict(options)
        maximum = max(levels)
        target = maximum * percentage // 100
        if target not in levels:
            raise ValueError("Target serving unavailable")
        result.append({"city_id": row["city_id"], "city_name": row["city_name"],
                       "current_level": current, "max_level": maximum, "target_level": target,
                       "current_wine": wine, "target_wine": levels[target]})
    return validate_fixed_tavern({"percentage": percentage, "rows": result})


def validate_fixed_tavern(value):
    if (not isinstance(value, dict) or set(value) != {"percentage", "rows"}
            or type(value["percentage"]) is not int or not 0 <= value["percentage"] <= 100
            or not isinstance(value["rows"], list) or not 1 <= len(value["rows"]) <= 100):
        raise ValueError("Invalid fixed tavern review")
    seen = set()
    for row in value["rows"]:
        if (not isinstance(row, dict) or set(row) != {"city_id", "city_name", "current_level", "max_level",
                    "target_level", "current_wine", "target_wine"}
                or type(row["city_id"]) is not int or not 0 < row["city_id"] < 10**12
                or row["city_id"] in seen or not isinstance(row["city_name"], str)
                or not 0 < len(row["city_name"]) <= 100
                or any(ord(c) < 32 or c in "<>" for c in row["city_name"])
                or type(row["max_level"]) is not int or not 0 <= row["max_level"] <= 150
                or any(type(row[k]) is not int or not 0 <= row[k] <= row["max_level"]
                       for k in ("current_level", "target_level"))
                or row["target_level"] != row["max_level"] * value["percentage"] // 100
                or any(type(row[k]) is not int or not 0 <= row[k] <= 10**9
                       for k in ("current_wine", "target_wine"))):
            raise ValueError("Invalid reviewed tavern row")
        seen.add(row["city_id"])
    return value
