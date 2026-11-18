"""Explicit synthetic demonstration data for the desktop; never contacts Ikariam.

Used ONLY when a backend operator passes --demo. No credentials, login,
network calls, IPC descriptors, real account TOML or game sessions are used.
"""

from __future__ import annotations

from datetime import UTC, datetime

from daedalus.accounts import Account
from daedalus.warehouse import CityWarehouseSnapshot, WarehouseResources


def demo_accounts() -> list[Account]:
    return [
        Account("demo_alpha", "s999-en", "DemoExplorer", "DEMO — Explorer", True),
        Account("demo_beta", "s998-en", "DemoMerchant", "DEMO — Merchant", True),
    ]


def demo_warehouses(account_id: str) -> list[CityWarehouseSnapshot]:
    """Deterministic resource values, current capture time explicitly synthetic."""
    if account_id not in {account.id for account in demo_accounts()}:
        raise KeyError("Unknown demo account")
    captured = datetime.now(UTC).isoformat()

    def snapshot(
        city_id: int, city: str, island: str, values: dict[str, int | None], capacity: int,
    ) -> CityWarehouseSnapshot:
        return CityWarehouseSnapshot(
            account_id=account_id,
            city_id=city_id,
            city_name="DEMO " + city,
            captured_at=captured,
            island=island,
            resources=WarehouseResources(unsecured=values, capacity=capacity),
        )

    if account_id == "demo_alpha":
        return [
            snapshot(101, "Athens", "1:2", {
                "wood": 225_000, "wine": 75_000, "marble": 15_000,
                "glass": None, "sulfur": 0,
            }, 500_000),
            snapshot(102, "Sparta", "1:2", {
                "wood": 60_000, "wine": 25_000, "marble": None,
                "glass": 500, "sulfur": 0,
            }, 200_000),
        ]
    return [
        snapshot(201, "Miletus", "3:4", {
            "wood": 44_000, "wine": 36_000, "marble": 12_000,
            "glass": 0, "sulfur": None,
        }, 220_000),
    ]


def demo_cities(account_id: str) -> list[dict[str, object]]:
    return [
        {"id": warehouse.city_id, "name": warehouse.city_name,
         "coords": warehouse.island, "tradegood": "demo"}
        for warehouse in demo_warehouses(account_id)
    ]
