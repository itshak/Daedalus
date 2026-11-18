#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import ast
import ctypes
import importlib
import importlib.util
import inspect
import json
import multiprocessing
import os
import re
import secrets
import socket
import sys
import threading
import time
from uuid import UUID

import psutil

from ikabot import config
from ikabot.helpers.decorators import _TASK_REGISTRY
from ikabot.helpers.logging import getLogger, setLoggedInPlayer
from ikabot.helpers.process import set_child_mode, updateProcessList
from ikabot.helpers.sessionStorage import (
    get_global_config_path,
    get_home_dir,
    get_ikabot_dir,
    init_storage,
    read_json_file,
    write_json_file,
)
from ikabot.web.session import Session, parse_world_spec

logger = getLogger(__name__)

_CLI_FLAGS = (
    "--task",
    "--email",
    "--world",
    "--player",
    "--config",
    "--batch",
    "--cities",
    "--server",
    "--help",
    "-h",
)
_BATCH_ENTRY_KEYS = ("task", "config", "email", "world", "server", "player")
# the game's order of the resources (a city's "tradegood" index)
_TRADEGOODS = ("wood", "wine", "marble", "crystal", "sulfur")
_MAX_IPC_MSG_BYTES = 16 * 1024 * 1024
_TASK_STARTUP_TIMEOUT = 60.0
_LOCAL_SERVER = None
_LOCAL_SERVER_LOCK = threading.Lock()


def get_ipc_file_path():
    """Return path to ~/.ikabot/ipc.json."""
    return os.path.join(get_ikabot_dir(), "ipc.json")


def get_ipc_lock_path():
    """Return path to ~/.ikabot/ipc.lock."""
    return os.path.join(get_ikabot_dir(), "ipc.lock")


def get_tasks_dir():
    """Return path to ~/.ikabot/tasks (saved --batch files)."""
    return os.path.join(get_ikabot_dir(), "tasks")


def is_cli_invocation(argv):
    """Return True if argv uses CLI flags (--task, --email, --world, --config, etc.)
    rather than interactive mode or legacy positional predetermined_input.
    """
    for arg in argv[1:]:
        if arg in _CLI_FLAGS:
            return True
        for flag in _CLI_FLAGS:
            if flag.startswith("--") and arg.startswith(flag + "="):
                return True
    return False


class _StartupLock:
    """Cross-process lock file in ~/.ikabot/ipc.lock to prevent race conditions
    when multiple CLI processes check/start the IPC server simultaneously.
    """

    def __init__(self, timeout=5.0):
        self.timeout = timeout
        self.path = get_ipc_lock_path()
        self.acquired = False

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, str(os.getpid()).encode("utf-8"))
                finally:
                    os.close(fd)
                self.acquired = True
                return self
            except FileExistsError:
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        holder_pid = int(f.read().strip() or "0")
                    stale_age = time.time() - os.path.getmtime(self.path) > 15.0
                    if (holder_pid and not psutil.pid_exists(holder_pid)) or stale_age:
                        os.remove(self.path)
                        continue
                except Exception:
                    pass
                if time.time() >= deadline:
                    return self
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            try:
                os.remove(self.path)
            except OSError:
                pass


def _extract_windows_raw_config(raw_cmdline=None):
    """Recover lossless JSON after --config from Windows GetCommandLineW() when
    PowerShell 5.1 strips inner double quotes before building sys.argv.
    """
    if raw_cmdline is None:
        if not config.isWindows:
            return None
        try:
            ctypes.windll.kernel32.GetCommandLineW.restype = ctypes.c_wchar_p
            raw_cmdline = ctypes.windll.kernel32.GetCommandLineW()
        except Exception:
            return None
    if not raw_cmdline:
        return None
    idx = raw_cmdline.rfind("--config")
    if idx == -1:
        return None
    brace_idx = raw_cmdline.find("{", idx)
    if brace_idx == -1:
        return None
    obj, _ = json.JSONDecoder().raw_decode(raw_cmdline[brace_idx:])
    return obj if isinstance(obj, dict) else None


def _read_arg_file(text, opening):
    """Return the contents of @file / bare file path arguments, or text unchanged."""
    if text.startswith("@"):
        filepath = text[1:].strip()
        if not os.path.isfile(filepath):
            raise ValueError(f"File not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    if not text.startswith(opening) and os.path.isfile(text):
        with open(text, "r", encoding="utf-8") as f:
            return f.read().strip()
    return text


def parse_config_arg(config_str, raw_cmdline=None):
    """Parse --config value from JSON string, Python dict literal, @file.json,
    or Windows raw command line fallback.
    """
    if config_str is None or str(config_str).strip() == "":
        return {}
    text = _read_arg_file(str(config_str).strip(), "{")

    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("--config must decode to a JSON object/dictionary.")
        return parsed
    except json.JSONDecodeError:
        pass

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    try:
        recovered = _extract_windows_raw_config(raw_cmdline=raw_cmdline)
        if isinstance(recovered, dict):
            return recovered
    except Exception:
        pass

    raise ValueError(
        f"Invalid --config dictionary: {config_str!r}. Pass a valid JSON object (e.g. '{{\"minutes\": 20}}')."
    )


def parse_batch_arg(batch_str, overrides=None):
    """Parse --batch value (JSON list of task entries, a single entry, or @file.json)
    into a list of start_task requests. email/world/server/player given in ``overrides``
    (the CLI flags) replace the entries' own values; the others are kept.
    """
    if batch_str is None or str(batch_str).strip() == "":
        raise ValueError("--batch cannot be empty.")
    text = _read_arg_file(str(batch_str).strip(), "[")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid --batch JSON: {exc}")
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("--batch must be a non-empty JSON list of task entries.")

    overrides = overrides or {}
    requests = []
    for idx, entry in enumerate(parsed, start=1):
        if not isinstance(entry, dict) or not entry.get("task"):
            raise ValueError(f"Batch entry {idx} must be an object with a 'task' key.")
        unknown = [k for k in entry if k not in _BATCH_ENTRY_KEYS]
        if unknown:
            raise ValueError(
                f"Batch entry {idx} has unknown key(s) {unknown}. Expected: {list(_BATCH_ENTRY_KEYS)}"
            )
        task_config = entry.get("config") or {}
        if not isinstance(task_config, dict):
            raise ValueError(f"Batch entry {idx}: 'config' must be an object.")
        request = {"action": "start_task", "task": entry["task"], "config": task_config}
        for key in ("email", "world", "server", "player"):
            request[key] = overrides.get(key) or entry.get(key)
        requests.append(request)
    return requests


def build_batch_entry(session, process):
    """Build a --batch entry that relaunches a running task (processList row) on this session's account."""
    entry = {
        "task": process["action"],
        "world": f"s{session.mundo}-{session.servidor}",
        "player": session.username,
        "config": process["config"],
    }
    if getattr(session, "mail", ""):
        entry = {"email": session.mail, **entry}
    return entry


def _write_tasks_file(session, name, data):
    """Write ``data`` to ~/.ikabot/tasks/<player>_s<world>-<lang>_<name>.json and return the path."""
    stem = f"{session.username}_s{session.mundo}-{session.servidor}_{name}"
    stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    path = os.path.join(get_tasks_dir(), stem + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def save_task_config(session, process):
    """Write one running task's config as a --config file (see build_task_command).
    Returns the path, or None if the task has no config.
    """
    if process.get("config") is None:
        return None
    return _write_tasks_file(session, process["action"], process["config"])


def build_task_command(session, process, config_path):
    """Return the `ikabot --task=... --config=@...` command that relaunches ``process``."""
    entry = build_batch_entry(session, process)
    args = []
    if entry.get("email"):
        args.append(f'--email="{entry["email"]}"')
    args += [
        f'--world={entry["world"]}',
        f'--player="{entry["player"]}"',
        f'--task={entry["task"]}',
        f'--config="@{config_path}"',
    ]
    return "ikabot " + " ".join(args)


def save_batch_file(session, processes, name):
    """Write the configs of ``processes`` to ~/.ikabot/tasks/<player>_s<world>-<lang>_<name>.json
    as a --batch file. Rows without a config are skipped.
    Returns (path, saved_count, skipped_actions).
    """
    entries = [build_batch_entry(session, p) for p in processes if p.get("config") is not None]
    skipped = [p["action"] for p in processes if p.get("config") is None]
    if not entries:
        return None, 0, skipped
    return _write_tasks_file(session, name, entries), len(entries), skipped


def _lookup_registry(task_name):
    if task_name in _TASK_REGISTRY:
        return task_name, _TASK_REGISTRY[task_name]
    low = task_name.lower()
    for reg_name, func in _TASK_REGISTRY.items():
        if reg_name.lower() == low:
            return reg_name, func
    return None, None


def _resolve_task(task_name):
    """Locate (canonical_name, task_func) for a @task-decorated ikabot module."""
    if not task_name or not str(task_name).strip():
        raise ValueError("Task name (--task) cannot be empty.")
    name = str(task_name).strip()

    found_name, found_func = _lookup_registry(name)
    if found_func is not None:
        return found_name, found_func

    func_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "function")
    if os.path.isdir(func_dir):
        for fname in os.listdir(func_dir):
            if not fname.endswith(".py") or fname.startswith("__"):
                continue
            mod_stem = fname[:-3]
            if mod_stem.lower() == name.lower():
                importlib.import_module(f"ikabot.function.{mod_stem}")
                found_name, found_func = _lookup_registry(name)
                if found_func is not None:
                    return found_name, found_func

    custom_paths = read_json_file(get_global_config_path(), {}).get("customModules", [])
    for cpath in custom_paths:
        if not isinstance(cpath, str) or not os.path.isfile(cpath):
            continue
        cstem = os.path.splitext(os.path.basename(cpath))[0]
        if cstem.lower() == name.lower():
            spec = importlib.util.spec_from_file_location(cstem, cpath)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            found_name, found_func = _lookup_registry(name)
            if found_func is not None:
                return found_name, found_func

    # Populate full registry so the error lists all available tasks
    if os.path.isdir(func_dir):
        for fname in sorted(os.listdir(func_dir)):
            if not fname.endswith(".py") or fname.startswith("__"):
                continue
            try:
                importlib.import_module(f"ikabot.function.{fname[:-3]}")
            except Exception:
                pass

    found_name, found_func = _lookup_registry(name)
    if found_func is not None:
        return found_name, found_func

    available = ", ".join(sorted(_TASK_REGISTRY.keys()))
    raise ValueError(
        f"Unknown background task '{name}'. Available tasks: {available}"
    )


def _validate_task_config(task_name, task_func, config_dict):
    """Validate config_dict against the @task function's parameter signature."""
    if not isinstance(config_dict, dict):
        raise ValueError("--config must be a dictionary.")
    raw = {k: v for k, v in config_dict.items() if k != "session"}
    clean = json.loads(json.dumps(raw, default=list))

    target = getattr(task_func, "__wrapped__", task_func)
    sig = inspect.signature(target)
    accepts_var_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )

    required = [
        pname
        for pname, p in sig.parameters.items()
        if pname != "session"
        and p.default is inspect.Parameter.empty
        and p.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    ]
    missing = [pname for pname in required if pname not in clean]
    if missing:
        raise ValueError(
            f"Missing required config parameter(s) for task '{task_name}': {missing}"
        )

    if not accepts_var_kw:
        allowed = {pname for pname in sig.parameters if pname != "session"}
        unknown = [k for k in clean if k not in allowed]
        if unknown:
            raise ValueError(
                f"Unknown config parameter(s) for task '{task_name}': {unknown}. Expected: {sorted(allowed)}"
            )

    return clean


def _run_ipc_task(task_name, session, task_config, started=None):
    """Child-process entry point for tasks launched via CLI/IPC."""
    if started is not None:
        # arguments are unpickled by now: the launching process may exit
        started.set()
    try:
        sys.stdin = open(os.devnull, "r")
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    except Exception:
        pass

    setLoggedInPlayer(getattr(session, "username", ""))
    set_child_mode(session)
    _, task_func = _resolve_task(task_name)
    try:
        task_func(session=session, **task_config)
    except Exception:
        logger.error("Unhandled exception in IPC task %s", task_name, exc_info=True)
        raise


def _send_json_line(sock, payload):
    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    sock.sendall(data)


def _recv_json_line(sock):
    buf = bytearray()
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf.extend(chunk)
        if b"\n" in chunk:
            break
        if len(buf) > _MAX_IPC_MSG_BYTES:
            raise ValueError("IPC message exceeded maximum size.")
    if not buf:
        raise EOFError("Empty IPC message.")
    line = bytes(buf).split(b"\n", 1)[0]
    return json.loads(line.decode("utf-8"))


class IPCServer:
    """Loopback socket server stored in ~/.ikabot/ipc.json so external CLI calls
    can add background tasks to an already-running ikabot main process.
    """

    def __init__(self, default_session=None):
        self._sock = None
        self.port = None
        self.authkey = secrets.token_hex(32)
        self._lock = threading.Lock()
        self._count_lock = threading.Lock()
        self._active_requests = 0
        self._running = False
        self._sessions = [default_session] if default_session is not None else []
        self._daedalus_tasks = {}  # only children started by existing-session IPC
        self._daedalus_requests = {}  # session-scoped UUID4 receipt cache
        self._thread = None

    @property
    def has_active_requests(self):
        with self._count_lock:
            return self._active_requests > 0

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(16)
        self._sock = sock
        self.port = sock.getsockname()[1]
        self._running = True

        ipc_path = get_ipc_file_path()
        write_json_file(
            ipc_path,
            {
                "pid": os.getpid(),
                "host": "127.0.0.1",
                "port": self.port,
                "authkey": self.authkey,
            },
        )
        try:
            os.chmod(ipc_path, 0o600)
        except OSError:
            pass

        self._thread = threading.Thread(
            target=self._accept_loop, name="ikabot-ipc-server", daemon=True
        )
        self._thread.start()
        return self

    def stop(self):
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        ipc_path = get_ipc_file_path()
        try:
            info = read_json_file(ipc_path, {})
            if info.get("pid") == os.getpid() and os.path.exists(ipc_path):
                os.remove(ipc_path)
        except OSError:
            pass

    def _accept_loop(self):
        while self._running and self._sock is not None:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            # counted from accept() on, so stopping the server can wait for it
            with self._count_lock:
                self._active_requests += 1
            threading.Thread(
                target=self._handle_client, args=(conn,), daemon=True
            ).start()

    def _handle_client(self, conn):
        try:
            self._serve_connection(conn)
        finally:
            with self._count_lock:
                self._active_requests -= 1

    def _serve_connection(self, conn):
        with conn:
            conn.settimeout(30.0)
            try:
                msg = _recv_json_line(conn)
                if not isinstance(msg, dict) or not secrets.compare_digest(
                    str(msg.get("authkey", "")), self.authkey
                ):
                    _send_json_line(
                        conn, {"status": "error", "error": "Unauthorized IPC request."}
                    )
                    return
                resp = self.handle_request(msg)
                _send_json_line(conn, resp)
            except Exception as exc:
                try:
                    _send_json_line(conn, {"status": "error", "error": str(exc)})
                except Exception:
                    pass

    def _session_matches(self, sess, email, world, server, player=None):
        if sess is None or not getattr(sess, "logged", False):
            return False
        if player and str(player).strip():
            sess_player = (getattr(sess, "username", None) or "").strip().lower()
            if sess_player != str(player).strip().lower():
                return False
        sess_mail = (getattr(sess, "mail", None) or "").strip().lower()
        if email and str(email).strip() and str(email).strip() != "default_user":
            if sess_mail != str(email).strip().lower():
                return False
        elif email == "default_user":
            if sess_mail != "":
                return False

        want_mundo, want_servidor, raw_world = parse_world_spec(world, server)
        if not raw_world and want_servidor is None:
            return True
        if want_mundo is not None:
            if str(getattr(sess, "mundo", "")) != want_mundo:
                return False
            if want_servidor is not None:
                s_srv = (getattr(sess, "servidor", "") or "").lower()
                l_srv = (getattr(sess, "login_servidor", "") or "").lower()
                if want_servidor not in (s_srv, l_srv):
                    return False
            return True
        if raw_world:
            if (getattr(sess, "word", "") or "").strip().lower() != raw_world.lower():
                return False
            if want_servidor is not None:
                s_srv = (getattr(sess, "servidor", "") or "").lower()
                l_srv = (getattr(sess, "login_servidor", "") or "").lower()
                if want_servidor not in (s_srv, l_srv):
                    return False
        return True

    def _get_or_create_session(self, email, world, server, player=None):
        matches = [
            sess
            for sess in self._sessions
            if self._session_matches(sess, email, world, server, player)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                "Multiple active sessions match; please specify --email, --world and/or --player."
            )
        sess = Session.from_saved(mail=email, world=world, server=server, player=player)
        self._sessions.append(sess)
        return sess

    def _existing_session(self, request):
        """Select an in-memory logged-in session; NEVER restore or create one.

        Daedalus uses this interface only with a fully specified world/player
        identity, so a controller cannot accidentally start a second game login.
        """
        world = request.get("world")
        player = request.get("player")
        if not isinstance(world, str) or not world.strip():
            raise ValueError("Existing-session IPC requires an explicit world")
        if not isinstance(player, str) or not player.strip():
            raise ValueError("Existing-session IPC requires an explicit player")
        matches = [
            sess
            for sess in self._sessions
            if self._session_matches(sess, None, world, None, player)
        ]
        if len(matches) != 1:
            raise ValueError("No unique already-authenticated game session matches")
        return matches[0]

    def _validate_session_existing(self, request):
        """Read-only validation of an already owned world session, never a login.

        The fixed game-world GET returns only a boolean to Daedalus. No HTML,
        cookies, redirect destinations, loginLink or action tokens cross IPC.
        """
        from urllib.parse import urlsplit

        session = self._existing_session(request)
        number = str(getattr(session, "mundo", ""))
        language = str(getattr(session, "servidor", "")).lower()
        if not re.fullmatch(r"[0-9]{1,6}", number) or not re.fullmatch(r"[a-z]{2,4}", language):
            raise ValueError("Invalid existing game world identity")
        host = f"s{number}-{language}.ikariam.gameforge.com"
        world = f"s{number}-{language}"
        identity = {"world": world, "username": str(session.username)}
        base_url = getattr(session, "urlBase", "")
        try:
            parsed = urlsplit(base_url)
            trusted_url = (
                parsed.scheme == "https" and parsed.hostname == host
                and parsed.path == "/index.php" and not parsed.username
                and not parsed.password and parsed.port in (None, 443)
                and parsed.query == "" and parsed.fragment == ""
            )
        except (ValueError, TypeError, AttributeError):
            trusted_url = False
        if not trusted_url:
            return {"status": "ok", **identity, "session_valid": False}
        try:
            response = session.s.get(base_url, timeout=8, verify=config.do_ssl_verify)
            text = response.text
            destination = urlsplit(str(response.url))
            # A valid city page includes its actionRequest marker. A bare 200
            # lobby or marketing/login page must never count as authenticated.
            valid = (
                response.status_code == 200
                and destination.scheme == "https"
                and destination.hostname == host
                and destination.path == "/index.php"
                and isinstance(text, str)
                and "actionRequest" in text
                and "index.php?logout" not in text
                and not session.isExpired(text)
                and "lobby.ikariam.gameforge.com" not in text
            )
        except (OSError, ValueError, TypeError, AttributeError):
            valid = False
        return {"status": "ok", **identity, "session_valid": bool(valid)}

    def _list_existing_sessions(self):
        """Nonsecret in-memory identities, without saved-session restoration."""
        sessions = []
        for sess in self._sessions:
            if not getattr(sess, "logged", False):
                continue
            world = f"s{getattr(sess, 'mundo', '')}-{getattr(sess, 'servidor', '')}"
            player = getattr(sess, "username", None)
            if not player or world == "s-":
                continue
            sessions.append({"world": world, "player": str(player)})
        return {"status": "ok", "pid": os.getpid(), "sessions": sessions}

    def handle_request(self, request):
        action = request.get("action")
        if action == "ping":
            return {"status": "ok", "pid": os.getpid()}

        try:
            with self._lock:
                if action == "start_task":
                    return self._start_task(request)
                if action == "list_cities":
                    return self._list_cities(request)
                if action == "list_sessions":
                    return self._list_existing_sessions()
                if action == "validate_session_existing":
                    return self._validate_session_existing(request)
                if action == "list_cities_existing":
                    return self._list_cities(request, existing_only=True)
                if action == "warehouse_snapshots_existing":
                    return self._warehouse_snapshots_existing(request)
                if action == "start_task_existing":
                    return self._start_task(request, existing_only=True)
                if action == "list_tasks_existing":
                    return self._list_existing_tasks(request)
                if action == "stop_task_existing":
                    return self._stop_existing_task(request)
                return {"status": "error", "error": f"Unknown IPC action: {action!r}"}
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            logger.error("IPC request failed", exc_info=True)
            response = {"status": "error", "error": str(exc)}
            if request.get("task"):
                response["task"] = request["task"]
            return response

    def _list_cities(self, request, existing_only=False):
        """The account's own cities, so task configs can use their ids."""
        from ikabot.helpers import pedirInfo
        from ikabot.helpers.varios import decodeUnicodeEscape

        session = (
            self._existing_session(request)
            if existing_only
            else self._get_or_create_session(
                request.get("email"), request.get("world"), request.get("server"), request.get("player")
            )
        )
        pedirInfo.ids_cache = None  # the cache lives as long as the menu: a city may be new or renamed
        ids, cities = pedirInfo.getIdsOfCities(session)
        result = {
            "status": "ok",
            "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username,
            "cities": [
                {
                    "id": city_id,
                    "name": decodeUnicodeEscape(cities[city_id]["name"]),
                    "coords": cities[city_id]["coords"].strip().strip("[]"),
                    "tradegood": _TRADEGOODS[int(cities[city_id]["tradegood"])],
                }
                for city_id in ids
            ],
        }
        if not existing_only:
            # Preserve upstream CLI semantics, including the email field.
            result["email"] = session.mail
        return result

    def _warehouse_snapshots_existing(self, request):
        """Read per-city warehouse spans via an existing authenticated session.

        Return ONLY formatted numeric resource strings, never whole page HTML,
        login data, actionRequest tokens or arbitrary hidden input values.
        """
        import html
        import re

        from ikabot.helpers import pedirInfo
        from ikabot.helpers.varios import decodeUnicodeEscape

        session = self._existing_session(request)
        pedirInfo.ids_cache = None
        ids, cities = pedirInfo.getIdsOfCities(session)
        if len(ids) > 100:
            raise ValueError("Too many cities for one warehouse snapshot")
        span_pattern = re.compile(
            r"""<span\b[^>]*\bid=["']js_(plunderable|capacity)_(wood|wine|marble|crystal|glass|sulfur)["'][^>]*>(.*?)</span>""",
            re.IGNORECASE | re.DOTALL,
        )
        tooltip_pattern = re.compile(
            r"""<div\b[^>]*\bclass=["'][^"']*\btooltip\b[^"']*["'][^>]*>(.*?)</div>""",
            re.IGNORECASE | re.DOTALL,
        )
        safe_number = re.compile(r"[0-9][0-9,.\s\u00a0\u202f]*[KMBkmb]?\Z")
        results = []
        for city_id in ids:
            if type(city_id) is not int or city_id <= 0:
                raise ValueError("Invalid authenticated city ID")
            markup = session.get(f"view=warehouse&cityId={city_id}", noIndex=True)
            if not isinstance(markup, str):
                raise ValueError("Warehouse response is not HTML")
            unsecured = {}
            capacity = None
            for kind, resource, inner in span_pattern.findall(markup):
                tooltip = tooltip_pattern.search(inner)
                amount = tooltip.group(1) if tooltip is not None else inner
                amount = html.unescape(re.sub(r"<[^>]*>", "", amount)).strip()
                if not safe_number.fullmatch(amount):
                    raise ValueError("Warehouse amount is not numeric")
                key = "glass" if resource.casefold() == "crystal" else resource.casefold()
                if kind.casefold() == "plunderable":
                    unsecured[key] = amount
                elif capacity is None:
                    capacity = amount
            if not unsecured:
                raise ValueError("No unsecured warehouse resource values")
            raw_coords = cities[city_id].get("coords")
            # Only numeric coordinate pairs may leave the engine. The city
            # inventory comes from the authenticated session; no second call.
            island = None
            if isinstance(raw_coords, str):
                candidate = raw_coords.strip().strip("[]").strip()
                if re.fullmatch(r"[0-9]{1,3}:[0-9]{1,3}", candidate):
                    island = candidate
            results.append({
                "city_id": city_id,
                "city_name": decodeUnicodeEscape(cities[city_id]["name"]),
                "unsecured": unsecured,
                "capacity": capacity,
                "island": island,
            })
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "cities": results}

    def _task_entry(self, request):
        world = request.get("world")
        player = request.get("player")
        if not isinstance(world, str) or not world.strip():
            raise ValueError("Task management requires world")
        if not isinstance(player, str) or not player.strip():
            raise ValueError("Task management requires player")
        return world.casefold(), player.casefold()

    def _list_existing_tasks(self, request):
        world, player = self._task_entry(request)
        rows = []
        for task_id, entry in self._daedalus_tasks.items():
            if (entry["world"].casefold(), entry["player"].casefold()) != (world, player):
                continue
            proc = entry["process"]
            if entry["status"] == "running" and not proc.is_alive():
                entry["status"] = "finished"
            rows.append({
                "task_id": task_id, "task": entry["task"], "pid": entry["pid"],
                "status": entry["status"], "started_at": entry["started_at"],
            })
        return {"status": "ok", "tasks": rows, "world": request["world"],
                "player": request["player"]}

    def _stop_existing_task(self, request):
        world, player = self._task_entry(request)
        task_id = request.get("task_id")
        if not isinstance(task_id, str) or len(task_id) != 24:
            raise ValueError("A valid managed task ID is required")
        entry = self._daedalus_tasks.get(task_id)
        if entry is None or (entry["world"].casefold(), entry["player"].casefold()) != (world, player):
            raise ValueError("Task is not managed for this account")
        proc = entry["process"]
        if entry["status"] in ("finished", "stopped") or not proc.is_alive():
            entry["status"] = "finished" if entry["status"] != "stopped" else "stopped"
        else:
            proc.terminate()
            proc.join(timeout=4.0)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=4.0)
            entry["status"] = "stopping" if proc.is_alive() else "stopped"
        return {"status": "ok", "task_id": task_id, "task": entry["task"],
                "pid": entry["pid"], "task_status": entry["status"]}

    def _start_task(self, request, existing_only=False):
        task_name = request.get("task")
        config_dict = request.get("config") or {}
        email = request.get("email")
        world = request.get("world")
        server = request.get("server")
        player = request.get("player")

        if existing_only:
            # Public CLI custom modules remain usable, but the opt-in GUI path
            # accepts only built-in @task-decorated engine modules.
            if not isinstance(task_name, str) or not re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_]{0,79}", task_name
            ):
                raise ValueError("A built-in IkaBot task name is required")
            builtin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "function")
            builtin = next(
                (fname[:-3] for fname in os.listdir(builtin_dir)
                 if fname.endswith(".py") and fname[:-3].casefold() == task_name.casefold()),
                None,
            )
            if builtin is None:
                raise ValueError("Only built-in engine background tasks can be started")
            task_name = builtin
            if not isinstance(request.get("config"), dict) or "session" in request["config"]:
                raise ValueError("Task config must be a JSON object without session values")
            try:
                canonical_config = json.dumps(
                    request["config"], sort_keys=True, ensure_ascii=False, allow_nan=False,
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("Task config must contain finite JSON values") from exc
            if len(canonical_config.encode("utf-8")) > 16384:
                raise ValueError("Task config exceeds safe size limit")
            session = self._existing_session(request)
            request_id = request.get("request_id")
            if not isinstance(request_id, str) or not re.fullmatch(
                r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
                request_id,
            ) or str(UUID(request_id)) != request_id:
                raise ValueError("Task request requires a canonical UUID4 idempotency key")
            fingerprint = (
                f"s{session.mundo}-{session.servidor}".casefold(), session.username.casefold(),
                task_name, hashlib.sha256(canonical_config.encode("utf-8")).hexdigest(),
            )
            prior = self._daedalus_requests.get(request_id)
            if prior is not None:
                if prior[0] != fingerprint:
                    raise ValueError("Task request ID was reused with different inputs")
                return dict(prior[1])

        canonical_name, task_func = _resolve_task(task_name)
        if existing_only and task_func.__module__ != f"ikabot.function.{canonical_name}":
            raise ValueError("Only built-in IkaBot task implementations are allowed")
        clean_config = _validate_task_config(canonical_name, task_func, config_dict)
        if not existing_only:
            session = self._get_or_create_session(email, world, server, player)
        if existing_only:
            active_same_account = sum(
                entry["world"].casefold() == fingerprint[0]
                and entry["player"].casefold() == fingerprint[1]
                and entry["process"].is_alive()
                for entry in self._daedalus_tasks.values()
            )
            if active_same_account >= 16:
                raise ValueError("Account has reached the active task safety limit")
            if len(self._daedalus_tasks) >= 256:
                raise ValueError("Managed task registry has reached its safety limit")
            if len(self._daedalus_requests) >= 2048:
                raise ValueError("Task receipt cache is full; manual recovery is required")
        prepare = getattr(task_func, "prepare", None)
        if prepare is not None:
            # errors found here go back to the CLI instead of only to the task's log
            prepared = prepare(session, **clean_config)
            if prepared is not None:
                clean_config = _validate_task_config(canonical_name, task_func, prepared)

        started = multiprocessing.Event()
        proc = multiprocessing.Process(
            target=_run_ipc_task,
            args=(canonical_name, session, clean_config, started),
            name=canonical_name,
        )
        proc.start()
        # A spawned child reads its arguments through a handle owned by this process,
        # so wait for it before answering: a CLI launcher exits right after the answer.
        if not started.wait(timeout=_TASK_STARTUP_TIMEOUT) and not proc.is_alive():
            raise RuntimeError(
                f"Task '{canonical_name}' exited during startup (exit code {proc.exitcode})."
            )

        entry = {
            "pid": proc.pid,
            "action": canonical_name,
            "date": time.time(),
            "status": "started",
            "config": clean_config,
        }
        try:
            updateProcessList(session, programprocesslist=[entry])
        except Exception:
            # An untracked process could continue performing game actions
            # while the controller mistakenly considers a retry safe.
            if existing_only and proc.is_alive():
                proc.terminate()
                proc.join(timeout=4.0)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=4.0)
            raise

        response = {
            "status": "ok", "pid": proc.pid, "task": canonical_name,
            "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "host_pid": os.getpid(),
        }
        if existing_only:
            task_id = secrets.token_hex(12)
            self._daedalus_tasks[task_id] = {
                "process": proc, "pid": proc.pid, "task": canonical_name,
                "world": response["world"], "player": session.username,
                "status": "running", "started_at": time.time(),
            }
            response["task_id"] = task_id
            self._daedalus_requests[request_id] = (fingerprint, dict(response))
        else:
            # Keep the original upstream CLI response intact.
            response["email"] = session.mail
        return response


def send_ipc_request(request, connect_timeout=1.5, read_timeout=120.0):
    """Send a request dict to the running ikabot IPC server if one exists.
    Returns the decoded response dict, or None if no live server is reachable.
    """
    ipc_path = get_ipc_file_path()
    info = read_json_file(ipc_path, None)
    if not isinstance(info, dict):
        return None
    pid = info.get("pid")
    host = info.get("host") or "127.0.0.1"
    port = info.get("port")
    authkey = info.get("authkey")
    if not pid or not port or not authkey or not psutil.pid_exists(int(pid)):
        return None

    try:
        with socket.create_connection((host, int(port)), timeout=connect_timeout) as sock:
            sock.settimeout(read_timeout)
            payload = dict(request)
            payload["authkey"] = authkey
            _send_json_line(sock, payload)
            return _recv_json_line(sock)
    except OSError:
        return None
    except EOFError:
        return None


def ping_ipc_server():
    """Return True if a live ikabot IPC server responds on ~/.ikabot/ipc.json."""
    resp = send_ipc_request({"action": "ping"}, connect_timeout=1.0, read_timeout=2.0)
    return isinstance(resp, dict) and resp.get("status") == "ok"


def ensure_ipc_server(default_session=None):
    """Ensure an IPC server is running in this interactive ikabot process if no
    other ikabot main process on the system already owns ~/.ikabot/ipc.json.
    """
    global _LOCAL_SERVER
    with _LOCAL_SERVER_LOCK:
        if _LOCAL_SERVER is not None:
            if default_session is not None and default_session not in _LOCAL_SERVER._sessions:
                _LOCAL_SERVER._sessions.insert(0, default_session)
            return _LOCAL_SERVER
        with _StartupLock():
            if ping_ipc_server():
                return None
            _LOCAL_SERVER = IPCServer(default_session=default_session).start()
            return _LOCAL_SERVER




def start_dedicated_ipc_server(default_session):
    """Own a fresh IPC endpoint for an already authenticated Daedalus session.

    Never reuse an existing in-process or external IPC owner. In particular,
    a cookie-only worker must not attach its newly restored session to someone
    else's running IkaBot or replace that worker's descriptor.
    """
    global _LOCAL_SERVER
    if default_session is None or getattr(default_session, "logged", False) is not True:
        raise ValueError("A verified authenticated session is required")
    with _LOCAL_SERVER_LOCK:
        if _LOCAL_SERVER is not None:
            raise RuntimeError("An IkaBot IPC owner is already running in this process")
        with _StartupLock() as startup_lock:
            if not startup_lock.acquired:
                raise RuntimeError("Cannot acquire the exclusive IkaBot startup lock")
            if ping_ipc_server():
                raise RuntimeError("Another IkaBot IPC owner is already running")
            server = IPCServer(default_session=default_session)
            try:
                server.start()
            except BaseException:
                server.stop()
                raise
            _LOCAL_SERVER = server
            return server


def stop_ipc_server():
    """Stop this process's IPC server if one was started."""
    global _LOCAL_SERVER
    with _LOCAL_SERVER_LOCK:
        if _LOCAL_SERVER is not None:
            _LOCAL_SERVER.stop()
            _LOCAL_SERVER = None


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def build_cli_parser():
    parser = _JsonArgumentParser(
        prog="ikabot",
        description="Start ikabot background tasks via CLI / IPC.",
    )
    parser.add_argument("--email", default=None, help="Saved account email address")
    parser.add_argument(
        "--world",
        default=None,
        help="Target world (e.g. s301, 301, s301-en, or world name)",
    )
    parser.add_argument(
        "--server",
        default=None,
        help="Optional server language disambiguator (e.g. en, de)",
    )
    parser.add_argument(
        "--player",
        default=None,
        help="In-game player name, needed when the lobby has several accounts on the same world",
    )
    parser.add_argument(
        "--task", default=None, help="Name of the @task module (e.g. alertAttacks)"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="JSON config dict for the task (or @path/to/config.json)",
    )
    parser.add_argument(
        "--batch",
        default=None,
        help='JSON list of tasks to start, e.g. [{"task": "alertAttacks", "config": {"minutes": 20}}] '
        "(or @path/to/tasks.json). Entries may set email/world/server/player; "
        "those flags, when given on the command line, override them for every entry.",
    )
    parser.add_argument(
        "--cities",
        action="store_true",
        help="List the account's cities (id, name, island coordinates, trade good) instead of starting a task",
    )
    return parser


def _check_task_or_batch(parser, args):
    if args.cities:
        if args.task is not None or args.config is not None or args.batch is not None:
            parser.error("--cities cannot be combined with --task, --config or --batch.")
    elif args.batch is not None:
        if args.task is not None or args.config is not None:
            parser.error("--batch cannot be combined with --task or --config.")
    elif not args.task:
        parser.error("one of the arguments --task, --batch or --cities is required")


def parse_cli_args(argv, raw_cmdline=None):
    parser = build_cli_parser()
    args, extras = parser.parse_known_args(argv)
    _check_task_or_batch(parser, args)
    if not extras:
        return args, parse_config_arg(args.config, raw_cmdline=raw_cmdline)

    if not any(e.startswith("-") for e in extras):
        try:
            recovered = _extract_windows_raw_config(raw_cmdline=raw_cmdline)
            if isinstance(recovered, dict):
                return args, recovered
        except Exception:
            pass

    parser.error(f"unrecognized arguments: {' '.join(extras)}")


def _dispatch_request(request, local_server):
    """Send one request to the running IPC server, or handle it in this process.
    Returns (response, local_server); local_server is set once this process owns the IPC server.
    """
    if local_server is not None:
        return local_server.handle_request(request), local_server
    response = send_ipc_request(request)
    if response is not None:
        return response, None
    # Existing server exited right after ping; claim IPC server locally
    with _StartupLock():
        if not ping_ipc_server():
            local_server = IPCServer().start()
    if local_server is not None:
        return local_server.handle_request(request), local_server
    response = send_ipc_request(request) or {
        "status": "error",
        "error": "Failed to communicate with running ikabot IPC server.",
    }
    return response, None


def run_cli_task(argv):
    """Entry point for CLI task queries (`ikabot --email=... --world=... --task=... --config=...`
    or `ikabot --batch=@tasks.json`)."""
    # the JSON answer is read by scripts: write UTF-8 even when stdout is a pipe,
    # where Windows would use the ANSI code page and break accented names
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if "-h" in argv or "--help" in argv:
        parser = build_cli_parser()
        parser.print_help()
        return

    try:
        args, config_dict = parse_cli_args(argv)
        account_flags = {
            "email": args.email,
            "world": args.world,
            "server": args.server,
            "player": args.player,
        }
        if args.cities:
            requests = [dict(account_flags, action="list_cities")]
        elif args.batch is not None:
            requests = parse_batch_arg(args.batch, overrides=account_flags)
        else:
            requests = [
                dict(account_flags, action="start_task", task=args.task, config=config_dict)
            ]
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), flush=True)
        sys.exit(1)

    os.chdir(get_home_dir())
    init_storage()

    local_server = None
    with _StartupLock():
        if not ping_ipc_server():
            local_server = IPCServer().start()

    responses = []
    for request in requests:
        response, local_server = _dispatch_request(request, local_server)
        responses.append(response)

    output = responses if args.batch is not None else responses[0]
    print(json.dumps(output, ensure_ascii=False), flush=True)
    all_ok = all(r.get("status") == "ok" for r in responses)

    if local_server is not None:
        local_server.stop()
        # let requests from other CLI calls that reached us finish
        while local_server.has_active_requests:
            time.sleep(0.2)

    # Like the menu's exit, return the shell and leave the tasks running in the
    # background. os._exit skips multiprocessing's atexit hook, which would wait for them.
    os._exit(0 if all_ok else 1)
