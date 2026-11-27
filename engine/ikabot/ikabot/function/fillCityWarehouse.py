"""Daedalus one-time owned-city fill, using IkaBot's existing transport sender."""
import re

from ikabot.config import materials_names_tec
from ikabot.helpers import pedirInfo
from ikabot.helpers.decorators import task
from ikabot.helpers.fillProgress import mark
from ikabot.helpers.fleetAdvisor import advisor_data as _advisor_data
from ikabot.helpers.naval import getAvailableFreighters, getAvailableShips, getTotalFreighters, getTotalShips
from ikabot.function import sendResources
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.taskConfig import getCityById, requireOwnCity
from ikabot.helpers.varios import decodeUnicodeEscape, wait

RESOURCES = ("wood", "wine", "marble", "crystal", "sulfur")
MAX_AMOUNT = 10**12


class FillPreviewError(ValueError):
    """Bounded reason code; never forward game HTML or exception details."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _free_space(v):
    # A legitimately overfilled warehouse can report negative remaining
    # space. Treat it as full, not an invalid or positive allocation.
    if type(v) is not int or not -MAX_AMOUNT <= v <= MAX_AMOUNT:
        raise ValueError("Invalid storage observation")
    return max(0, v)


def _amount(v):
    if type(v) is not int or not 0 <= v <= MAX_AMOUNT:
        raise ValueError("Invalid resource observation")
    return v


def _owned(session):
    pedirInfo.ids_cache = None
    ids, cities = pedirInfo.getIdsOfCities(session)
    if not 1 <= len(ids) <= 100:
        raise ValueError("Invalid owned city inventory")
    return {int(c): decodeUnicodeEscape(cities[c]["name"]) for c in ids}


def _city(session, cid):
    city = getCityById(session, str(cid))
    if str(city["id"]) != str(cid):
        raise ValueError("City identity changed")
    return city


def incoming_amount(session, target, name, resource, source_name=None):
    """Conservative matching: duplicate owned city names share reservations."""
    raw = _advisor_data(session, target)
    rows = raw[1][1][2]["viewScriptParams"]["militaryAndFleetMovements"]
    if not isinstance(rows, list) or len(rows) > 250:
        raise ValueError("Incoming cargo unavailable")
    result = 0
    for row in rows:
        returning = row["event"]["isFleetReturning"]
        if type(returning) is not bool:
            raise ValueError("Movement direction unavailable")
        dest = row["origin" if returning else "target"]
        label = dest.get("name")
        if not isinstance(label, str) or not label:
            raise ValueError("Movement destination unavailable")
        if decodeUnicodeEscape(label) != name:
            continue
        player = dest.get("avatarName")
        if player is None:
            player = ""
        if not isinstance(player, str):
            raise ValueError("Movement destination unavailable")
        # A matching city name with no attested player is ambiguous. Never
        # silently omit its cargo; duplicate names are conservatively counted.
        if player and decodeUnicodeEscape(player).casefold() != session.username.casefold():
            continue
        if source_name is not None:
            # A checkpoint receipt needs a matching owned source, not merely
            # an increase in unrelated cargo heading to the same warehouse.
            if returning:
                continue
            source = row["origin"]
            origin_name, origin_player = source.get("name"), source.get("avatarName")
            if not isinstance(origin_name, str):
                raise ValueError("Movement origin unavailable")
            if decodeUnicodeEscape(origin_name) != source_name:
                continue
            if not player or not isinstance(origin_player, str) or not origin_player:
                raise ValueError("Movement ownership unavailable")
            if decodeUnicodeEscape(origin_player).casefold() != session.username.casefold():
                continue
        cargo = row.get("resources")
        if not isinstance(cargo, list) or len(cargo) > 6:
            raise ValueError("Incoming cargo unavailable; inspect movements")
        for entry in cargo:
            key = entry["cssClass"].split()
            if len(key) < 2 or key[1] not in (*materials_names_tec, "gold"):
                raise ValueError("Unknown incoming resource")
            if key[1] == materials_names_tec[resource]:
                value = entry["amount"]
                if not isinstance(value, str):
                    raise ValueError("Invalid incoming quantity")
                number = re.sub(r"[, .\u00a0]", "", value)
                if not re.fullmatch(r"[0-9]{1,13}", number):
                    raise ValueError("Invalid incoming quantity")
                result += _amount(int(number))
    return _amount(result)


def _target(session, target, resource):
    names = _owned(session)
    if target not in names:
        raise ValueError("Destination no longer owned")
    incoming = incoming_amount(session, target, names[target], resource)
    city = _city(session, target)
    return names, city, _free_space(city["freeSpaceForResources"][resource]), incoming


def preview_fill(session, draft):
    target, resource, freighters = draft["destination_city"], draft["resource"], draft["useFreighters"]
    if type(target) is not int or resource not in RESOURCES or type(freighters) is not bool:
        raise ValueError("Invalid warehouse fill draft")
    i = RESOURCES.index(resource)
    try:
        names = _owned(session)
        if target not in names:
            raise ValueError("Destination no longer owned")
        city = _city(session, target)
        free = _free_space(city["freeSpaceForResources"][i])
        stock_at_target = _amount(city["availableResources"][i])
    except (Exception, SystemExit) as exc:
        raise FillPreviewError("fill_destination_unavailable") from exc
    try:
        incoming = incoming_amount(session, target, names[target], i)
    except (Exception, SystemExit) as exc:
        raise FillPreviewError("fill_incoming_unavailable") from exc
    budget = max(0, free-incoming)
    remaining = budget
    rows = []
    for cid in sorted(set(names)-{target}):
        try:
            stock = _amount(_city(session, cid)["availableResources"][i])
        except (Exception, SystemExit) as exc:
            raise FillPreviewError("fill_source_unavailable") from exc
        amount = min(stock, remaining)
        remaining -= amount
        rows.append({"city_id": cid, "city_name": names[cid], "stock": stock, "amount": amount})
    try:
        caps = pedirInfo.getShipCapacity(session)
        capacity = _amount(caps[int(freighters)])
        total = _amount((getTotalFreighters if freighters else getTotalShips)(session))
        available = _amount((getAvailableFreighters if freighters else getAvailableShips)(session))
        if available > total or (budget != remaining and (not capacity or not total)):
            raise ValueError("No usable fleet")
    except (Exception, SystemExit) as exc:
        raise FillPreviewError("fill_fleet_unavailable") from exc
    return {"destination_city": target, "destination_name": names[target],
            "stock": stock_at_target, "free_space": free, "incoming": incoming,
            "budget": budget, "amount": budget-remaining, "sources": rows,
            "capacity": capacity, "total_ships": total, "available_ships": available}


def prepare_fill(session, destination_city, resource, useFreighters=False, reviewed_sources=None, transfer_id=None):
    if type(destination_city) is not int or type(useFreighters) is not bool or resource not in RESOURCES:
        raise ValueError("Invalid warehouse fill")
    requireOwnCity(session, destination_city, "destination_city")
    if not isinstance(reviewed_sources, list) or not 0 <= len(reviewed_sources) <= 99:
        raise ValueError("Warehouse fill requires a reviewed allocation")
    seen = set()
    for row in reviewed_sources:
        if (not isinstance(row, dict) or set(row) != {"city_id", "amount"} or type(row["city_id"]) is not int
                or row["city_id"] == destination_city or row["city_id"] in seen or not _amount(row["amount"])):
            raise ValueError("Invalid warehouse fill source")
        requireOwnCity(session, row["city_id"], "source_city")
        seen.add(row["city_id"])
    config = {"destination_city": destination_city, "resource": resource, "useFreighters": useFreighters,
              "reviewed_sources": reviewed_sources}
    if transfer_id is not None:
        from ikabot.helpers.fixedTransferJournal import FixedTransferJournal
        FixedTransferJournal(session, transfer_id, _reviewed_routes(config), useFreighters, warehouse=True)
        config["transfer_id"] = transfer_id
    return config


def _reviewed_routes(config):
    index = RESOURCES.index(config["resource"])
    routes = []
    for row in config["reviewed_sources"]:
        amounts = [0] * len(RESOURCES)
        amounts[index] = row["amount"]
        routes.append({"from": row["city_id"], "to": config["destination_city"], "resources": amounts})
    return routes


class _WarehousePolicy:
    """Only warehouse-specific rules; route execution remains in executeRoutes."""

    def __init__(self, session, destination, resource, freighters):
        self.session, self.destination = session, destination
        self.index, self.resource = RESOURCES.index(resource), resource
        self.freighters = freighters
        self.sent = 0
        self.before_incoming = 0
        self.checkpoint = None
        self.source = None
        self.full = False

    def _observe(self, source, target, island=None):
        if int(target) != self.destination:
            raise ValueError("Reviewed destination changed")
        names, city, free, incoming = _target(self.session, self.destination, self.index)
        if int(source) not in names or (island is not None and str(city["islandId"]) != str(island)):
            raise ValueError("Storage or ownership changed; review before retrying")
        return max(0, free - incoming), incoming

    def _has_space(self, budget):
        if budget:
            return True
        if self.checkpoint is not None:
            self.checkpoint.warehouse_capacity_reached()
        self.full = True
        mark(self.session, "capacity_reached")
        self.session.setStatus(f"Storage budget exhausted; submitted {self.sent:,}")
        return False

    def before_wait(self, source, target):
        mark(self.session, "checking_destination")
        budget, _ = self._observe(source, target)
        if not self._has_space(budget):
            return False
        total = (getTotalFreighters if self.freighters else getTotalShips)(self.session)
        if type(total) is not int or total <= 0:
            raise ValueError("Selected fleet unavailable")
        mark(self.session, "waiting_ships")
        return True

    def limit(self, origin, target, island, proposed):
        mark(self.session, "checking_source")
        stock = _amount(origin["availableResources"][self.index])
        budget, _ = self._observe(origin["id"], target["id"], island)
        if not self._has_space(budget):
            return None
        if any(n for i, n in enumerate(proposed) if i != self.index):
            raise ValueError("Unexpected reviewed resource")
        cargo = [0] * len(RESOURCES)
        cargo[self.index] = min(_amount(proposed[self.index]), stock, budget)
        return cargo

    def before_send(self, source, target, island, cargo):
        mark(self.session, "checking_guard")
        budget, self.before_incoming = self._observe(source, target, island)
        if cargo[self.index] > budget:
            raise ValueError("Storage or ownership changed; review before retrying")
        if self.checkpoint is not None:
            self.source = int(source)
            self.before_incoming = self._source_incoming()

    def _source_incoming(self):
        names = _owned(self.session)
        if self.source not in names or self.destination not in names:
            raise ValueError("Warehouse source or destination changed")
        source_name, dest_name = names[self.source], names[self.destination]
        if list(names.values()).count(source_name) != 1 or list(names.values()).count(dest_name) != 1:
            raise ValueError("Ambiguous warehouse city names; review before retrying")
        return incoming_amount(self.session, self.destination, dest_name, self.index, source_name)

    def after_send(self, cargo):
        quantity = cargo[self.index]
        self.sent += quantity
        mark(self.session, "verifying_cargo", submitted=self.sent)
        self.session.setStatus(f"Submitted {self.sent:,} {self.resource}; checking incoming cargo")
        for attempt in range(3):
            _, _, _, observed = _target(self.session, self.destination, self.index)
            if self.checkpoint is not None:
                observed = self._source_incoming()
            if observed >= self.before_incoming + quantity:
                if self.checkpoint is not None:
                    self.checkpoint.warehouse_observed(cargo)
                mark(self.session, "verifying_cargo", verified=self.sent)
                return
            if attempt < 2:
                wait(2)
        self.session.setStatus(f"Submitted {self.sent:,}; incoming cargo unconfirmed. Review before retrying.")
        raise RuntimeError("Warehouse cargo unconfirmed; reconcile before retrying")


@task("fillCityWarehouse", prepare=prepare_fill, report_error=False)
def fill(session, destination_city, resource, useFreighters=False, reviewed_sources=None, transfer_id=None):
    """Translate the review to upstream JSON routes and use the shared sender."""
    mark(session, "preparing")
    config = prepare_fill(session, destination_city, resource, useFreighters, reviewed_sources, transfer_id)
    index = RESOURCES.index(resource)
    setInfoSignal(session, f"Fill warehouse: {resource} (one time)")
    # Cap the reviewed amounts at fresh stock before upstream's strict
    # preparation. The shared executor rechecks stock before each load.
    routes = _reviewed_routes(config) if transfer_id is not None else []
    if transfer_id is None:
        for row in config["reviewed_sources"]:
            amount = min(row["amount"], _amount(_city(session, row["city_id"])["availableResources"][index]))
            if amount:
                routes.append({"from": row["city_id"], "to": destination_city,
                               "resources": {resource: amount}})
    policy = _WarehousePolicy(session, destination_city, resource, useFreighters)
    if routes:
        # The exact same preparation and execution functions as sendResources CLI.
        prepared = sendResources.prepare_sendResources(session, routes, useFreighters, transfer_id, warehouse=transfer_id is not None)
        sendResources.execute_prepared_shipments(session, **prepared, policy=policy)
    if not policy.full:
        complete = policy.checkpoint is None or policy.checkpoint.warehouse_finish()
        mark(session, "finished")
        session.setStatus(f"Warehouse fill finished; submitted {policy.sent:,} {resource}" if complete else
                          f"Warehouse fill held: source stock depleted; submitted {policy.sent:,} {resource}")
