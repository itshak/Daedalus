"""Read-only warehouse data extraction using an existing IkaBot game session.

No Selenium, authentication, or game-network implementation is added here.
The only optional network call is delegated to an already-authenticated IkaBot
Session supplied by the account worker.
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Protocol

RESOURCES = ("wood", "wine", "marble", "glass", "sulfur")
_SUFFIXES = {"K": 1000, "M": 1000000, "B": 1000000000}
_SPAN_RE = re.compile(
    r'<span\b[^>]*\bid=["\']js_(plunderable|capacity)_([a-z]+)["\'][^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
_TOOLTIP_RE = re.compile(
    r'<div\b[^>]*\bclass=["\'][^"\']*\btooltip\b[^"\']*["\'][^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
_GROUPED = re.compile(r"(?:\d{1,3}(?:[,.\s]\d{3})+|\d+)\Z")
_ABBREV = re.compile(r"(\d+(?:[.,]\d+)?)([KMB])\Z", re.IGNORECASE)


class WarehouseParseError(ValueError):
    """The returned HTML did not contain interpretable warehouse data."""


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fragments: list[str] = []

    def handle_data(self, data: str) -> None:
        self.fragments.append(data)


def _text(fragment: str) -> str:
    parser = _Text()
    parser.feed(fragment)
    return html.unescape("".join(parser.fragments)).strip()


def parse_amount(value: str) -> int:
    """Parse formatted exact amounts and abbreviated visible quantities."""
    normalized = html.unescape(value).replace("\u202f", " ").replace("\xa0", " ")
    normalized = re.sub(r"[\u200e\u200f\u2066\u2067\u2068\u2069]", "", normalized).strip()
    abbreviated = _ABBREV.fullmatch(normalized)
    if abbreviated:
        try:
            decimal_value = Decimal(abbreviated[1].replace(",", "."))
            return int(
                (decimal_value * _SUFFIXES[abbreviated[2].upper()]).to_integral_value(
                    rounding=ROUND_HALF_UP
                )
            )
        except InvalidOperation as exc:
            raise WarehouseParseError("Invalid abbreviated warehouse amount") from exc
    if not _GROUPED.fullmatch(normalized):
        raise WarehouseParseError("Invalid numeric warehouse amount")
    return int(re.sub(r"[,.\s]", "", normalized))


@dataclass(frozen=True)
class WarehouseResources:
    """Unknown resource values are None, never silently interpreted as zero."""

    unsecured: dict[str, int | None]
    capacity: int | None
    total: dict[str, int | None] = field(default_factory=lambda: dict.fromkeys(RESOURCES))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CityWarehouseSnapshot:
    account_id: str
    city_id: int
    city_name: str
    captured_at: str
    resources: WarehouseResources

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_warehouse_html(markup: str) -> WarehouseResources:
    values: dict[str, int | None] = dict.fromkeys(RESOURCES)
    capacity: int | None = None
    found_unsecured = False
    for kind, original_resource, content in _SPAN_RE.findall(markup):
        resource = "glass" if original_resource.casefold() == "crystal" else original_resource.casefold()
        if resource not in RESOURCES:
            continue
        tooltip = _TOOLTIP_RE.search(content)
        exact = _text(tooltip[1]) if tooltip else _text(content)
        amount = parse_amount(exact)
        if kind.casefold() == "plunderable":
            if values[resource] is not None and values[resource] != amount:
                raise WarehouseParseError(f"Conflicting {resource} unsecured values")
            values[resource] = amount
            found_unsecured = True
        elif capacity is None:
            capacity = amount
    if not found_unsecured:
        raise WarehouseParseError("No unsecured warehouse values found")
    return WarehouseResources(unsecured=values, capacity=capacity)


class ExistingGameSession(Protocol):
    def get(self, url: str = "", *, noIndex: bool = False) -> str: ...


def fetch_warehouse(
    session: ExistingGameSession,
    *,
    account_id: str,
    city_id: int,
    city_name: str,
) -> CityWarehouseSnapshot:
    """Use the engine's existing authenticated Session.get, not a new HTTP client."""
    if type(city_id) is not int or city_id <= 0:
        raise ValueError("city_id must be a positive integer")
    markup = session.get(f"view=warehouse&cityId={city_id}", noIndex=True)
    if not isinstance(markup, str):
        raise WarehouseParseError("Warehouse response is not HTML")
    return CityWarehouseSnapshot(
        account_id=account_id,
        city_id=city_id,
        city_name=city_name,
        captured_at=datetime.now(UTC).isoformat(),
        resources=parse_warehouse_html(markup),
    )
