"""Attach read-only to an already-running IkaBot IPC worker.

No game login, session restore, process creation, or task launch occurs here.
Daedalus only asks the engine for identities and already-authenticated cities.
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from daedalus.accounts import Account
from daedalus.reviewed_operations import (
    validate_attack_inventory,
    validate_attack_plan,
    validate_build_inventory,
    validate_build_plan,
    validate_grind_plan,
    validate_island_destinations,
    validate_layout_plan,
    validate_shipment_plan,
    validate_station_plan,
    validate_vacation_plan,
    validate_worker_plan,
    validated_attack_draft,
    validated_build_draft,
    validated_coordinates,
    validated_grind_draft,
    validated_layout_draft,
    validated_shipment_draft,
    validated_station_draft,
    validated_worker_draft,
)
from daedalus.warehouse import (
    RESOURCES,
    CityWarehouseSnapshot,
    WarehouseParseError,
    WarehouseResources,
    parse_amount,
)

_MAX_DESCRIPTOR_BYTES = 4096
_MAX_REPLY_BYTES = 512 * 1024
_ALLOWED = frozenset({
    "ping", "list_sessions", "preview_shipments_existing", "island_destinations_existing", "list_cities_existing", "warehouse_snapshots_existing",
    "validate_session_existing", "task_preflight_existing", "list_buildings_existing",
    "preview_vacation_existing", "list_attack_units_existing", "preview_attack_existing", "preview_grind_existing", "preview_station_existing", "list_build_options_existing", "preview_build_existing", "preview_layout_existing", "preview_workers_existing", "production_inventory_existing", "preview_donation_existing", "preview_construction_existing", "list_workshop_upgrades_existing",
    "list_trainables_existing", "market_quotes_existing",
    "list_academies_existing", "list_taverns_existing",
    "list_miracles_existing", "shrine_status_existing", "administrative_status_existing",
    "list_pirate_fortresses_existing",
    "military_overview_existing", "ship_movements_existing",
})


class EngineIPCUnavailable(RuntimeError):
    """A safe, nonsecret reason why no compatible engine is reachable."""


class FillPreviewUnavailable(EngineIPCUnavailable):
    """Only fixed, nonsecret warehouse preview errors are permitted."""

    def __init__(self, reason):
        from daedalus.fill_warehouse_review import FILL_PREVIEW_MESSAGES

        if not isinstance(reason, str) or reason not in FILL_PREVIEW_MESSAGES:
            raise EngineIPCUnavailable("Invalid warehouse preview failure")
        self.reason = reason
        super().__init__(FILL_PREVIEW_MESSAGES[reason])


class EngineTaskRejected(RuntimeError):
    """Proven engine-side rejection before any child task process starts."""

    def __init__(self, reason: str):
        if reason not in {"invalid_configuration", "notifications_required"}:
            raise EngineIPCUnavailable("Engine task rejection contained an invalid reason")
        self.reason = reason
        super().__init__("Engine rejected this task before launch")


def default_ipc_descriptor_path() -> Path:
    """The engine's public IPC discovery location, never inside this repository."""
    return Path.home() / ".ikabot" / "ipc.json"


def _is_exact_identity(value: object, account: Account) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("world"), str)
        and isinstance(value.get("player"), str)
        and value["world"].casefold() == account.world.casefold()
        and value["player"].casefold() == account.player.casefold()
    )


class ExistingIPCClient:
    """Authenticated local IPC with descriptor validation and strict allowlist."""

    def __init__(self, descriptor_path: str | Path | None = None) -> None:
        self._path = (
            Path(descriptor_path).expanduser()
            if descriptor_path is not None
            else default_ipc_descriptor_path()
        )

    def _descriptor(self) -> tuple[int, str]:
        path = self._path
        try:
            if path.is_symlink() or path.parent.is_symlink():
                raise EngineIPCUnavailable("IPC descriptor cannot be a symlink")
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_DESCRIPTOR_BYTES:
                raise EngineIPCUnavailable("IPC descriptor is invalid")
            if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise EngineIPCUnavailable("IPC descriptor must be owner-only")
            with path.open("rb") as handle:
                raw = handle.read(_MAX_DESCRIPTOR_BYTES + 1)
            if len(raw) > _MAX_DESCRIPTOR_BYTES:
                raise EngineIPCUnavailable("IPC descriptor is too large")
            descriptor = json.loads(raw)
        except (OSError, ValueError, TypeError) as exc:
            raise EngineIPCUnavailable("No readable, valid IkaBot IPC descriptor") from exc
        if not isinstance(descriptor, dict):
            raise EngineIPCUnavailable("IPC descriptor must be an object")
        if descriptor.get("host") != "127.0.0.1":
            raise EngineIPCUnavailable("IkaBot IPC must be bound to loopback")
        port, pid, authkey = (
            descriptor.get("port"),
            descriptor.get("pid"),
            descriptor.get("authkey"),
        )
        if type(port) is not int or not 0 < port < 65536:
            raise EngineIPCUnavailable("Invalid IkaBot IPC port")
        if type(pid) is not int or pid <= 0:
            raise EngineIPCUnavailable("Invalid IkaBot IPC owner PID")
        if not isinstance(authkey, str) or len(authkey) != 64:
            raise EngineIPCUnavailable("Invalid IkaBot IPC authentication key")
        try:
            bytes.fromhex(authkey)
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid IkaBot IPC authentication key") from exc
        # Windows os.kill(pid, 0) may call TerminateProcess rather than probing.
        # On Windows, rely on authenticated loopback connection and socket timeout.
        if os.name != "nt":
            try:
                os.kill(pid, 0)
            except ProcessLookupError as exc:
                raise EngineIPCUnavailable("IkaBot IPC owner process no longer exists") from exc
            except PermissionError as exc:
                raise EngineIPCUnavailable("Cannot verify IkaBot IPC owner") from exc
        return port, authkey

    def request(self, action: str, *, account: Account | None = None,
                city_id: int | None = None,
                upgrades: list[dict[str, int]] | None = None,
                construction_supply: dict[str, object] | None = None,
                train_troops: bool | None = None,
                resource_type: int | None = None,
                market_side: str | None = None,
                project: str | None = None, amount: int | None = None,
                worker_task: str | None = None, worker_draft: dict[str, object] | None = None,
                template_city_id: int | None = None, build_draft: dict[str, int] | None = None,
                station_draft: dict[str, object] | None = None,
                grind_draft: dict[str, object] | None = None,
                attack_draft: dict[str, object] | None = None,
                coordinates: tuple[int, int] | None = None,
                shipment_draft: dict[str, object] | None = None) -> dict[str, Any]:
        """Issue only a fixed nonmutating action; never expose an unrestricted RPC."""
        if action not in _ALLOWED:
            raise ValueError("This IPC bridge is read-only")
        if action in {
            "preview_shipments_existing", "island_destinations_existing", "list_cities_existing", "warehouse_snapshots_existing", "validate_session_existing",
            "task_preflight_existing", "list_buildings_existing",
            "preview_vacation_existing", "list_attack_units_existing", "preview_attack_existing", "preview_grind_existing", "preview_station_existing", "list_build_options_existing", "preview_build_existing", "preview_layout_existing", "preview_workers_existing", "production_inventory_existing", "preview_donation_existing", "preview_construction_existing", "list_workshop_upgrades_existing",
            "list_trainables_existing", "market_quotes_existing",
            "list_academies_existing", "list_taverns_existing",
            "list_miracles_existing", "shrine_status_existing", "administrative_status_existing",
            "list_pirate_fortresses_existing",
    "military_overview_existing", "ship_movements_existing",
        } and account is None:
            raise ValueError("Explicit account identity is required")
        if account is not None and not account.enabled:
            raise ValueError("Account is disabled")
        payload: dict[str, object] = {"action": action}
        if account is not None:
            payload.update(world=account.world, player=account.player)
        if action in {"list_buildings_existing", "preview_construction_existing",
                      "preview_donation_existing", "preview_workers_existing", "production_inventory_existing", "preview_layout_existing",
                      "list_build_options_existing", "preview_build_existing", "preview_vacation_existing", "list_attack_units_existing", "preview_attack_existing", "preview_grind_existing", "preview_station_existing",
                      "list_workshop_upgrades_existing", "list_trainables_existing",
                      "market_quotes_existing"}:
            if type(city_id) is not int or not 0 < city_id < 10**12:
                raise ValueError("Choose a valid city")
            payload["city_id"] = city_id
            if action == "preview_construction_existing":
                if not isinstance(upgrades, list) or not 0 < len(upgrades) <= 12:
                    raise ValueError("Choose valid construction upgrades")
                for upgrade in upgrades:
                    if (not isinstance(upgrade, dict)
                            or set(upgrade) != {"position", "target_level"}
                            or type(upgrade["position"]) is not int
                            or type(upgrade["target_level"]) is not int):
                        raise ValueError("Invalid construction upgrade")
                payload["upgrades"] = upgrades
                if construction_supply is not None:
                    from daedalus.reviewed_operations import validated_construction_supply

                    payload["supply"] = validated_construction_supply(city_id, construction_supply)
            elif upgrades is not None:
                raise ValueError("Upgrades are allowed only in a construction preview")
            if action == "list_trainables_existing":
                if type(train_troops) is not bool:
                    raise ValueError("Choose troops or ships")
                payload["train_troops"] = train_troops
            elif train_troops is not None:
                raise ValueError("Training mode is only supported for real unit discovery")
            if action == "market_quotes_existing":
                if (type(resource_type) is not int or not 0 <= resource_type <= 4
                        or market_side not in {"buy", "sell_to_offers", "create_offer"}):
                    raise ValueError("Choose a valid market product and action")
                payload["resource_type"] = resource_type
                payload["market_side"] = market_side
            elif resource_type is not None or market_side is not None:
                raise ValueError("Market filters may only be used for read-only quotes")
        elif (city_id is not None or upgrades is not None or train_troops is not None
              or resource_type is not None or market_side is not None):
            raise ValueError("City argument is not supported for this IPC action")
        if action == "preview_donation_existing":
            if project not in ("resource", "tradegood") or type(amount) is not int or not 1 <= amount <= 10**9:
                raise ValueError("Invalid donation draft")
            payload.update(project=project, amount=amount)
        elif project is not None or amount is not None:
            raise ValueError("Donation fields are allowed only for a donation preview")
        if action == "preview_workers_existing":
            payload.update(task=worker_task, **validated_worker_draft(worker_task, worker_draft))
        elif worker_task is not None or worker_draft is not None:
            raise ValueError("Worker fields are allowed only for a worker preview")
        if action == "preview_layout_existing":
            payload["template_city_id"] = validated_layout_draft(city_id, {"template_city_id": template_city_id})
        elif template_city_id is not None:
            raise ValueError("Unexpected layout template")
        if action == "preview_build_existing":
            payload.update(validated_build_draft(build_draft))
        elif build_draft is not None:
            raise ValueError("Unexpected new building draft")
        if action == "preview_station_existing":
            payload.update(validated_station_draft(city_id, station_draft))
        elif station_draft is not None:
            raise ValueError("Unexpected deployment draft")
        if action == "preview_grind_existing":
            payload.update(validated_grind_draft(city_id, grind_draft))
        elif grind_draft is not None:
            raise ValueError("Unexpected automatic attack draft")
        if action == "preview_attack_existing":
            payload.update(validated_attack_draft(city_id, attack_draft))
        elif attack_draft is not None:
            raise ValueError("Unexpected manual attack draft")
        if construction_supply is not None and action != "preview_construction_existing":
            raise ValueError("Unexpected construction supply")
        if action == "island_destinations_existing":
            if not isinstance(coordinates, tuple) or len(coordinates) != 2:
                raise ValueError("Choose an island")
            payload["x"], payload["y"] = validated_coordinates(*coordinates)
        elif coordinates is not None:
            raise ValueError("Unexpected island coordinates")
        if action == "preview_shipments_existing":
            payload.update(validated_shipment_draft(shipment_draft))
        elif shipment_draft is not None:
            raise ValueError("Unexpected shipment draft")
        return self._exchange(payload, read_timeout=60.0 if action in {
            "preview_shipments_existing", "island_destinations_existing",
            "preview_vacation_existing", "list_attack_units_existing", "preview_attack_existing", "preview_grind_existing", "preview_station_existing",
            "list_build_options_existing", "preview_build_existing",
            "preview_layout_existing",
            "preview_workers_existing", "production_inventory_existing",
            "preview_donation_existing",
            "preview_construction_existing", "military_overview_existing",
            "ship_movements_existing",
        } else 8.0)

    def _exchange(self, payload: dict[str, object], *, read_timeout: float = 8.0,
                  allow_task_rejection: bool = False) -> dict[str, Any]:
        """Internal authenticated transport; public read bridge remains allowlisted."""
        port, secret = self._descriptor()
        wire_data = {**payload, "authkey": secret}
        wire = (json.dumps(wire_data, separators=(",", ":")) + "\n").encode("utf-8")
        if len(wire) > 32768:
            raise ValueError("IPC request exceeds safe size limit")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2.0) as conn:
                conn.settimeout(read_timeout)
                conn.sendall(wire)
                data = bytearray()
                while len(data) <= _MAX_REPLY_BYTES:
                    chunk = conn.recv(min(65536, _MAX_REPLY_BYTES + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if b"\n" in chunk:
                        break
        except (OSError, TimeoutError) as exc:
            raise EngineIPCUnavailable("IkaBot IPC server is unavailable") from exc
        if len(data) > _MAX_REPLY_BYTES or b"\n" not in data:
            raise EngineIPCUnavailable("IkaBot IPC reply is invalid or oversized")
        try:
            reply = json.loads(bytes(data).split(b"\n", 1)[0])
        except (ValueError, UnicodeError) as exc:
            raise EngineIPCUnavailable("IkaBot IPC reply is not JSON") from exc
        if (allow_task_rejection and isinstance(reply, dict)
                and reply.get("status") == "rejected"):
            # Never expose raw engine error/traceback, only an audited code.
            raise EngineTaskRejected(reply.get("reason"))
        if (payload.get("action") == "preview_fill_existing" and isinstance(reply, dict)
                and reply.get("status") == "error" and "reason" in reply):
            raise FillPreviewUnavailable(reply["reason"])
        if not isinstance(reply, dict) or reply.get("status") != "ok":
            # Engine errors may contain account data or cookie fragments.
            raise EngineIPCUnavailable("IkaBot IPC request failed")
        return reply

    def list_sessions(self) -> list[dict[str, str]]:
        """Only nonsecret in-memory identities; do not reveal unrelated account emails."""
        rows = self.request("list_sessions").get("sessions")
        if not isinstance(rows, list) or len(rows) > 100:
            raise EngineIPCUnavailable("IkaBot IPC returned invalid session metadata")
        sessions = []
        for item in rows:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("world"), str)
                or not isinstance(item.get("player"), str)
                or not item["world"]
                or not item["player"]
            ):
                raise EngineIPCUnavailable("IkaBot IPC returned invalid session identity")
            sessions.append({"world": item["world"], "player": item["player"]})
        return sessions

    def has_account(self, account: Account) -> bool:
        return sum(_is_exact_identity(row, account) for row in self.list_sessions()) == 1

    def validate_account(self, account: Account) -> bool:
        """Verify real existing world session by fixed read-only game GET.

        Only enable this explicitly in session monitoring mode. An unrecognized
        response or old IkaBot IPC server fails closed; this cannot log in.
        """
        if not self.has_account(account):
            return False
        reply = self.request("validate_session_existing", account=account)
        if (
            not isinstance(reply.get("world"), str)
            or not isinstance(reply.get("username"), str)
            or reply["world"].casefold() != account.world.casefold()
            or reply["username"].casefold() != account.player.casefold()
            or type(reply.get("session_valid")) is not bool
            or type(reply.get("player_attested")) is not bool
            or (reply["session_valid"] and not reply["player_attested"])
        ):
            raise EngineIPCUnavailable("IkaBot session validation reply is invalid")
        # The boolean must come from a current world-server page, not from
        # session.username or saved-account metadata alone. Older IPC workers
        # lacking explicit attestation are deliberately incompatible.
        return reply["session_valid"] and reply["player_attested"]

    def cities(self, account: Account) -> list[dict[str, object]]:
        matches = sum(_is_exact_identity(row, account) for row in self.list_sessions())
        if matches != 1:
            raise EngineIPCUnavailable("No unique already-authenticated account session")
        response = self.request("list_cities_existing", account=account)
        if (
            not isinstance(response.get("world"), str)
            or not isinstance(response.get("username"), str)
            or response["world"].casefold() != account.world.casefold()
            or response["username"].casefold() != account.player.casefold()
        ):
            raise EngineIPCUnavailable("IkaBot IPC returned another account's data")
        rows = response.get("cities")
        if not isinstance(rows, list) or len(rows) > 500:
            raise EngineIPCUnavailable("IkaBot IPC returned invalid city data")
        result: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise EngineIPCUnavailable("IkaBot IPC returned malformed city data")
            city_id = row.get("id")
            name = row.get("name")
            if type(city_id) is not int or city_id <= 0 or not isinstance(name, str):
                raise EngineIPCUnavailable("IkaBot IPC returned invalid city identity")
            result.append(
                {
                    "id": city_id,
                    "name": name[:120],
                    "coords": str(row.get("coords", ""))[:40],
                    "tradegood": str(row.get("tradegood", ""))[:20],
                }
            )
        return result

    def fill_preview(self, account: Account, draft):
        from daedalus.fill_warehouse_review import draft_fill, validate_fill

        clean = draft_fill(draft)
        try:
            owned = {r["id"] for r in self.cities(account)}
        except EngineIPCUnavailable:
            raise FillPreviewUnavailable("fill_inventory_unavailable") from None
        if clean["destination_city"] not in owned or not account.enabled:
            raise FillPreviewUnavailable("fill_scope_changed")
        try:
            response = self._exchange({"action": "preview_fill_existing", "world": account.world,
                                       "player": account.player, "draft": clean}, read_timeout=90)
        except FillPreviewUnavailable:
            raise
        except EngineIPCUnavailable:
            raise FillPreviewUnavailable("fill_worker_unavailable") from None
        if not _is_exact_identity({"world": response.get("world"), "player": response.get("username")}, account):
            raise FillPreviewUnavailable("fill_scope_changed")
        try:
            result = validate_fill(clean, response.get("result"))
            if {r["city_id"] for r in result["sources"]} != owned - {clean["destination_city"]}:
                raise ValueError("Owned city scope changed")
            return result
        except (ValueError, KeyError, TypeError):
            raise FillPreviewUnavailable("fill_scope_changed") from None

    def recurring_preview(self, account: Account, task, draft):
        from daedalus.recurring_review import (
            RECURRING_TASKS,
            recurring_draft,
            route_scope,
            validate_recurring,
        )

        if task not in RECURRING_TASKS - {"autoPirate"} or not account.enabled:
            raise ValueError("Unsupported policy")
        clean = recurring_draft(task, draft)
        inventory = self.cities(account)
        owned = {r["id"] for r in inventory}
        if task in {"consolidateResources", "resourceTransportManager"}:
            sources, destinations = route_scope(task, clean)
            if any(i not in owned for i in sources) or any((i in owned) == ("recipient" in clean) for i in destinations):
                raise ValueError("Invalid recipient scope")
        if task == "donationBot" and not set(map(int, clean["cities_dict"])) <= owned:
            raise ValueError("Invalid donation scope")
        response = self._exchange({"action": "preview_recurring_existing", "task": task,
                                   "world": account.world, "player": account.player, "draft": clean},
                                  read_timeout=120)
        if not _is_exact_identity({"world": response.get("world"), "player": response.get("username")}, account):
            raise EngineIPCUnavailable("Invalid recurring scope")
        try:
            result = validate_recurring(task, clean, response.get("result"))
            if (task == "searchForIslandSpaces" and not clean["islandList"]
                    and set(result["islands"]) != {r["coords"] for r in inventory}):
                raise ValueError("Owned island scope changed")
            return result
        except (ValueError, KeyError, TypeError) as exc:
            raise EngineIPCUnavailable("Invalid recurring observation") from exc

    def native_reward_distribution_preview(self, account: Account, task, draft):
        from daedalus.daily_distribution_review import (
            daily_draft,
            distribution_draft,
            validate_daily,
            validate_distribution,
        )
        from daedalus.market_review import market_draft, validate_market_observation

        if task not in ("loginDaily", "distributeResources", "buyResources", "sellResources") or not account.enabled:
            raise ValueError("Unsupported preview")
        clean = (daily_draft(draft) if task == "loginDaily" else distribution_draft(draft)
                 if task == "distributeResources" else market_draft(task, draft))
        owned = {r["id"] for r in self.cities(account)}
        ids = ([clean[k] for k in ("wine_city", "wood_city", "luxury_city") if clean[k] is not None]
               if task == "loginDaily" else clean["cities_ids"] if task == "distributeResources"
               else [int((clean.get("city") or clean["city_to_buy_from"])["id"])])
        if any(i not in owned for i in ids):
            raise ValueError("Choose owned cities")
        action = ("preview_daily_rewards_existing" if task == "loginDaily" else "preview_distribution_existing"
                  if task == "distributeResources" else "preview_market_existing")
        data = self._exchange({"action": action, "world": account.world, "player": account.player,
                               "draft": clean, "task": task}, read_timeout=120.0)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid preview scope")
        try:
            observation = data["result"]
            if task == "loginDaily":
                validate_daily(clean, observation)
            elif task == "distributeResources":
                validate_distribution(clean, observation)
            else:
                validate_market_observation(task, clean, observation)
            return observation
        except (ValueError, KeyError, TypeError) as exc:
            raise EngineIPCUnavailable("Invalid operation preview") from exc

    def shipment_preview(self, account: Account, draft: dict[str, object]) -> dict[str, object]:
        clean = validated_shipment_draft(draft)
        owned = {row["id"] for row in self.cities(account)}
        if any(r["from"] not in owned or ((r["to"] in owned) == ("recipient" in r))
               for r in clean["routes"]):
            raise ValueError("Choose verified shipment cities")
        data = self.request("preview_shipments_existing", account=account, shipment_draft=clean)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid shipment scope")
        try:
            return {"account_id": account.id, **validate_shipment_plan(clean, data.get("plan"))}
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid shipment preview") from exc

    def island_destinations(self, account: Account, x: int, y: int) -> dict[str, object]:
        validated_coordinates(x, y)
        result = self.request("island_destinations_existing", account=account, coordinates=(x, y))
        if (str(result.get("world", "")).casefold() != account.world.casefold()
                or str(result.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid island scope")
        try:
            rows = validate_island_destinations(x, y, result)
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid island inventory") from exc
        return {"account_id": account.id, "x": x, "y": y, "cities": rows}

    def buildings(self, account: Account, city_id: int) -> list[dict[str, object]]:
        """Return sanitized existing-session building slots from an owned city."""
        if type(city_id) is not int or city_id <= 0:
            raise ValueError("Invalid city ID")
        # Independent membership check at both the controller and IkaBot IPC.
        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("City does not belong to this account")
        response = self.request("list_buildings_existing", account=account, city_id=city_id)
        if (str(response.get("world", "")).casefold() != account.world.casefold()
                or str(response.get("username", "")).casefold() != account.player.casefold()
                or response.get("city_id") != city_id):
            raise EngineIPCUnavailable("IkaBot IPC returned another account's building data")
        rows = response.get("buildings")
        if not isinstance(rows, list) or len(rows) > 80:
            raise EngineIPCUnavailable("IkaBot IPC returned invalid buildings")
        validated = []
        positions: set[int] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise EngineIPCUnavailable("Malformed building row")
            slot, level = row.get("position"), row.get("level")
            name, building = row.get("name"), row.get("building")
            if (type(slot) is not int or not 0 <= slot <= 80 or slot in positions
                    or type(level) is not int or not 0 <= level <= 150
                    or not isinstance(name, str) or not 0 < len(name) <= 100
                    or not isinstance(building, str) or not 0 < len(building) <= 64
                    or type(row.get("busy")) is not bool
                    or type(row.get("can_upgrade")) is not bool
                    or (row.get("can_upgrade_now") is not None
                        and type(row["can_upgrade_now"]) is not bool)):
                raise EngineIPCUnavailable("IkaBot IPC returned invalid building data")
            positions.add(slot)
            validated.append({
                "position": slot, "level": level, "name": name,
                "building": building, "busy": row["busy"],
                "can_upgrade": row["can_upgrade"],
                "can_upgrade_now": row.get("can_upgrade_now", row["can_upgrade"]),
            })
        return validated

    def vacation_preview(self, account: Account, city_id: int) -> dict[str, object]:
        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("Choose an owned city")
        data = self.request("preview_vacation_existing", account=account, city_id=city_id)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid vacation preview scope")
        try:
            return {"account_id": account.id, **validate_vacation_plan(city_id, data.get("plan"))}
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid vacation preview") from exc

    def attack_inventory(self, account: Account, city_id: int) -> dict[str, object]:
        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("Choose an owned city")
        data = self.request("list_attack_units_existing", account=account, city_id=city_id)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid attack inventory scope")
        try:
            return {"account_id": account.id, **validate_attack_inventory(city_id, data.get("inventory"))}
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid attack inventory") from exc

    def attack_preview(self, account: Account, city_id: int, draft: dict[str, object]) -> dict[str, object]:
        clean = validated_attack_draft(city_id, draft)
        owned = {row["id"] for row in self.cities(account)}
        if city_id not in owned or clean["target_city_id"] not in owned:
            raise ValueError("Both cities must belong to this account")
        data = self.request("preview_attack_existing", account=account, city_id=city_id, attack_draft=clean)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid manual attack scope")
        try:
            return {"account_id": account.id, **validate_attack_plan(city_id, clean, data.get("plan"))}
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid manual attack plan") from exc

    def grind_preview(self, account: Account, city_id: int, draft: dict[str, object]) -> dict[str, object]:
        clean = validated_grind_draft(city_id, draft)
        owned = {row["id"] for row in self.cities(account)}
        if city_id not in owned or clean["target_city_id"] not in owned:
            raise ValueError("Both cities must belong to this account")
        data = self.request("preview_grind_existing", account=account, city_id=city_id, grind_draft=clean)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid automatic attack preview scope")
        try:
            return {"account_id": account.id, **validate_grind_plan(city_id, clean, data.get("plan"))}
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid automatic attack plan") from exc

    def station_preview(self, account: Account, city_id: int, draft: dict[str, object]) -> dict[str, object]:
        clean = validated_station_draft(city_id, draft)
        owned = {row["id"] for row in self.cities(account)}
        if city_id not in owned or clean["destination_city_id"] not in owned:
            raise ValueError("Both cities must belong to this account")
        data = self.request("preview_station_existing", account=account, city_id=city_id, station_draft=clean)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid deployment preview scope")
        try:
            plan = validate_station_plan(city_id, clean, data.get("plan"))
            if clean.get("all_origins") and {r["city_id"] for r in plan["deployments"]} != owned - {clean["destination_city_id"]}:
                raise ValueError("Owned city inventory changed")
            return {"account_id": account.id, **plan}
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid deployment plan") from exc

    def build_options(self, account: Account, city_id: int) -> dict[str, object]:
        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("Choose an owned city")
        data = self.request("list_build_options_existing", account=account, city_id=city_id)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid building inventory scope")
        try:
            return {"account_id": account.id, **validate_build_inventory(city_id, data.get("inventory"))}
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid building inventory") from exc

    def build_preview(self, account: Account, city_id: int, draft: dict[str, int]) -> dict[str, object]:
        clean = validated_build_draft(draft)
        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("Choose an owned city")
        data = self.request("preview_build_existing", account=account, city_id=city_id, build_draft=clean)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid building preview scope")
        try:
            return {"account_id": account.id, **validate_build_plan(city_id, clean, data.get("plan"))}
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid building plan") from exc

    def layout_preview(self, account: Account, city_id: int, template_city_id: int) -> dict[str, object]:
        template = validated_layout_draft(city_id, {"template_city_id": template_city_id})
        owned = {row["id"] for row in self.cities(account)}
        if city_id not in owned or template not in owned:
            raise ValueError("Both cities must belong to this account")
        data = self.request("preview_layout_existing", account=account,
                            city_id=city_id, template_city_id=template)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid layout preview scope")
        try:
            plan = validate_layout_plan(city_id, template, data.get("plan"))
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid layout preview") from exc
        return {"account_id": account.id, **plan}

    def production_inventory(self, account: Account, city_id: int) -> dict[str, object]:
        from daedalus.production_inventory import validate_production_inventory

        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("Production city is not owned by this account")
        data = self.request("production_inventory_existing", account=account, city_id=city_id)
        if not _is_exact_identity({"world": data.get("world"), "player": data.get("username")}, account):
            raise EngineIPCUnavailable("Invalid production inventory scope")
        try:
            return validate_production_inventory(city_id, data.get("inventory"))
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid production inventory") from exc

    def worker_preview(self, account: Account, city_id: int, task: str,
                       draft: dict[str, object]) -> dict[str, object]:
        clean = validated_worker_draft(task, draft)
        owned = {row["id"] for row in self.cities(account)}
        if "priority" in clean:
            from daedalus.production_inventory import (
                validate_priority_draft,
                validate_priority_plan,
            )

            rows = validate_priority_draft(city_id, clean["priority"])
            if not {row["city_id"] for row in rows} <= owned:
                raise ValueError("Production city is not owned by this account")
            data = self.request("preview_workers_existing", account=account,
                                city_id=city_id, worker_task=task, worker_draft=clean)
            if not _is_exact_identity({"world": data.get("world"), "player": data.get("username")}, account):
                raise EngineIPCUnavailable("Invalid production preview scope")
            plans = data.get("plans")
            try:
                if not isinstance(plans, list) or len(plans) != len(rows):
                    raise ValueError("Invalid production preview")
                validated = [validate_priority_plan(row["city_id"], row["draft"], plan)
                             for row, plan in zip(rows, plans)]
            except ValueError as exc:
                raise EngineIPCUnavailable("Invalid production preview") from exc
            return {"account_id": account.id, "task": task, "city_id": city_id,
                    "plans": validated, "ready": True, "config": {"production_plans": validated}}
        additional = clean.get("additional_city_ids", [])
        if city_id not in owned or city_id in additional or not set(additional) <= owned:
            raise ValueError("Worker city is not owned by this account")
        data = self.request("preview_workers_existing", account=account,
                            city_id=city_id, worker_task=task, worker_draft=clean)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid worker preview scope")
        try:
            plan = validate_worker_plan(task, city_id, clean, data.get("plan"))
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid worker preview") from exc
        return {"account_id": account.id, **plan}

    def donation_preview(self, account: Account, city_id: int,
                         project: str, amount: int) -> dict[str, object]:
        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("Donation city is not owned by this account")
        data = self.request("preview_donation_existing", account=account,
                            city_id=city_id, project=project, amount=amount)
        plan = data.get("plan")
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()
                or not isinstance(plan, dict)
                or plan.get("city_id") != city_id or plan.get("project") != project
                or plan.get("amount") != amount):
            raise EngineIPCUnavailable("Invalid donation preview scope")
        for key in ("city_name", "project_name"):
            if not isinstance(plan.get(key), str) or not 0 < len(plan[key]) <= 100:
                raise EngineIPCUnavailable("Invalid donation name")
        for key in ("stock", "required", "donated", "remaining", "level"):
            if type(plan.get(key)) is not int or not 0 <= plan[key] <= 10**15:
                raise EngineIPCUnavailable("Invalid donation observation")
        if (type(plan.get("upgrading")) is not bool or type(plan.get("ready")) is not bool
                or plan["remaining"] != plan["required"] - plan["donated"]
                or plan["ready"] != (not plan["upgrading"]
                                     and amount <= min(plan["stock"], plan["remaining"]))):
            raise EngineIPCUnavailable("Invalid donation eligibility")
        config = plan.get("config")
        if (not isinstance(config, dict)
                or set(config) != {"city_id", "project", "amount", "expected_island",
                                   "expected_level", "expected_donated", "expected_required"}
                or type(config.get("expected_island")) is not int
                or not 0 < config["expected_island"] < 10**12
                or config != {"city_id": city_id, "project": project, "amount": amount,
                              "expected_island": config["expected_island"],
                              "expected_level": plan["level"],
                              "expected_donated": plan["donated"],
                              "expected_required": plan["required"]}):
            raise EngineIPCUnavailable("Invalid reviewed donation config")
        return {"account_id": account.id, **{k: plan[k] for k in (
            "city_id", "city_name", "project", "project_name", "amount", "stock",
            "required", "donated", "remaining", "level", "upgrading", "ready", "config",
        )}}

    def construction_preview(
        self, account: Account, city_id: int, upgrades: list[dict[str, int]],
        *, supply: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """One strictly read-only engine calculation, bound to an owned city."""
        if type(city_id) is not int or city_id <= 0:
            raise ValueError("Invalid preview city")
        from daedalus.reviewed_operations import (
            validate_construction_supply,
            validated_construction_supply,
        )

        owned = {row["id"] for row in self.cities(account)}
        if city_id not in owned:
            raise ValueError("Construction city is not owned by this account")
        if supply is not None:
            supply = validated_construction_supply(city_id, supply)
            if not set(supply["source_ids"]) <= owned:
                raise ValueError("Construction supplier is not owned")
        data = self.request(
            "preview_construction_existing", account=account, city_id=city_id,
            upgrades=upgrades, construction_supply=supply,
        )
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()
                or data.get("city_id") != city_id):
            raise EngineIPCUnavailable("IkaBot preview belongs to a different game account")
        plan = data.get("plan")
        if not isinstance(plan, dict) or type(plan.get("ready")) is not bool:
            raise EngineIPCUnavailable("Invalid IkaBot construction preview")
        numbers = {}
        for name in ("costs", "available", "missing"):
            values = plan.get(name)
            if (not isinstance(values, list) or len(values) != 5
                    or any(type(v) is not int or v < 0 or v > 10**15
                           for v in values)):
                raise EngineIPCUnavailable("IkaBot returned invalid resource amounts")
            numbers[name] = values
        config = plan.get("config")
        expected_keys = {
            "city_id", "city_name", "buildings", "shipments", "expand_overall",
            "wait_resources", "construction_queue", "total_time",
        }
        if supply is not None:
            expected_keys.add("supply_review")
        if (not isinstance(config, dict) or set(config) != expected_keys
                or config.get("city_id") != city_id
                or not isinstance(config.get("city_name"), str)
                or not 0 < len(config["city_name"]) <= 100
                or (supply is None and (config.get("shipments") != []
                    or config.get("expand_overall") is not True or config.get("wait_resources") is not False))
                or not isinstance(config.get("buildings"), list)
                or not 0 < len(config["buildings"]) <= 12
                or not isinstance(config.get("construction_queue"), list)
                or any(type(v) is not int or v <= 0
                       for v in config["construction_queue"])
                or type(config.get("total_time")) is not int
                or config["total_time"] < 0):
            raise EngineIPCUnavailable("IkaBot returned an invalid prepared plan")
        extra = {}
        if supply is not None:
            try:
                extra["supply"] = validate_construction_supply(city_id, supply, numbers, plan, config)
            except (ValueError, KeyError, TypeError) as exc:
                raise EngineIPCUnavailable("Invalid construction supply preview") from exc
        elif "supply" in plan:
            raise EngineIPCUnavailable("Unexpected construction supply preview")
        allowed_building_keys = {
            "position", "name", "building", "level", "isBusy", "upgradeTo",
            "constructionTime", "constructionTimes",
        }
        for row in config["buildings"]:
            if (not isinstance(row, dict) or set(row) != allowed_building_keys
                    or type(row.get("position")) is not int or not 0 <= row["position"] <= 80
                    or type(row.get("level")) is not int or not 0 <= row["level"] <= 150
                    or type(row.get("upgradeTo")) is not int
                    or not row["level"] < row["upgradeTo"] <= 150
                    or row.get("isBusy") is not False
                    or not isinstance(row.get("name"), str)
                    or not 0 < len(row["name"]) <= 100
                    or not isinstance(row.get("building"), str)
                    or not 0 < len(row["building"]) <= 64
                    or type(row.get("constructionTime")) is not int
                    or not isinstance(row.get("constructionTimes"), list)):
                raise EngineIPCUnavailable("IkaBot returned an invalid building plan")
        try:
            size = len(json.dumps(config, allow_nan=False).encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise EngineIPCUnavailable("IkaBot returned an invalid preview payload") from exc
        if size > 16000:
            raise EngineIPCUnavailable("IkaBot construction plan exceeds safe size")
        seconds = plan.get("estimated_seconds")
        if type(seconds) is not int or seconds < 0:
            raise EngineIPCUnavailable("IkaBot returned an invalid construction time")
        return {
            "account_id": account.id, "city_id": city_id, "ready": plan["ready"],
            "config": config, "estimated_seconds": seconds, **numbers, **extra,
        }

    def workshop_upgrades(self, account: Account, city_id: int) -> dict[str, object]:
        """Return verified current account workshop levels and upgrade choices."""
        if type(city_id) is not int or not 0 < city_id < 10**12:
            raise ValueError("Invalid workshop city")
        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("Workshop city not owned by account")
        data = self.request(
            "list_workshop_upgrades_existing", account=account, city_id=city_id,
        )
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()
                or data.get("city_id") != city_id):
            raise EngineIPCUnavailable("IkaBot returned another account's workshop")
        level = data.get("workshop_level")
        choices = data.get("upgrades")
        if (type(level) is not int or not 0 <= level <= 25
                or not isinstance(choices, list) or len(choices) > 250):
            raise EngineIPCUnavailable("Invalid IkaBot workshop inventory")
        result = []
        seen = set()
        for item in choices:
            if not isinstance(item, dict):
                raise EngineIPCUnavailable("Invalid workshop upgrade")
            uid, name, upgrade_type = (
                item.get("unit_id"), item.get("name"), item.get("upgrade_type")
            )
            current, maximum = item.get("current_level"), item.get("max_level")
            description = item.get("description")
            if (not isinstance(uid, str) or not uid.isdecimal()
                    or not 0 < len(uid) <= 16
                    or not isinstance(name, str) or not 0 < len(name) <= 100
                    or not isinstance(upgrade_type, str)
                    or not re.fullmatch(r"[a-zA-Z_]{1,40}", upgrade_type)
                    or not isinstance(description, str) or len(description) > 100
                    or type(current) is not int or not 0 <= current <= 25
                    or type(maximum) is not int or maximum != level
                    or (uid, upgrade_type) in seen):
                raise EngineIPCUnavailable("Malformed workshop upgrade data")
            seen.add((uid, upgrade_type))
            result.append({
                "unit_id": uid, "name": name, "upgrade_type": upgrade_type,
                "description": description, "current_level": current,
                "max_level": maximum,
            })
        return {
            "account_id": account.id, "city_id": city_id,
            "workshop_level": level, "upgrades": result,
        }

    def trainable_units(
        self, account: Account, city_id: int, *, train_troops: bool,
    ) -> dict[str, object]:
        """Bounded, account-owned barracks/shipyard unit options and current costs."""
        if type(city_id) is not int or not 0 < city_id < 10**12 or type(train_troops) is not bool:
            raise ValueError("Invalid training selection")
        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("Training city not owned by account")
        data = self.request(
            "list_trainables_existing", account=account, city_id=city_id,
            train_troops=train_troops,
        )
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()
                or data.get("city_id") != city_id or data.get("train_troops") is not train_troops):
            raise EngineIPCUnavailable("IkaBot training options belong to another account")
        city = data.get("city")
        units = data.get("units")
        resources = data.get("available")
        citizens = data.get("free_citizens")
        if (not isinstance(city, dict) or not isinstance(units, list)
                or not 0 < len(units) <= 100
                or not isinstance(resources, list) or len(resources) != 5
                or any(type(value) is not int or not 0 <= value <= 10**15 for value in resources)
                or type(citizens) is not int or not 0 <= citizens <= 10**15):
            raise EngineIPCUnavailable("Invalid IkaBot training inventory")
        if (city.get("id") != str(city_id)
                or not isinstance(city.get("cityName"), str)
                or not 0 < len(city["cityName"]) <= 100
                or not isinstance(city.get("pos"), str)
                or not city["pos"].isdigit()):
            raise EngineIPCUnavailable("IkaBot training city did not match")
        allowed_costs = {
            "wood", "wine", "marble", "crystal", "sulfur",
            "citizens", "upkeep", "completiontime",
        }
        verified = []
        ids = set()
        for unit in units:
            if not isinstance(unit, dict):
                raise EngineIPCUnavailable("Invalid trainable unit")
            uid, name, costs = (
                unit.get("unit_type_id"), unit.get("local_name"), unit.get("costs")
            )
            if (type(uid) is not int or not 0 < uid < 10**7 or uid in ids
                    or not isinstance(name, str) or not 0 < len(name) <= 100
                    or not isinstance(costs, dict) or not set(costs).issubset(allowed_costs)):
                raise EngineIPCUnavailable("Malformed trainable unit data")
            for value in costs.values():
                if (type(value) not in (int, float)
                        or not math.isfinite(value) or not 0 <= value <= 10**9):
                    raise EngineIPCUnavailable("Invalid recruitable unit costs")
            ids.add(uid)
            verified.append({
                "unit_type_id": uid, "local_name": name, "costs": dict(costs),
            })
        return {
            "account_id": account.id, "city_id": city_id,
            "train_troops": train_troops,
            "city": city, "units": verified,
            "available": list(resources), "free_citizens": citizens,
        }

    def market_quotes(
        self, account: Account, city_id: int, resource_type: int, side: str,
    ) -> dict[str, object]:
        """Read strict, owned-city actual market quotes without game mutation."""
        if (type(city_id) is not int or not 0 < city_id < 10**12
                or type(resource_type) is not int or not 0 <= resource_type <= 4
                or side not in {"buy", "sell_to_offers", "create_offer"}):
            raise ValueError("Invalid market selection")
        if city_id not in {row["id"] for row in self.cities(account)}:
            raise ValueError("Market city is not owned by account")
        data = self.request(
            "market_quotes_existing", account=account, city_id=city_id,
            resource_type=resource_type, market_side=side,
        )
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()
                or data.get("city_id") != city_id
                or data.get("resource_type") != resource_type
                or data.get("side") != side):
            raise EngineIPCUnavailable("IkaBot market quotes belong to another account")
        city = data.get("city")
        offers = data.get("offers")
        if (not isinstance(city, dict) or not isinstance(offers, list)
                or len(offers) > 200 or city.get("id") != str(city_id)
                or not isinstance(city.get("name"), str)
                or not 0 < len(city["name"]) <= 100
                or not isinstance(city.get("cityName"), str)
                or not 0 < len(city["cityName"]) <= 100
                or type(city.get("pos")) is not int
                or not 0 <= city["pos"] <= 80
                or type(city.get("rango")) is not int
                or not 0 < city["rango"] <= 100
                or not isinstance(city.get("availableResources"), list)
                or len(city["availableResources"]) != 5
                or any(type(v) is not int or v < 0
                       for v in city["availableResources"])):
            raise EngineIPCUnavailable("Invalid IkaBot market snapshot")
        if side == "buy":
            keys = {
                "ciudadDestino", "jugadorAComprar", "amountAvailable",
                "tipo", "precio", "destinationCityId", "cityId", "position",
                "type", "resource",
            }
            for offer in offers:
                if (not isinstance(offer, dict) or set(offer) != keys
                        or any(not isinstance(offer.get(key), str)
                               or not 0 < len(offer[key]) <= 100
                               for key in ("ciudadDestino", "jugadorAComprar", "tipo"))
                        or any(not isinstance(offer.get(key), str)
                               or not offer[key].isdigit()
                               for key in ("destinationCityId", "cityId", "position", "type"))
                        or type(offer.get("amountAvailable")) is not int
                        or not 0 < offer["amountAvailable"] <= 10**12
                        or type(offer.get("precio")) is not int
                        or not 0 < offer["precio"] <= 10**9
                        or not isinstance(offer.get("resource"), str)
                        or offer["resource"] != ("resource" if resource_type == 0
                                                else str(resource_type))):
                    raise EngineIPCUnavailable("IkaBot returned invalid buying quote")
        elif side == "sell_to_offers":
            for offer in offers:
                if (not isinstance(offer, list) or len(offer) != 6
                        or any(not isinstance(value, str) or not 0 < len(value) <= 100
                               for value in offer[:2])
                        or any(type(value) is not int or value < 0 or value > 10**12
                               for value in offer[2:])
                        or offer[2] == 0 or offer[3] == 0 or offer[5] == 0):
                    raise EngineIPCUnavailable("IkaBot returned invalid selling quote")
        else:
            for key in ("price_min", "price_max", "sell_market_capacity", "currently_on_sale"):
                if type(data.get(key)) is not int or data[key] < 0:
                    raise EngineIPCUnavailable("IkaBot returned invalid market listing limits")
            if data["price_min"] > data["price_max"]:
                raise EngineIPCUnavailable("Inconsistent market pricing limits")
            if offers:
                raise EngineIPCUnavailable("Listing mode cannot return external quotes")
        return {
            "account_id": account.id, "city_id": city_id,
            "resource_type": resource_type, "side": side,
            "city": city, "offers": offers,
            "price_min": data.get("price_min"),
            "price_max": data.get("price_max"),
            "sell_market_capacity": data.get("sell_market_capacity"),
            "currently_on_sale": data.get("currently_on_sale"),
        }

    def academies(self, account: Account) -> dict[str, object]:
        """Bounded academy inventory, with authoritative crystal/cooldown status."""
        data = self.request("list_academies_existing", account=account)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("IkaBot academy list belongs to another account")
        records = data.get("academies")
        if not isinstance(records, list) or len(records) > 100:
            raise EngineIPCUnavailable("IkaBot returned invalid academy list")
        owned = {city["id"] for city in self.cities(account)}
        seen = set()
        result = []
        for record in records:
            if not isinstance(record, dict):
                raise EngineIPCUnavailable("Invalid academy record")
            ident = record.get("city_id")
            name = record.get("city_name")
            position = record.get("position")
            crystal = record.get("crystal")
            cooldown = record.get("cooldown")
            ready = record.get("can_experiment_now")
            if (type(ident) is not int or ident not in owned or ident in seen
                    or not isinstance(name, str) or not 0 < len(name) <= 100
                    or type(position) is not int or not 0 <= position <= 80
                    or type(crystal) is not int or not 0 <= crystal <= 10**15
                    or type(cooldown) is not bool or type(ready) is not bool
                    or (ready and (cooldown or crystal < 300000))):
                raise EngineIPCUnavailable("Invalid or foreign academy entry")
            seen.add(ident)
            result.append({
                "city_id": ident, "city_name": name, "position": position,
                "crystal": crystal, "cooldown": cooldown, "can_experiment_now": ready,
            })
        response = {"account_id": account.id, "academies": result}
        if "studies" in data:
            from daedalus.research_choices import validate_studies

            try:
                response["studies"] = validate_studies(data["studies"])
            except ValueError as exc:
                raise EngineIPCUnavailable("Invalid research advisor inventory") from exc
        return response

    def taverns(self, account: Account) -> dict[str, object]:
        """Account-local wine, servings and satisfaction observations."""
        data = self.request("list_taverns_existing", account=account)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("IkaBot tavern inventory belongs to another account")
        records = data.get("taverns")
        if not isinstance(records, list) or len(records) > 100:
            raise EngineIPCUnavailable("Invalid IkaBot tavern inventory")
        owned = {row["id"] for row in self.cities(account)}
        seen = set()
        result = []
        for record in records:
            if not isinstance(record, dict):
                raise EngineIPCUnavailable("Malformed tavern record")
            city_id = record.get("city_id")
            name = record.get("city_name")
            wine = record.get("wine")
            has_tavern = record.get("has_tavern")
            servings = record.get("serving_level")
            consumption = record.get("wine_per_hour")
            satisfaction = record.get("satisfaction")
            population = record.get("population")
            capacity = record.get("capacity")
            if (type(city_id) is not int or city_id not in owned or city_id in seen
                    or not isinstance(name, str) or not 0 < len(name) <= 100
                    or type(wine) is not int or not 0 <= wine <= 10**15
                    or type(has_tavern) is not bool
                    or (servings is not None and (type(servings) is not int
                                                  or not 0 <= servings <= 100))
                    or (consumption is not None and (type(consumption) is not int
                                                    or not 0 <= consumption <= 10**9))
                    or (satisfaction is not None and (type(satisfaction) is not int
                                                     or not -10**9 <= satisfaction <= 10**9))
                    or (population is not None and (type(population) is not int
                                                   or not 0 <= population <= 10**9))
                    or (capacity is not None and (type(capacity) is not int
                                                 or not 0 <= capacity <= 10**9))):
                raise EngineIPCUnavailable("Invalid tavern state from game")
            seen.add(city_id)
            result.append({
                "city_id": city_id, "city_name": name,
                "wine": wine, "has_tavern": has_tavern,
                "serving_level": servings, "wine_per_hour": consumption,
                "satisfaction": satisfaction,
                "population": population, "capacity": capacity,
            })
            if "serving_options" in record:
                from daedalus.tavern_choices import validate_serving_options

                try:
                    result[-1]["serving_options"] = validate_serving_options(
                        record["serving_options"], servings, consumption)
                except ValueError as exc:
                    raise EngineIPCUnavailable("Invalid tavern serving choices") from exc
        return {"account_id": account.id, "taverns": result}

    def miracles(self, account: Account) -> dict[str, object]:
        """Verified own temples and current wonder cooldown/readiness."""
        data = self.request("list_miracles_existing", account=account)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("IkaBot wonders belong to another account")
        raw = data.get("miracles")
        if not isinstance(raw, list) or len(raw) > 100:
            raise EngineIPCUnavailable("Invalid IkaBot wonders list")
        owned = {row["id"] for row in self.cities(account)}
        seen = set()
        result = []
        for item in raw:
            if not isinstance(item, dict):
                raise EngineIPCUnavailable("Invalid wonder record")
            city_id = item.get("city_id")
            temple_city = item.get("temple_city")
            island_id = item.get("island_id")
            wonder = item.get("wonder")
            wonder_name = item.get("wonder_name")
            level = item.get("level")
            enabled = item.get("available")
            seconds = item.get("available_in_seconds")
            if (type(city_id) is not int or city_id not in owned
                    or not isinstance(temple_city, str)
                    or not 0 < len(temple_city) <= 100
                    or not isinstance(island_id, str)
                    or not island_id.isdecimal() or not 0 < len(island_id) <= 30
                    or not isinstance(wonder, str)
                    or wonder not in set("12345678") or wonder in seen
                    or not isinstance(wonder_name, str)
                    or not 0 < len(wonder_name) <= 100
                    or type(level) is not int or not 0 <= level <= 5
                    or type(enabled) is not bool
                    or type(seconds) is not int or not 0 <= seconds <= 7 * 86400):
                raise EngineIPCUnavailable("Malformed owned wonder information")
            seen.add(wonder)
            result.append({
                "city_id": city_id, "temple_city": temple_city,
                "island_id": island_id, "wonder": wonder,
                "wonder_name": wonder_name, "level": level,
                "available": enabled, "available_in_seconds": seconds,
            })
        return {"account_id": account.id, "miracles": result}

    def notification_settings_begin(self, account: Account, provider: str) -> dict[str, object]:
        from daedalus.notification_settings import PROVIDERS, validate_challenge

        if not account.enabled or provider not in PROVIDERS:
            raise ValueError("Invalid provider scope")
        reply = self._exchange({"action": "notification_settings_begin_existing", "world": account.world,
                                "player": account.player, "account_id": account.id, "provider": provider,
                                "confirmed_global": True})
        if (str(reply.get("world", "")).casefold() != account.world.casefold()
                or str(reply.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid provider scope")
        try:
            return validate_challenge(reply.get("result"), account.id, provider)
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid provider configuration challenge") from exc

    def notification_settings_complete(self, account: Account, provider: str,
                                       envelope: dict[str, object]) -> dict[str, object]:
        from daedalus.notification_settings import PROVIDERS, validate_envelope, validate_receipt

        if not account.enabled or provider not in PROVIDERS:
            raise ValueError("Invalid provider scope")
        reply = self._exchange({"action": "notification_settings_complete_existing", "world": account.world,
                                "player": account.player, "account_id": account.id, "provider": provider,
                                "envelope": validate_envelope(envelope)}, read_timeout=30.0)
        if (str(reply.get("world", "")).casefold() != account.world.casefold()
                or str(reply.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Invalid provider scope")
        try:
            return validate_receipt(reply.get("result"), account.id, provider)
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid provider configuration receipt") from exc

    def proxy_profiles(self, account: Account, draft=None):
        from daedalus.proxy_profiles import validate_proxy_draft, validate_proxy_result

        if not account.enabled:
            raise ValueError("Account disabled")
        payload = {"action": "proxy_profiles_existing", "world": account.world, "player": account.player}
        if draft is not None:
            payload.update(action="configure_proxy_profile_existing", draft=validate_proxy_draft(draft))
        reply = self._exchange(payload, read_timeout=20.0)
        if (str(reply.get("world", "")).casefold() != account.world.casefold()
                or str(reply.get("username", "")).casefold() != account.player.casefold()
                or not isinstance(reply.get("result"), dict)):
            raise EngineIPCUnavailable("Invalid network profile scope")
        try:
            return validate_proxy_result({**reply["result"], "account_id": account.id}, account.id, draft)
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid network profile result") from exc

    def challenge_policy(self, account: Account, draft=None) -> dict[str, object]:
        from daedalus.challenge_policy import (
            validate_challenge_policy,
            validate_challenge_policy_draft,
        )

        if not account.enabled:
            raise ValueError("Account disabled")
        payload = {"action": "challenge_policy_existing", "world": account.world, "player": account.player}
        if draft is not None:
            payload.update(action="set_challenge_policy_existing", draft=validate_challenge_policy_draft(draft))
        reply = self._exchange(payload)
        if (str(reply.get("world", "")).casefold() != account.world.casefold()
                or str(reply.get("username", "")).casefold() != account.player.casefold()
                or not isinstance(reply.get("result"), dict)):
            raise EngineIPCUnavailable("Invalid human challenge policy scope")
        try:
            value = validate_challenge_policy({**reply["result"], "account_id": account.id}, account.id)
            if draft is not None and value["mode"] != draft["mode"]:
                raise ValueError("Human challenge policy result unconfirmed")
            return value
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid human challenge policy") from exc

    def extension_settings(self, account: Account, draft=None) -> dict[str, object]:
        from daedalus.extension_settings import validate_extension_draft, validate_extension_status

        if not account.enabled:
            raise ValueError("Account disabled")
        payload = {"action": "extension_status_existing", "world": account.world, "player": account.player}
        if draft is not None:
            payload.update(action="extension_registration_existing", draft=validate_extension_draft(draft))
        reply = self._exchange(payload)
        if (str(reply.get("world", "")).casefold() != account.world.casefold()
                or str(reply.get("username", "")).casefold() != account.player.casefold()
                or not isinstance(reply.get("result"), dict)):
            raise EngineIPCUnavailable("Invalid extension scope")
        try:
            result = validate_extension_status({**reply["result"], "account_id": account.id}, account.id)
            if draft is not None and not any(r["id"] == draft["id"] and r["sha256"] == draft["sha256"]
                    and r["registered"] is draft["registered"] for r in result["extensions"]):
                raise ValueError("Registration result unconfirmed")
            return result
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid extension status") from exc

    def world_reports(self, account: Account, report_id=None, offset=0) -> dict[str, object]:
        from daedalus.world_reports import REPORT_ID, validate_world_page, validate_world_reports

        if not account.enabled or (report_id is not None and (
                not isinstance(report_id, str) or not REPORT_ID.fullmatch(report_id)
                or type(offset) is not int or not 0 <= offset <= 10201)):
            raise ValueError("Invalid map report scope")
        payload = {"action": "world_reports_existing", "world": account.world, "player": account.player}
        if report_id is not None:
            payload.update(action="world_report_page_existing", report_id=report_id, offset=offset)
        reply = self._exchange(payload)
        if (str(reply.get("world", "")).casefold() != account.world.casefold()
                or str(reply.get("username", "")).casefold() != account.player.casefold()
                or not isinstance(reply.get("result"), dict)):
            raise EngineIPCUnavailable("Invalid map report scope")
        value = {**reply["result"], "account_id": account.id}
        try:
            return (validate_world_reports(value, account.id) if report_id is None else
                    validate_world_page(value, account.id, report_id, offset))
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid aggregate map report") from exc

    def administrative_status(self, account: Account) -> dict[str, object]:
        from daedalus.admin_status import scoped_admin_status

        data = self.request("administrative_status_existing", account=account)
        try:
            return scoped_admin_status(account, data)
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid account-scoped administrative status") from exc

    def shrine_status(self, account: Account) -> dict[str, object]:
        """Verified account-local Shrine of Olympus, never a guessed favour balance."""
        data = self.request("shrine_status_existing", account=account)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Shrine status belongs to another game account")
        shrine = data.get("shrine")
        if shrine is not None:
            if not isinstance(shrine, dict):
                raise EngineIPCUnavailable("Malformed IkaBot shrine status")
            city_id = shrine.get("city_id")
            name = shrine.get("city_name")
            position = shrine.get("position")
            favor = shrine.get("favor")
            if (type(city_id) is not int
                    or city_id not in {city["id"] for city in self.cities(account)}
                    or not isinstance(name, str) or not 0 < len(name) <= 100
                    or type(position) is not int or not 0 <= position <= 80
                    or (favor is not None and (
                        type(favor) is not int or not 0 <= favor <= 10**12
                    ))):
                raise EngineIPCUnavailable("Invalid or foreign Shrine of Olympus")
            shrine = {"city_id": city_id, "city_name": name,
                      "position": position, "favor": favor}
        return {"account_id": account.id, "shrine": shrine}

    def pirate_fortresses(self, account: Account) -> dict[str, object]:
        """Bounded, account-owned fortress inventory and actual mission eligibility."""
        data = self.request("list_pirate_fortresses_existing", account=account)
        if (str(data.get("world", "")).casefold() != account.world.casefold()
                or str(data.get("username", "")).casefold() != account.player.casefold()):
            raise EngineIPCUnavailable("Pirate fortresses belong to another account")
        records = data.get("fortresses")
        if not isinstance(records, list) or len(records) > 100:
            raise EngineIPCUnavailable("Invalid pirate fortress inventory")
        owned = {city["id"] for city in self.cities(account)}
        seen = set()
        result = []
        for row in records:
            if not isinstance(row, dict):
                raise EngineIPCUnavailable("Malformed pirate fortress")
            city_id = row.get("city_id")
            level = row.get("fortress_level")
            missions = row.get("missions")
            name = row.get("city_name")
            if (type(city_id) is not int or city_id not in owned or city_id in seen
                    or type(level) is not int or not 1 <= level <= 100
                    or not isinstance(name, str) or not 0 < len(name) <= 100
                    or not isinstance(missions, list) or not 0 < len(missions) <= 9):
                raise EngineIPCUnavailable("Invalid pirate fortress city")
            seen.add(city_id)
            verified_missions = []
            mission_ids = set()
            for mission in missions:
                if not isinstance(mission, dict):
                    raise EngineIPCUnavailable("Malformed pirate mission")
                number = mission.get("number")
                duration = mission.get("duration_seconds")
                if (type(number) is not int or not 1 <= number <= 9
                        or number in mission_ids
                        or type(duration) is not int or not 0 < duration <= 86400
                        or level < 2 * number - 1):
                    raise EngineIPCUnavailable("Pirate mission not supported by fortress level")
                mission_ids.add(number)
                verified_missions.append({"number": number, "duration_seconds": duration})
            result.append({
                "city_id": city_id, "city_name": name, "fortress_level": level,
                "missions": verified_missions,
            })
        return {"account_id": account.id, "fortresses": result}

    def military_overview(self, account: Account) -> dict[str, object]:
        """Bounded, source-backed troop and ship counts for this exact account."""
        if not self.has_account(account):
            raise EngineIPCUnavailable("No unique authenticated military session")
        data = self.request("military_overview_existing", account=account)
        if not _is_exact_identity({
            "world": data.get("world"), "player": data.get("username")
        }, account):
            raise EngineIPCUnavailable("Military inventory belongs to another account")
        rows = data.get("cities")
        observed = data.get("observed_at")
        if (not isinstance(rows, list) or len(rows) > 100
                or type(observed) is not int or observed <= 0):
            raise EngineIPCUnavailable("Invalid military inventory")
        owned = {city["id"] for city in self.cities(account)}
        output = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or type(row.get("city_id")) is not int:
                raise EngineIPCUnavailable("Invalid military city")
            cid = row["city_id"]
            if (cid not in owned or cid in seen or
                    not isinstance(row.get("city_name"), str) or
                    len(row["city_name"]) > 120):
                raise EngineIPCUnavailable("Military city is not verified")
            seen.add(cid)
            typed = {"city_id": cid, "city_name": row["city_name"]}
            for group in ("troops", "fleet"):
                units = row.get(group)
                if not isinstance(units, list) or len(units) > 100:
                    raise EngineIPCUnavailable("Invalid military unit list")
                clean = []
                for unit in units:
                    if (not isinstance(unit, dict)
                            or not isinstance(unit.get("unit"), str)
                            or not 0 < len(unit["unit"]) <= 100
                            or type(unit.get("amount")) is not int
                            or not 0 <= unit["amount"] <= 10**10):
                        raise EngineIPCUnavailable("Invalid military unit record")
                    clean.append({"unit": unit["unit"], "amount": unit["amount"]})
                typed[group] = clean
            output.append(typed)
        return {"cities": output, "observed_at": observed}

    def ship_movements(self, account: Account) -> dict[str, object]:
        """Read-only bounded movements, never a military dispatch."""
        if not self.has_account(account):
            raise EngineIPCUnavailable("No unique authenticated movement session")
        data = self.request("ship_movements_existing", account=account)
        if not _is_exact_identity({
            "world": data.get("world"), "player": data.get("username")
        }, account):
            raise EngineIPCUnavailable("Movements belong to another account")
        rows = data.get("movements")
        observed = data.get("observed_at")
        if (not isinstance(rows, list) or len(rows) > 250
                or type(observed) is not int or observed <= 0):
            raise EngineIPCUnavailable("Invalid movement inventory")
        cleaned = []
        for row in rows:
            if not isinstance(row, dict):
                raise EngineIPCUnavailable("Invalid movement record")
            clean = {}
            for field in ("origin", "destination", "origin_player",
                          "destination_player", "mission"):
                value = row.get(field)
                if not isinstance(value, str) or len(value) > 120:
                    raise EngineIPCUnavailable("Invalid movement text")
                clean[field] = value
            for field in ("seconds_remaining", "troops", "ships"):
                value = row.get(field)
                if type(value) is not int or not 0 <= value <= 10**10:
                    raise EngineIPCUnavailable("Invalid movement count")
                clean[field] = value
            for field in ("hostile", "returning"):
                if type(row.get(field)) is not bool:
                    raise EngineIPCUnavailable("Invalid movement flag")
                clean[field] = row[field]
            cleaned.append(clean)
        return {"movements": cleaned, "observed_at": observed}

    def warehouses(self, account: Account) -> list[CityWarehouseSnapshot]:
        """Convert numeric-only engine IPC snapshots into typed warehouse records."""
        if sum(_is_exact_identity(row, account) for row in self.list_sessions()) != 1:
            raise EngineIPCUnavailable("No unique already-authenticated account session")
        response = self.request("warehouse_snapshots_existing", account=account)
        if (
            not isinstance(response.get("world"), str)
            or not isinstance(response.get("username"), str)
            or response["world"].casefold() != account.world.casefold()
            or response["username"].casefold() != account.player.casefold()
        ):
            raise EngineIPCUnavailable("IkaBot IPC returned another account's data")
        rows = response.get("cities")
        if not isinstance(rows, list) or len(rows) > 100:
            raise EngineIPCUnavailable("Invalid warehouse snapshot collection")
        snapshots: list[CityWarehouseSnapshot] = []
        seen: set[int] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise EngineIPCUnavailable("Invalid warehouse snapshot")
            city_id, name = row.get("city_id"), row.get("city_name")
            if type(city_id) is not int or city_id <= 0 or city_id in seen:
                raise EngineIPCUnavailable("Invalid or duplicate warehouse city ID")
            if not isinstance(name, str) or not name or len(name) > 120:
                raise EngineIPCUnavailable("Invalid warehouse city name")
            seen.add(city_id)
            reported = row.get("unsecured")
            # Validate an explicit fixed set of resource names: never echo unknown markup.
            if not isinstance(reported, dict) or not reported or set(reported) - set(RESOURCES):
                raise EngineIPCUnavailable("Invalid unsecured resource fields")
            try:
                values = dict.fromkeys(RESOURCES)
                for resource, amount in reported.items():
                    if not isinstance(amount, str):
                        raise WarehouseParseError("Numeric warehouse amount required")
                    values[resource] = parse_amount(amount)
                capacity_str = row.get("capacity")
                if capacity_str is not None and not isinstance(capacity_str, str):
                    raise WarehouseParseError("Numeric capacity required")
                capacity = parse_amount(capacity_str) if capacity_str is not None else None
            except WarehouseParseError as exc:
                raise EngineIPCUnavailable("Invalid warehouse numeric value") from exc
            island = row.get("island")
            if island is not None and (
                not isinstance(island, str)
                or not re.fullmatch(r"[0-9]{1,3}:[0-9]{1,3}", island)
            ):
                raise EngineIPCUnavailable("Invalid island coordinates in warehouse snapshot")
            island_resource = row.get("island_resource")
            if island_resource is not None and (
                not isinstance(island_resource, str)
                or island_resource not in {"", "wood", "wine", "marble", "glass", "sulfur"}
            ):
                raise EngineIPCUnavailable("Invalid island resource in warehouse snapshot")
            snapshots.append(CityWarehouseSnapshot(
                account_id=account.id,
                city_id=city_id,
                city_name=name,
                captured_at=datetime.now(UTC).isoformat(),
                resources=WarehouseResources(unsecured=values, capacity=capacity),
                island=island,
                island_resource=island_resource or None,
            ))
        return snapshots


class ControlledIPCClient(ExistingIPCClient):
    """Opt-in task transport; never exposed through the parent read-only API."""

    @staticmethod
    def _identity(account: Account) -> dict[str, str]:
        if not account.enabled:
            raise ValueError("Account is disabled")
        return {"world": account.world, "player": account.player}

    def preflight_task(self, account: Account, task: str) -> dict[str, object]:
        """Nonmutating prerequisites with strict identity and typed reason codes."""
        if not isinstance(task, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", task):
            raise ValueError("Invalid task name")
        result = self._exchange({
            "action": "task_preflight_existing", **self._identity(account), "task": task,
        })
        if (
            str(result.get("world", "")).casefold() != account.world.casefold()
            or str(result.get("player", "")).casefold() != account.player.casefold()
            or str(result.get("task", "")).casefold() != task.casefold()
            or type(result.get("ready")) is not bool
            or type(result.get("notifications_required")) is not bool
            or result.get("reason") not in {"none", "notifications_required"}
            or not isinstance(result.get("checked"), list)
            or any(not isinstance(item, str) for item in result["checked"])
            or set(result["checked"]) - {"notifications"}
            or (not result["ready"]) != (result["reason"] == "notifications_required")
            or (result["reason"] == "notifications_required" and not result["notifications_required"])
        ):
            raise EngineIPCUnavailable("Invalid authenticated task preflight reply")
        return {"task": task, "ready": result["ready"],
                "reason": result["reason"],
                "notifications_required": result["notifications_required"],
                "checked": list(result["checked"])}

    def start_managed_task(
        self, account: Account, task: str, config: dict[str, object], request_id: str
    ) -> dict[str, object]:
        if not isinstance(task, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", task):
            raise ValueError("Invalid engine task name")
        if not isinstance(config, dict):
            raise TypeError("Task configuration must be a JSON object")
        if not isinstance(request_id, str) or not re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            request_id,
        ):
            raise ValueError("A valid UUID4 idempotency key is required")
        response = self._exchange(
            {"action": "start_task_existing", **self._identity(account),
             "task": task, "config": config, "request_id": request_id},
            read_timeout=120.0, allow_task_rejection=True,
        )
        task_id, pid = response.get("task_id"), response.get("pid")
        if (
            not isinstance(task_id, str)
            or not re.fullmatch(r"[0-9a-f]{24}", task_id)
            or type(pid) is not int or pid <= 0
            or str(response.get("world", "")).casefold() != account.world.casefold()
            or str(response.get("username", "")).casefold() != account.player.casefold()
        ):
            raise EngineIPCUnavailable("Engine task receipt is invalid")
        return {"task_id": task_id, "pid": pid, "task": task, "status": "running"}

    def list_managed_tasks(self, account: Account) -> list[dict[str, object]]:
        response = self._exchange({"action": "list_tasks_existing", **self._identity(account)})
        if (
            str(response.get("world", "")).casefold() != account.world.casefold()
            or str(response.get("player", "")).casefold() != account.player.casefold()
        ):
            raise EngineIPCUnavailable("Engine task list belongs to another account")
        rows = response.get("tasks")
        if not isinstance(rows, list) or len(rows) > 256:
            raise EngineIPCUnavailable("Invalid engine task list")
        cleaned = []
        for item in rows:
            if not isinstance(item, dict):
                raise EngineIPCUnavailable("Invalid engine task entry")
            task_id, task, status = item.get("task_id"), item.get("task"), item.get("status")
            if (
                not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-f]{24}", task_id)
                or not isinstance(task, str) or not isinstance(status, str)
                or status not in {"running", "finished", "stopping", "stopped"}
            ):
                raise EngineIPCUnavailable("Invalid engine task state")
            outcome = item.get("outcome")
            if outcome is not None and (status != "finished" or not (
                    (task in {"testTelegramBot", "testDiscordBot"}
                     and outcome in {"accepted", "failed_or_uncertain"})
                    or (task == "fillCityWarehouse" and outcome == "failed_or_uncertain"))):
                raise EngineIPCUnavailable("Invalid notification result")
            progress = item.get("progress")
            if progress is not None:
                from ikabot.helpers.fillProgress import STAGES
                if (task != "fillCityWarehouse" or not isinstance(progress, dict)
                        or set(progress) != {"stage", "submitted", "verified"}
                        or progress["stage"] not in STAGES
                        or any(type(progress[k]) is not int for k in ("submitted", "verified"))
                        or not 0 <= progress["verified"] <= progress["submitted"] <= 10**14):
                    raise EngineIPCUnavailable("Invalid warehouse progress")
            cleaned.append({"task_id": task_id, "task": task, "status": status,
                            **({"progress": progress} if progress is not None else {}),
                            "pid": item.get("pid"), "started_at": item.get("started_at"),
                            **({"outcome": outcome} if outcome is not None else {})})
        return cleaned

    def stop_managed_task(self, account: Account, task_id: str) -> dict[str, object]:
        if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-f]{24}", task_id):
            raise ValueError("Invalid managed task ID")
        response = self._exchange({"action": "stop_task_existing",
                                   **self._identity(account), "task_id": task_id},
                                  read_timeout=10.0)
        if response.get("task_id") != task_id or response.get("task_status") not in {
            "running", "stopping", "stopped", "finished"
        }:
            raise EngineIPCUnavailable("Invalid engine stop receipt")
        return {"task_id": task_id, "status": response["task_status"]}
