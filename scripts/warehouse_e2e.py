#!/usr/bin/env python3
"""Host-local, policy-scoped warehouse acceptance client; no direct engine access."""
import argparse
import fcntl
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

BASE = "http://127.0.0.1:8765/api/v1/"
TASK = "fillCityWarehouse"
RESOURCES = ("wood", "wine", "marble", "crystal", "sulfur")
SAFE_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")


class RefuseRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Unavailable(Exception):
    pass


class Client:
    def __init__(self, token):
        if not isinstance(token, str) or len(token) < 32:
            raise Unavailable("controller credential not provisioned")
        self.token = token
        self.opener = build_opener(ProxyHandler({}), RefuseRedirect())

    def call(self, path, body=None):
        req = Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                      headers={"Authorization": "Bearer " + self.token,
                               "Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=150) as res:
                raw = res.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise Unavailable("response exceeds limit")
                return json.loads(raw)
        except HTTPError as exc:
            raise Unavailable(f"HTTP {exc.code}") from None
        except (URLError, TimeoutError, ValueError, OSError):
            raise Unavailable("controller response unavailable") from None


def scope(path):
    p = Path(path)
    st = p.stat()
    if p.is_symlink() or st.st_uid != 0 or st.st_mode & 0o022:
        raise Unavailable("operator scope must be root-owned and not writable by others")
    v = json.loads(p.read_text())
    if (set(v) != {"player", "city", "resource", "useFreighters"}
            or not all(isinstance(v[k], str) and 0 < len(v[k]) <= 120 for k in ("player", "city"))
            or v["resource"] not in RESOURCES or type(v["useFreighters"]) is not bool):
        raise Unavailable("invalid operator scope")
    return v


def exact(rows, key, value):
    matches = [r for r in rows if isinstance(r.get(key), str)
               and r[key].casefold() == value.casefold()]
    if len(matches) != 1:
        raise Unavailable("scope identity not unique or unavailable")
    return matches[0]


def project_tasks(data):
    return {"requests": [{k: r.get(k) for k in ("request_id", "task", "status", "task_id", "pid")}
                         for r in data["requests"] if r.get("task") == TASK
                         or r.get("status") in ("dispatching", "unconfirmed")],
            "engine_tasks": [{k: r.get(k) for k in ("task_id", "task", "status", "pid", "started_at", "outcome")}
                             for r in data["engine_tasks"]]}


def run(client, policy, mode, confirmation=None, preview_file=None, *, skip_movements=False):
    def emit(stage, result):
        print(json.dumps({"stage": stage, "result": result}, ensure_ascii=False), flush=True)

    health = client.call("health")
    if health.get("synthetic_demo") is not False or health.get("mode") != "task_control_opt_in":
        raise Unavailable("not a live task-control backend")
    emit("health", {k: health.get(k) for k in ("mode", "authenticated_workers")})
    account = exact(client.call("accounts")["accounts"], "player", policy["player"])
    aid = account["id"]
    if not SAFE_ID.fullmatch(aid) or account.get("enabled") is not True:
        raise Unavailable("account unavailable")
    emit("account", {"player": policy["player"], "session_status": account.get("session_status")})
    prefix = "accounts/" + aid
    tasks = client.call(prefix + "/tasks")
    emit("tasks", project_tasks(tasks))
    preflight = client.call(prefix + "/tasks/preflight?task=" + TASK)
    emit("preflight", {k: preflight.get(k) for k in ("ready", "reason", "unresolved_request")})
    cities = client.call(prefix + "/cities")["cities"]
    city = exact(cities, "name", policy["city"])
    cid = city["id"]
    if type(cid) is not int or cid <= 0:
        raise Unavailable("invalid city identity")
    emit("destination", {"name": city["name"], "owned_cities": len(cities)})
    if mode == "inspect":
        # All failures are explicitly reported; no state-changing endpoint is called.
        try:
            snapshot = client.call("warehouses/" + aid)
            row = next(r for r in snapshot["cities"] if r["city_id"] == cid)
            key = "glass" if policy["resource"] == "crystal" else policy["resource"]
            resources = row["resources"]
            emit("warehouse", {"stock": resources["total"].get(key),
                               "capacity": resources.get("capacity"),
                               "captured_at": row.get("captured_at")})
        except (Unavailable, KeyError, StopIteration) as exc:
            emit("warehouse", {"unavailable": str(exc) if isinstance(exc, Unavailable) else "invalid observation"})
        if skip_movements:
            emit("movements", {"unavailable": "operator skipped legacy movement read"})
            return
        try:
            movements = client.call(prefix + "/ship-movements")["movements"]
            matching = [r for r in movements if
                        r.get("destination") == policy["city"] and
                        r.get("destination_player", "").casefold() == policy["player"].casefold()
                        and r.get("returning") is False and r.get("hostile") is False]
            emit("movements", {"matching_count": len(matching),
                               "ship_counts": [r.get("ships") for r in matching],
                               "seconds_remaining": [r.get("seconds_remaining") for r in matching],
                               "cargo_quantity_available": False})
        except Unavailable as exc:
            emit("movements", {"unavailable": str(exc)})
        return
    if preflight.get("ready") is not True or preflight.get("unresolved_request") is not False:
        raise Unavailable("preflight blocks preview or dispatch; reconcile first")
    draft = {"destination_city": cid, "resource": policy["resource"], "useFreighters": policy["useFreighters"]}
    if mode in ("preview", "observe"):
        plan = client.call(prefix + "/reward-distribution-plan", {"task": TASK, "draft": draft})
        if plan.get("account_id") != aid or plan.get("task") != TASK or plan.get("draft") != draft:
            raise Unavailable("review scope mismatch")
        if mode == "observe":
            emit("observation", plan["observation"])
            return
        ttl = plan.get("expires_in")
        if type(ttl) is not int or not 1 <= ttl <= 300:
            raise Unavailable("invalid review deadline")
        # Store the short-lived review ticket privately, never print it.
        request_id = str(uuid.uuid4())
        old = Path(preview_file)
        if old.exists():
            previous = load_review(old)
            if previous.get("deadline", 0) > time.time():
                raise Unavailable("unexpired review exists; confirm or let it expire")
            old.unlink()
        fd = os.open(preview_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"account_id": aid, "draft": draft, "plan": plan, "request_id": request_id,
                       "deadline": time.time() + ttl}, f)
        emit("preview", {"request_id": request_id, "observation": plan["observation"],
                         "expires_in": plan.get("expires_in")})
        return
    if mode != "start" or confirmation is None:
        raise Unavailable("explicit reviewed request confirmation required")
    if any(r.get("status") in ("running", "stopping") for r in tasks["engine_tasks"]):
        raise Unavailable("active account tasks; do not dispatch")
    p = Path(preview_file)
    review = load_review(p)
    if review.get("deadline", 0) <= time.time():
        raise Unavailable("review expired; generate a fresh preview")
    if (review["account_id"] != aid or review["draft"] != draft
            or review["request_id"] != confirmation or str(uuid.UUID(confirmation)) != confirmation):
        raise Unavailable("review confirmation mismatch")
    if review["plan"]["observation"]["amount"] <= 0:
        raise Unavailable("no positive reviewed transfer")
    # Consume local review BEFORE dispatch; a lost response is never replayed.
    p.unlink()
    try:
        receipt = client.call(prefix + "/tasks/fill-warehouse-start",
                              {"preview_id": review["plan"]["preview_id"],
                               "request_id": confirmation, "confirmed": True})
        emit("launch", {k: receipt.get(k) for k in ("request_id", "task", "status", "task_id", "pid")})
    except Unavailable as exc:
        emit("launch", {"request_id": confirmation, "status": "check_receipt", "reason": str(exc)})
    emit("receipt_recheck", project_tasks(client.call(prefix + "/tasks")))


def load_review(path):
    st = path.stat()
    if path.is_symlink() or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise Unavailable("review file permissions invalid")
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("inspect", "observe", "preview", "start"), nargs="?", default="inspect")
    parser.add_argument("--confirm-request")
    parser.add_argument("--skip-movements", action="store_true",
                        help="skip the legacy movement endpoint on older releases")
    args = parser.parse_args()
    try:
        policy = scope("/etc/daedalus/e2e-scope.json")
        fd = os.open("/var/lib/daedalus/e2e/runner.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run(Client(os.environ.get("DAEDALUS_API_TOKEN")), policy, args.mode,
                args.confirm_request, "/var/lib/daedalus/e2e/review.json",
                skip_movements=args.skip_movements)
    except (Unavailable, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc) if isinstance(exc, Unavailable)
                          else "invalid local state or observation"}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
