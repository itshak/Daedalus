"""Strict nonsecret research advisor projection and selection."""
from __future__ import annotations

import re


def validate_study_choice(row):
    if (not isinstance(row, dict) or set(row) != {"index", "name", "research_type"}
            or type(row["index"]) is not int or not 0 <= row["index"] <= 99
            or not isinstance(row["name"], str) or not 0 < len(row["name"]) <= 160
            or any(ord(c) < 32 or c in "<>" for c in row["name"])
            or not isinstance(row["research_type"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", row["research_type"])):
        raise ValueError("Invalid research advisor choice")
    return dict(row)


def validate_studies(rows):
    if rows is None:
        return None
    if not isinstance(rows, list) or len(rows) > 16:
        raise ValueError("Invalid research advisor inventory")
    result = [validate_study_choice(row) for row in rows]
    if (len({row["index"] for row in result}) != len(result)
            or len({row["research_type"] for row in result}) != len(result)):
        raise ValueError("Ambiguous research advisor choices")
    return result
