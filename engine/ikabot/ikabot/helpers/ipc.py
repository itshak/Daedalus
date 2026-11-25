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
# Match the original author's private IkaBot warehouse GUI tradegood mapping.
# Ikariam reports 1=wine, 2=marble, 3=crystal, 4=sulfur, 5=wood.
_ISLAND_RESOURCE_BY_TRADEGOOD = {
    "1": "wine", "2": "marble", "3": "glass", "4": "sulfur", "5": "wood",
}
_MAX_IPC_MSG_BYTES = 16 * 1024 * 1024


def _existing_city_id(value):
    """Normalize upstream JSON city-map keys at the IPC security boundary.

    Ikariam's relatedCityData object uses decimal STRING keys, whereas the
    typed Daedalus protocol requires a positive integer. Reject malformed
    keys instead of coercing arbitrary values, and leave legacy CLI values
    unchanged so upstream tasks retain their original city-map indexing.
    """
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,11}", value):
        return int(value)
    raise ValueError("Invalid authenticated city ID")
_TASK_STARTUP_TIMEOUT = 60.0
_LOCAL_SERVER = None
_LOCAL_SERVER_LOCK = threading.Lock()


def get_ipc_file_path():
    """Default IPC or a supervisor-confined, account-scoped descriptor.

    The env override is valid ONLY for a 64-character identity digest within
    this user's private Daedalus account IPC directory. Existing CLI behavior
    never changes without the explicit override.
    """
    selected = os.environ.get("DAEDALUS_ACCOUNT_IPC_FILE")
    if selected:
        import pathlib
        root = pathlib.Path.home() / ".local" / "state" / "daedalus" / "account-ipc"
        candidate = pathlib.Path(selected)
        if (
            not candidate.is_absolute() or candidate.parent != root
            or not re.fullmatch(r"[0-9a-f]{64}\.json", candidate.name)
            or root.is_symlink() or candidate.is_symlink()
        ):
            raise ValueError("Invalid account-scoped IPC descriptor path")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(root, 0o700)
        return str(candidate)
    return os.path.join(get_ikabot_dir(), "ipc.json")


def get_ipc_lock_path():
    """Use a separate startup lock per isolated account worker."""
    selected = os.environ.get("DAEDALUS_ACCOUNT_IPC_FILE")
    if selected:
        return str(get_ipc_file_path()[:-5] + ".lock")
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

        from ikabot.helpers.serverIdentity import attest_player_from_world_html

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
            return {
                "status": "ok", **identity, "session_valid": False,
                "player_attested": False,
            }
        try:
            # Never follow world-host redirects into lobby URLs with session
            # cookies. SSL validation cannot be disabled for this attestation.
            response = session.s.get(
                base_url, timeout=8, verify=True, allow_redirects=False,
            )
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
            attested = (
                bool(valid)
                and attest_player_from_world_html(text, str(session.username))
            )
        except (OSError, ValueError, TypeError, AttributeError):
            valid = False
            attested = False
        return {
            "status": "ok", **identity,
            "session_valid": bool(valid and attested),
            "player_attested": bool(attested),
        }

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
                if action == "preview_shipments_existing":
                    from ikabot.function.sendResources import preview_native_shipments
                    session = self._existing_session(request)
                    plan = preview_native_shipments(session, request.get("routes"), request.get("useFreighters"))
                    return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                            "username": session.username, "plan": plan}
                if action == "island_destinations_existing":
                    from ikabot.function.sendResources import native_island_destinations
                    session = self._existing_session(request)
                    result = native_island_destinations(session, request.get("x"), request.get("y"))
                    return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                            "username": session.username, **result}
                if action == "list_buildings_existing":
                    return self._list_buildings_existing(request)
                if action == "preview_vacation_existing":
                    return self._preview_vacation_existing(request)
                if action == "list_attack_units_existing":
                    return self._attack_units_existing(request)
                if action == "preview_attack_existing":
                    return self._preview_attack_existing(request)
                if action == "preview_grind_existing":
                    return self._preview_grind_existing(request)
                if action == "preview_station_existing":
                    return self._preview_station_existing(request)
                if action == "list_build_options_existing":
                    return self._build_options_existing(request)
                if action == "preview_build_existing":
                    return self._preview_build_existing(request)
                if action == "preview_layout_existing":
                    return self._preview_layout_existing(request)
                if action == "preview_workers_existing":
                    return self._preview_workers_existing(request)
                if action == "preview_donation_existing":
                    return self._preview_donation_existing(request)
                if action == "preview_construction_existing":
                    return self._preview_construction_existing(request)
                if action == "list_workshop_upgrades_existing":
                    return self._list_workshop_upgrades_existing(request)
                if action == "list_trainables_existing":
                    return self._list_trainables_existing(request)
                if action == "market_quotes_existing":
                    return self._market_quotes_existing(request)
                if action == "list_academies_existing":
                    return self._list_academies_existing(request)
                if action == "list_taverns_existing":
                    return self._list_taverns_existing(request)
                if action == "list_miracles_existing":
                    return self._list_miracles_existing(request)
                if action in {"notification_settings_begin_existing", "notification_settings_complete_existing"}:
                    # These narrow encrypted operations must not log exception
                    # traces or provider responses, even on a persistence error.
                    try:
                        from ikabot.helpers import nativeNotificationSettings

                        session = self._existing_session(request)
                        account, provider = request.get("account_id"), request.get("provider")
                        if action == "notification_settings_begin_existing":
                            if request.get("confirmed_global") is not True:
                                raise ValueError("Explicit worker-global consent required")
                            result = nativeNotificationSettings.begin(session, account, provider)
                        else:
                            result = nativeNotificationSettings.complete(session, account, provider, request.get("envelope"))
                        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                                "username": session.username, "result": result}
                    except Exception:
                        return {"status": "error", "error": "Provider configuration unavailable or outcome uncertain"}
                if action in {"proxy_profiles_existing", "configure_proxy_profile_existing"}:
                    try:
                        from ikabot.helpers import nativeProxyProfiles

                        session = self._existing_session(request)
                        world, player = self._task_entry(request)
                        busy = any(entry["world"].casefold() == world
                                   and entry["player"].casefold() == player
                                   and entry["process"].is_alive()
                                   for entry in self._daedalus_tasks.values())
                        result = (nativeProxyProfiles.status(session) if action == "proxy_profiles_existing"
                                  else nativeProxyProfiles.configure(session, request.get("draft"), managed_busy=busy))
                        result["busy"] = result["busy"] or busy
                        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                                "username": session.username, "result": result}
                    except Exception:
                        return {"status": "error", "error": "Approved network profile unavailable or outcome uncertain"}
                if action in {"extension_status_existing", "extension_registration_existing"}:
                    try:
                        from ikabot.helpers import nativeExtensions

                        session = self._existing_session(request)
                        result = (nativeExtensions.status(session) if action == "extension_status_existing"
                                  else nativeExtensions.set_registration(session, request.get("draft")))
                        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                                "username": session.username, "result": result}
                    except Exception:
                        return {"status": "error", "error": "Protected extension registration unavailable"}
                if action in {"challenge_policy_existing", "set_challenge_policy_existing"}:
                    try:
                        from ikabot.helpers import nativeChallengePolicy

                        session = self._existing_session(request)
                        result = (nativeChallengePolicy.status(session) if action == "challenge_policy_existing"
                                  else nativeChallengePolicy.configure(session, request.get("draft")))
                        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                                "username": session.username, "result": result}
                    except Exception:
                        return {"status": "error", "error": "Human challenge policy unavailable"}
                if action in {"world_reports_existing", "world_report_page_existing"}:
                    try:
                        from ikabot.helpers import nativeWorldReports

                        session = self._existing_session(request)
                        result = ({"reports": nativeWorldReports.list_reports(session)}
                                  if action == "world_reports_existing" else
                                  nativeWorldReports.read_report(session, request.get("report_id"), request.get("offset")))
                        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                                "username": session.username, "result": result}
                    except Exception:
                        return {"status": "error", "error": "Aggregate world reports unavailable"}
                if action == "administrative_status_existing":
                    from ikabot.helpers.nativeAdminStatus import administrative_status

                    session = self._existing_session(request)
                    return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                            "username": session.username, "settings": administrative_status(session)}
                if action == "shrine_status_existing":
                    return self._shrine_status_existing(request)
                if action == "list_pirate_fortresses_existing":
                    return self._list_pirate_fortresses_existing(request)
                if action == "military_overview_existing":
                    return self._military_overview_existing(request)
                if action == "ship_movements_existing":
                    return self._ship_movements_existing(request)
                if action == "warehouse_snapshots_existing":
                    return self._warehouse_snapshots_existing(request)
                if action == "task_preflight_existing":
                    return self._task_preflight_existing(request)
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
                    "id": _existing_city_id(city_id) if existing_only else city_id,
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

    def _list_buildings_existing(self, request):
        """Read only one owned city's building slots from an existing session.

        All upstream game HTML is parsed and discarded within IkaBot. This
        action never prepares or starts an upgrade, alters worker production,
        or restores a session. The request city must belong to this player.
        """
        from ikabot.config import city_url
        from ikabot.helpers.getJson import getCity
        from ikabot.helpers.pedirInfo import getIdsOfCities

        session = self._existing_session(request)
        city_id = request.get("city_id")
        if type(city_id) is not int or not 0 < city_id < 10**12:
            raise ValueError("Invalid building inventory city")
        ids, _cities = getIdsOfCities(session)
        if city_id not in {_existing_city_id(value) for value in ids}:
            raise ValueError("Building inventory city is not owned by this session")
        html = session.get(city_url + str(city_id))
        city = getCity(html)
        if _existing_city_id(city.get("id")) != city_id:
            raise ValueError("The game returned a different city")
        buildings = []
        for item in city.get("position", []):
            if not isinstance(item, dict) or item.get("building") == "empty":
                continue
            slot, level = item.get("position"), item.get("level")
            if (type(slot) is not int or not 0 <= slot <= 80
                    or type(level) is not int or not 0 <= level <= 150):
                raise ValueError("Invalid building position or level")
            title = item.get("name")
            if not isinstance(title, str) or not title.strip():
                raise ValueError("Invalid building name")
            buildings.append({
                "position": slot,
                "building": str(item.get("building") or "")[:64],
                "name": title[:100],
                "level": level,
                "busy": item.get("isBusy") is True,
                "can_upgrade": item.get("isMaxLevel") is not True,
                "can_upgrade_now": item.get("canUpgrade") is True,
            })
        if len(buildings) > 80 or len({item["position"] for item in buildings}) != len(buildings):
            raise ValueError("Invalid building inventory")
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "city_id": city_id,
            "buildings": buildings,
        }

    def _preview_vacation_existing(self, request):
        from ikabot.function.vacationMode import preview_native_vacation

        session = self._existing_session(request)
        plan = preview_native_vacation(session, request.get("city_id"))
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "plan": plan}

    def _attack_units_existing(self, request):
        from ikabot.function.attackBarbarians import native_attack_inventory

        session = self._existing_session(request)
        inventory = native_attack_inventory(session, request.get("city_id"))
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "inventory": inventory}

    def _preview_attack_existing(self, request):
        from ikabot.function.attackBarbarians import preview_native_attack

        session = self._existing_session(request)
        plan = preview_native_attack(session, request.get("city_id"), request.get("target_city_id"),
                                     request.get("waves"))
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "plan": plan}

    def _preview_grind_existing(self, request):
        from ikabot.function.autoBarbarians import preview_native_grind

        session = self._existing_session(request)
        plan = preview_native_grind(session, request.get("city_id"), request.get("target_city_id"),
                                    request.get("send_notifications"))
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "plan": plan}

    def _preview_station_existing(self, request):
        from ikabot.function.stationArmy import preview_native_station

        session = self._existing_session(request)
        plan = preview_native_station(session, request.get("city_id"),
                                      request.get("destination_city_id"), request.get("ground"),
                                      request.get("all_origins", False), request.get("both", False))
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "plan": plan}

    def _build_options_existing(self, request):
        from ikabot.function.constructBuilding import native_build_options

        session = self._existing_session(request)
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "inventory": native_build_options(session, request.get("city_id"))}

    def _preview_build_existing(self, request):
        from ikabot.function.constructBuilding import preview_native_build

        session = self._existing_session(request)
        plan = preview_native_build(session, request.get("city_id"), request.get("position"), request.get("building_id"))
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "plan": plan}

    def _preview_layout_existing(self, request):
        from ikabot.function.reorganizeCityBuildings import preview_native_layout

        session = self._existing_session(request)
        plan = preview_native_layout(session, request.get("city_id"), request.get("template_city_id"))
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "plan": plan}

    def _preview_workers_existing(self, request):
        from ikabot.function.modifyProduction import preview_native_workers

        session = self._existing_session(request)
        plan = preview_native_workers(session, request.get("task"), request.get("city_id"),
                                      request.get("percentage"), request.get("project"),
                                      request.get("overcharge", False), request.get("additional_city_ids"))
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "plan": plan}

    def _preview_donation_existing(self, request):
        from ikabot.function.donate import preview_native_donation

        session = self._existing_session(request)
        plan = preview_native_donation(
            session, request.get("city_id"), request.get("project"), request.get("amount"),
        )
        return {"status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "plan": plan}

    def _preview_construction_existing(self, request):
        """Read-only construction cost/queue preparation for a verified owned city.

        Only sanitized game-calculated quantities and a bounded exact task
        config leave the existing session; never HTML or login/session state.
        """
        from ikabot.function.constructionList import preview_native_construction

        session = self._existing_session(request)
        city_id = request.get("city_id")
        upgrades = request.get("upgrades")
        if (type(city_id) is not int or not 0 < city_id < 10**12
                or not isinstance(upgrades, list) or not 0 < len(upgrades) <= 12):
            raise ValueError("Invalid construction preview request")
        reviewed = []
        for item in upgrades:
            if (not isinstance(item, dict)
                    or type(item.get("position")) is not int
                    or type(item.get("target_level")) is not int
                    or not 0 <= item["position"] <= 80
                    or not 1 <= item["target_level"] <= 150):
                raise ValueError("Invalid building preview target")
            reviewed.append({
                "position": item["position"], "target_level": item["target_level"]
            })
        result = (preview_native_construction(session, city_id, reviewed, request["supply"])
                  if "supply" in request else preview_native_construction(session, city_id, reviewed))
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "city_id": city_id,
            "plan": result,
        }

    def _list_workshop_upgrades_existing(self, request):
        """Enumerate real workshop unit levels without starting upgrades."""
        from ikabot.function.UpgradeUnits import find_workshop, workshop_upgrades
        from ikabot.helpers.pedirInfo import getIdsOfCities

        session = self._existing_session(request)
        city_id = request.get("city_id")
        if type(city_id) is not int or not 0 < city_id < 10**12:
            raise ValueError("Invalid workshop city")
        ids, _cities = getIdsOfCities(session)
        if city_id not in {_existing_city_id(value) for value in ids}:
            raise ValueError("Workshop city is not owned by the selected account")
        city, workshop = find_workshop(session, str(city_id))
        if _existing_city_id(city.get("id")) != city_id:
            raise ValueError("Game returned a different workshop city")
        if workshop is None:
            return {
                "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
                "username": session.username, "city_id": city_id,
                "workshop_level": 0, "upgrades": [],
            }
        maximum = min(25, int(workshop.get("level") or 0))
        if not 0 <= maximum <= 25:
            raise ValueError("Invalid workshop level")
        available = workshop_upgrades(session, str(city_id), workshop["position"])
        if not isinstance(available, dict) or len(available) > 100:
            raise ValueError("Unbounded workshop upgrade inventory")
        upgrades = []
        for unit_id, unit in available.items():
            if (not isinstance(unit_id, str) or not unit_id.isdigit()
                    or not isinstance(unit, dict)):
                raise ValueError("Invalid workshop unit")
            name = str(unit.get("name") or "")[:100]
            if not name:
                raise ValueError("Missing workshop unit name")
            types = unit.get("types")
            if not isinstance(types, dict) or len(types) > 5:
                raise ValueError("Invalid workshop upgrade types")
            for upgrade_type, state in types.items():
                if (not isinstance(upgrade_type, str)
                        or not re.fullmatch(r"[a-zA-Z_]{1,40}", upgrade_type)
                        or not isinstance(state, dict)):
                    raise ValueError("Invalid unit upgrade")
                level = state.get("level")
                if type(level) is not int or not 0 <= level <= 25:
                    raise ValueError("Invalid current unit upgrade level")
                upgrades.append({
                    "unit_id": unit_id, "name": name,
                    "upgrade_type": upgrade_type,
                    "description": str(state.get("desc") or upgrade_type)[:100],
                    "current_level": level,
                    "max_level": maximum,
                })
        if len(upgrades) > 250:
            raise ValueError("Unbounded workshop upgrade choices")
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "city_id": city_id,
            "workshop_level": maximum, "upgrades": upgrades,
        }

    def _list_trainables_existing(self, request):
        """Inspect actual barracks/shipyard unit costs without recruiting."""
        from ikabot.function.trainArmy import available_trainable_units

        session = self._existing_session(request)
        city_id = request.get("city_id")
        train_troops = request.get("train_troops")
        if (type(city_id) is not int or not 0 < city_id < 10**12
                or type(train_troops) is not bool):
            raise ValueError("Choose a valid training city and troop/ship mode")
        snapshot = available_trainable_units(session, city_id, train_troops)
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "city_id": city_id,
            **snapshot,
        }

    def _market_quotes_existing(self, request):
        """Read-only buy/sell offer and price discovery from a verified game market."""
        from ikabot.function.nativeMarket import market_snapshot

        session = self._existing_session(request)
        city_id = request.get("city_id")
        resource_type = request.get("resource_type")
        side = request.get("market_side")
        if (type(city_id) is not int or not 0 < city_id < 10**12
                or type(resource_type) is not int or not 0 <= resource_type <= 4
                or side not in {"buy", "sell_to_offers", "create_offer"}):
            raise ValueError("Invalid market quote scope")
        snapshot = market_snapshot(session, city_id, resource_type, side)
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "city_id": city_id, **snapshot,
        }

    def _list_academies_existing(self, request):
        """Return owned academy buildings, real crystal stock and cooldown state."""
        from ikabot.config import actionRequest, city_url
        from ikabot.function.research import find_academy_cities, get_studies, native_study_choices
        from ikabot.helpers.getJson import getCity
        from ikabot.helpers.pedirInfo import getIdsOfCities

        session = self._existing_session(request)
        ids, _cities = getIdsOfCities(session)
        owned_ids = {_existing_city_id(value) for value in ids}
        found = find_academy_cities(session)
        if not isinstance(found, list) or len(found) > 100:
            raise ValueError("Invalid academy list returned by the game")
        academies = []
        seen = set()
        for academy in found:
            if not isinstance(academy, dict):
                raise ValueError("Invalid academy record")
            raw_id = _existing_city_id(academy.get("cityID"))
            position = academy.get("pos")
            if (raw_id not in owned_ids or raw_id in seen
                    or type(position) is not int or not 0 <= position <= 80):
                raise ValueError("Academy does not belong to the selected account")
            seen.add(raw_id)
            city = getCity(session.get(city_url + str(raw_id)))
            if _existing_city_id(city.get("id")) != raw_id:
                raise ValueError("Game returned an unexpected academy city")
            if not any(
                building.get("position") == position
                and building.get("building") == "academy"
                for building in city.get("position", [])
            ):
                raise ValueError("Academy position has changed")
            stock = city.get("availableResources")
            if (not isinstance(stock, list) or len(stock) != 5
                    or any(type(q) is not int or q < 0 for q in stock)):
                raise ValueError("Academy resource amounts unavailable")
            url = (
                f"view=academy&cityId={raw_id}&position={position}"
                f"&backgroundView=city&currentCityId={raw_id}&templateView=academy"
                f"&actionRequest={actionRequest}&ajax=1"
            )
            cooldown_html = session.get(url)
            if not isinstance(cooldown_html, str):
                raise ValueError("Academy cooldown cannot be confirmed")
            academies.append({
                "city_id": raw_id, "city_name": str(city.get("name") or "")[:100],
                "position": position, "crystal": stock[3],
                "cooldown": "experimentCooldown" in cooldown_html,
                "can_experiment_now": (
                    stock[3] >= 300000 and "experimentCooldown" not in cooldown_html
                ),
            })
        studies = None
        try:
            studies = native_study_choices(get_studies(session))
        except (ValueError, KeyError, IndexError, TypeError):
            # Advisor failure does not disable verified experiment controls.
            pass
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "academies": academies, "studies": studies,
        }

    def _list_taverns_existing(self, request):
        """Read-only city wine, tavern servings and population state."""
        from ikabot.config import city_url
        from ikabot.function.tavernManager import TavernManager, native_serving_options
        from ikabot.helpers.getJson import getCity
        from ikabot.helpers.pedirInfo import getIdsOfCities

        session = self._existing_session(request)
        ids, _cities = getIdsOfCities(session)
        if len(ids) > 100:
            raise ValueError("Too many cities to inspect")
        manager = TavernManager(session)
        taverns = []
        for raw in ids:
            city_id = _existing_city_id(raw)
            city = getCity(session.get(city_url + str(city_id)))
            if _existing_city_id(city.get("id")) != city_id:
                raise ValueError("Unexpected city in tavern inspection")
            stock = city.get("availableResources")
            if (not isinstance(stock, list) or len(stock) != 5
                    or any(type(x) is not int or x < 0 for x in stock)):
                raise ValueError("Current wine stock is unavailable")
            tavern = next(
                (row for row in city.get("position", [])
                 if row.get("building") == "tavern"), None
            )
            info = None
            if tavern:
                info = manager._get_tavern_data(city, tavern, force_refresh=True)
            hall = manager._get_town_hall_data(city_id, city)
            current = info.get("current_level") if isinstance(info, dict) else None
            servings = info.get("consumption_values") if isinstance(info, dict) else None
            wine_hour = (
                manager._wine_at_level(servings, current)
                if isinstance(servings, list) and type(current) is int else None
            )
            if wine_hour is not None and (
                type(wine_hour) is not int or wine_hour < 0
            ):
                raise ValueError("Invalid tavern wine consumption")
            taverns.append({
                "city_id": city_id, "city_name": str(city.get("name") or "")[:100],
                "wine": stock[1], "has_tavern": tavern is not None,
                "serving_level": current, "wine_per_hour": wine_hour,
                "serving_options": native_serving_options(info),
                "satisfaction": (
                    hall.get("total_satisfaction") if isinstance(hall, dict) else None
                ),
                "population": (
                    hall.get("current_pop") if isinstance(hall, dict) else None
                ),
                "capacity": (
                    hall.get("max_pop") if isinstance(hall, dict) else None
                ),
            })
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "taverns": taverns,
        }

    def _list_miracles_existing(self, request):
        """Inspect real owned temples, wonder level, cooldown and activation state."""
        from ikabot.function.activateMiracle import obtainMiraclesAvailable
        from ikabot.helpers.pedirInfo import getIdsOfCities

        session = self._existing_session(request)
        owned, _cities = getIdsOfCities(session)
        own = {_existing_city_id(raw) for raw in owned}
        available = obtainMiraclesAvailable(session)
        if not isinstance(available, list) or len(available) > 100:
            raise ValueError("Invalid wonder inventory")
        reviewed = []
        seen = set()
        for miracle in available:
            if not isinstance(miracle, dict):
                raise ValueError("Invalid miracle")
            temple = miracle.get("ciudad")
            if not isinstance(temple, dict):
                raise ValueError("Miracle is not associated with a temple")
            city_id = _existing_city_id(temple.get("id"))
            wonder = str(miracle.get("wonder") or "")
            level = miracle.get("wonderActivationLevel")
            enabled = miracle.get("available")
            pending = miracle.get("available_in") if enabled is False else 0
            if (city_id not in own or wonder not in set("12345678")
                    or wonder in seen or type(level) is not int
                    or not 0 <= level <= 5 or type(enabled) is not bool
                    or type(pending) is not int or pending < 0 or pending > 7 * 86400):
                raise ValueError("Invalid or foreign wonder temple")
            seen.add(wonder)
            reviewed.append({
                "city_id": city_id,
                "temple_city": str(temple.get("name") or "")[:100],
                "island_id": str(miracle.get("id") or "")[:30],
                "wonder": wonder,
                "wonder_name": str(miracle.get("wonderName") or "")[:100],
                "level": level, "available": enabled,
                "available_in_seconds": pending,
            })
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "miracles": reviewed,
        }

    def _shrine_status_existing(self, request):
        """Read only real Olympus shrine location and current favour (if parseable).

        A failed game response is unknown, not zero favour; never claim a
        shrine is ready from an unparsable or unauthorized game payload.
        """
        from ikabot.config import actionRequest
        from ikabot.function.activateShrine import findShrine
        from ikabot.helpers.getJson import getCity
        from ikabot.helpers.pedirInfo import getIdsOfCities

        session = self._existing_session(request)
        city_id, position = findShrine(session)
        if city_id is None or position is None:
            shrine = None
        else:
            owned, _cities = getIdsOfCities(session)
            integer_id = _existing_city_id(city_id)
            if integer_id not in {_existing_city_id(item) for item in owned}:
                raise ValueError("Shrine city is not owned")
            if type(position) is not int or not 0 <= position <= 80:
                raise ValueError("Invalid shrine position")
            city = getCity(session.get(f"view=city&cityId={integer_id}"))
            if _existing_city_id(city.get("id")) != integer_id:
                raise ValueError("Shrine city changed")
            raw = session.get(
                f"view=shrineOfOlympus&cityId={integer_id}&position={position}"
                f"&activeTab=tabOverview&backgroundView=city"
                f"&currentCityId={integer_id}&templateView=shrineOfOlympus"
                f"&actionRequest={actionRequest}&ajax=1",
                noIndex=True,
            )
            favor = None
            try:
                data = json.loads(raw, strict=False)
                parsed = data[2][1]["currentFavor"]
                if type(parsed) is int and 0 <= parsed <= 10**12:
                    favor = parsed
                elif isinstance(parsed, str) and parsed.isdigit():
                    favor = int(parsed)
            except (IndexError, KeyError, TypeError, ValueError):
                pass
            shrine = {
                "city_id": integer_id, "city_name": str(city.get("name") or "")[:100],
                "position": position, "favor": favor,
            }
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "shrine": shrine,
        }

    def _list_pirate_fortresses_existing(self, request):
        """Identify actual account-owned fortresses and supported mission durations."""
        from ikabot.config import piracyMissionToBuildingLevel, piracyMissionWaitingTime
        from ikabot.function.autoPirate import getPiracyCities

        session = self._existing_session(request)
        candidates = getPiracyCities(session, 1)
        if not isinstance(candidates, list) or len(candidates) > 100:
            raise ValueError("Game returned invalid pirate fortress inventory")
        verified = []
        seen = set()
        for city in candidates:
            if not isinstance(city, dict):
                raise ValueError("Invalid pirate city")
            city_id = _existing_city_id(city.get("id"))
            if city_id in seen:
                raise ValueError("Duplicate pirate fortress city")
            seen.add(city_id)
            fortress = next(
                (item for item in city.get("position", [])
                 if item.get("building") == "pirateFortress"), None
            )
            if fortress is None or type(fortress.get("level")) is not int:
                raise ValueError("Pirate fortress level unavailable")
            level = fortress["level"]
            if not 1 <= level <= 100:
                raise ValueError("Invalid pirate fortress level")
            missions = []
            for mission, required_level in piracyMissionToBuildingLevel.items():
                if (type(mission) is not int or not 1 <= mission <= 9
                        or type(required_level) is not int
                        or mission not in piracyMissionWaitingTime):
                    raise ValueError("Unknown IkaBot pirate mission schedule")
                if level >= required_level:
                    duration = piracyMissionWaitingTime[mission]
                    if type(duration) is not int or not 0 < duration <= 86400:
                        raise ValueError("Invalid pirate mission duration")
                    missions.append({"number": mission, "duration_seconds": duration})
            verified.append({
                "city_id": city_id, "city_name": str(city.get("name") or "")[:100],
                "fortress_level": level, "missions": missions,
            })
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "fortresses": verified,
        }

    def _military_overview_existing(self, request):
        """Read-only ground/fleet counts from the owner's existing cityMilitary view.

        Original CLI viewArmy parser is reused, but raw HTML never leaves IPC.
        Neither opening the view nor parsing its data changes the game state.
        """
        from ikabot.function.viewArmy import getCityMilitaryData, parseUnits
        from ikabot.helpers.pedirInfo import getIdsOfCities
        from ikabot.helpers.varios import decodeUnicodeEscape

        session = self._existing_session(request)
        ids, cities = getIdsOfCities(session)
        if not isinstance(ids, (list, tuple)) or len(ids) > 100:
            raise ValueError("Invalid number of military cities")
        results = []
        known = set()
        for raw_id in ids:
            city_id = _existing_city_id(raw_id)
            if city_id in known:
                raise ValueError("Repeated military city")
            known.add(city_id)
            city = cities[raw_id]
            if not isinstance(city, dict):
                raise ValueError("Invalid military city")
            city_name = decodeUnicodeEscape(city.get("name", ""))
            if (not isinstance(city_name, str) or not city_name.strip()
                    or len(city_name) > 120):
                raise ValueError("Invalid military city name")
            ground, fleet = parseUnits(getCityMilitaryData(session, city["id"]))
            def reviewed_units(units):
                if not isinstance(units, dict) or len(units) > 100:
                    raise ValueError("Invalid military inventory")
                rows = []
                for unit_name, amount in units.items():
                    if (not isinstance(unit_name, str) or not unit_name.strip()
                            or len(unit_name) > 100 or type(amount) is not int
                            or not 0 <= amount <= 10**10):
                        raise ValueError("Invalid military unit count")
                    if amount:
                        rows.append({"unit": unit_name, "amount": amount})
                return rows
            results.append({
                "city_id": city_id, "city_name": city_name,
                "troops": reviewed_units(ground), "fleet": reviewed_units(fleet),
            })
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "cities": results,
            "observed_at": int(time.time()),
        }

    def _ship_movements_existing(self, request):
        """Read-only military advisor's existing movement panel, not a send order."""
        from ikabot.helpers.pedirInfo import getIdsOfCities

        session = self._existing_session(request)
        ids, _cities = getIdsOfCities(session)
        if not ids or len(ids) > 100:
            raise ValueError("No verified owned city available for movements")
        city_id = _existing_city_id(ids[0])
        url = (
            "view=militaryAdvisor&oldView=city&oldBackgroundView=city"
            f"&backgroundView=city&currentCityId={city_id}"
            f"&actionRequest={config.actionRequest}&ajax=1"
        )
        raw = json.loads(session.post(url), strict=False)
        movements = raw[1][1][2]["viewScriptParams"]["militaryAndFleetMovements"]
        server_now = int(raw[0][1]["time"])
        if not isinstance(movements, list) or len(movements) > 250:
            raise ValueError("Invalid number of ship movements")
        def title(value):
            if not isinstance(value, str) or len(value) > 120:
                raise ValueError("Invalid movement text")
            return value
        result = []
        for item in movements:
            if not isinstance(item, dict):
                raise ValueError("Invalid ship movement")
            origin = item["origin"]
            destination = item["target"]
            event = item["event"]
            if not all(isinstance(value, dict) for value in (origin, destination, event)):
                raise ValueError("Invalid movement description")
            arrive = int(item["eventTime"])
            if arrive < 0 or arrive > 2**40:
                raise ValueError("Invalid movement arrival")
            soldiers = int(item["army"]["amount"])
            ships = int(item["fleet"]["amount"])
            if any(not 0 <= n <= 10**10 for n in (soldiers, ships)):
                raise ValueError("Invalid movement quantities")
            hostile = item.get("isHostile")
            returning = event.get("isFleetReturning")
            if type(hostile) is not bool or type(returning) is not bool:
                raise ValueError("Invalid movement flags")
            result.append({
                "origin": title(origin.get("name")),
                "destination": title(destination.get("name")),
                "origin_player": title(origin.get("avatarName") or ""),
                "destination_player": title(destination.get("avatarName") or ""),
                "mission": title(event.get("missionText") or ""),
                "seconds_remaining": max(0, arrive - server_now),
                "troops": soldiers, "ships": ships,
                "hostile": hostile, "returning": returning,
            })
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "username": session.username, "movements": result,
            "observed_at": int(time.time()),
        }

    def _warehouse_snapshots_existing(self, request):
        """Read numeric-only plunderable values from a real owned warehouse.

        The authenticated city view supplies the warehouse *building position*.
        Current Ikariam refuses a position-free warehouse view and renders
        resource values in a JavaScript JSON update map instead of direct
        span nodes. Support both verified formats, never whole page HTML or
        arbitrary markup as an amount, and never expose login/session tokens.
        """
        import html
        from html.parser import HTMLParser

        from ikabot.helpers import pedirInfo
        from ikabot.helpers.varios import decodeUnicodeEscape

        class _WarehouseSlots(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.positions = set()
                self.invalid = False

            def handle_starttag(self, tag, attrs):
                if tag != "div":
                    return
                classes = set((dict(attrs).get("class") or "").split())
                if not {"building", "warehouse"}.issubset(classes):
                    return
                slots = [
                    re.fullmatch(r"position([0-9]{1,2})", name)
                    for name in classes
                ]
                slots = [item for item in slots if item is not None]
                if len(slots) != 1:
                    self.invalid = True
                else:
                    self.positions.add(int(slots[0].group(1)))

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
        # Numeric JSON updater values are delivered in the current game's
        # authenticated warehouse markup as text + exact tooltip strings.
        update_pattern = re.compile(
            r'"js_(plunderable|capacity)_(wood|wine|marble|crystal|glass|sulfur)"\s*:\s*(\{)',
            re.IGNORECASE,
        )
        safe_number = re.compile(r"[0-9][0-9,.\s\u00a0\u202f]*[KMBkmb]?\Z")
        results = []
        for raw_city_id in ids:
            city_id = _existing_city_id(raw_city_id)
            city_html = session.get(f"view=city&cityId={city_id}", noIndex=True)
            if not isinstance(city_html, str) or len(city_html) > 2_000_000:
                raise ValueError("Invalid authenticated city building view")
            slots = _WarehouseSlots()
            slots.feed(city_html)
            slots.close()
            if slots.invalid or not slots.positions:
                raise ValueError("No trusted warehouse building slot in city view")
            position = min(slots.positions)
            markup = session.get(
                f"view=warehouse&cityId={city_id}&position={position}", noIndex=True,
            )
            if not isinstance(markup, str) or len(markup) > 2_000_000:
                raise ValueError("Invalid authenticated warehouse response")
            fields = {}

            def record(kind, resource, amount):
                key = (kind.casefold(), "glass" if resource.casefold() == "crystal"
                       else resource.casefold())
                if not isinstance(amount, str) or not safe_number.fullmatch(amount):
                    raise ValueError("Warehouse amount is not numeric")
                prior = fields.get(key)
                if prior is not None and prior != amount:
                    raise ValueError("Conflicting warehouse numeric resource values")
                fields[key] = amount

            for kind, resource, inner in span_pattern.findall(markup):
                tooltip = tooltip_pattern.search(inner)
                value = tooltip.group(1) if tooltip is not None else inner
                value = html.unescape(re.sub(r"<[^>]*>", "", value)).strip()
                record(kind, resource, value)
            for match in update_pattern.finditer(markup):
                try:
                    item, _ = json.JSONDecoder().raw_decode(markup[match.start(3):])
                except (ValueError, TypeError) as exc:
                    raise ValueError("Invalid warehouse resource update") from exc
                if not isinstance(item, dict) or set(item) - {"text", "tooltip"}:
                    raise ValueError("Invalid warehouse resource update fields")
                value = item.get("tooltip") if item.get("tooltip") is not None else item.get("text")
                record(match.group(1), match.group(2), value)
            unsecured = {res: amount for (kind, res), amount in fields.items()
                         if kind == "plunderable"}
            capacity_values = [amount for (kind, _), amount in fields.items()
                               if kind == "capacity"]
            if not unsecured:
                raise ValueError("No unsecured warehouse resource values")
            capacity = capacity_values[0] if capacity_values else None
            raw_coords = cities[raw_city_id].get("coords")
            island = None
            if isinstance(raw_coords, str):
                candidate = raw_coords.strip().strip("[]").strip()
                if re.fullmatch(r"[0-9]{1,3}:[0-9]{1,3}", candidate):
                    island = candidate
            results.append({
                "city_id": city_id,
                "city_name": decodeUnicodeEscape(cities[raw_city_id]["name"]),
                "unsecured": unsecured,
                "capacity": capacity,
                "island": island,
                # Legacy "Copy by island" groups by the island-produced good.
                # Read it from the same authenticated city inventory; do not
                # issue a second game request or echo arbitrary raw metadata.
                "island_resource": _ISLAND_RESOURCE_BY_TRADEGOOD.get(
                    str(cities[raw_city_id].get("tradegood")), ""
                ),
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
                **({"outcome": "accepted" if proc.exitcode == 0 else "failed_or_uncertain"}
                   if entry["task"] in {"testTelegramBot", "testDiscordBot"}
                   and entry["status"] == "finished" and proc.exitcode is not None else {}),
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

    def _task_preflight_existing(self, request):
        """Check known nonsecret prerequisites; never create a task or login.

        The result is deliberately *not* a claim that arbitrary game tasks
        are safe or fully configured. Only notification requirements for
        three built-in alerts are checked; all other task-specific validation
        remains authoritative in the engine during actual dispatch.
        """
        session = self._existing_session(request)
        name = request.get("task")
        if not isinstance(name, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]{0,79}", name,
        ):
            raise ValueError("A built-in task name is required for preflight")
        builtin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "function")
        names = {
            fname[:-3].casefold(): fname[:-3]
            for fname in os.listdir(builtin_dir)
            if fname.endswith(".py") and fname != "__init__.py"
        }
        canonical = names.get(name.casefold())
        if canonical is None:
            raise ValueError("Unknown built-in task")
        requires_notifications = canonical in {
            "alertAttacks", "alertLowWine", "searchForIslandSpaces",
            "testTelegramBot", "testDiscordBot",
        }
        if canonical in {"testTelegramBot", "testDiscordBot"}:
            from ikabot.helpers.botComm import native_notification_ready
            ready = native_notification_ready(session, "telegram" if canonical == "testTelegramBot" else "discord")
        elif requires_notifications:
            from ikabot.helpers.botComm import discordDataIsValid, telegramDataIsValid

            ready = bool(
                telegramDataIsValid(session) or discordDataIsValid(session)
            )
        else:
            ready = True
        return {
            "status": "ok", "world": f"s{session.mundo}-{session.servidor}",
            "player": session.username, "task": canonical,
            "ready": ready,
            "reason": "none" if ready else "notifications_required",
            "notifications_required": requires_notifications,
            "checked": ["notifications"] if requires_notifications else [],
        }

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
        if existing_only and canonical_name == "autoPirate":
            # The remote controller never invokes automated challenge solvers,
            # even if a legacy local provider is configured.
            config_dict = {**config_dict, "manual_challenge": True}
        try:
            clean_config = _validate_task_config(canonical_name, task_func, config_dict)
        except (ValueError, TypeError):
            if existing_only:
                # A pure JSON/signature failure before *any* game action or
                # child launch is definitively rejected, not an uncertain start.
                return {"status": "rejected", "reason": "invalid_configuration"}
            raise
        if not existing_only:
            session = self._get_or_create_session(email, world, server, player)
        if existing_only:
            active_same_account = sum(
                entry["world"].casefold() == fingerprint[0]
                and entry["player"].casefold() == fingerprint[1]
                and entry["process"].is_alive()
                for entry in self._daedalus_tasks.values()
            )
            if ((canonical_name == "vacationMode" and active_same_account)
                    or any(entry["world"].casefold() == fingerprint[0]
                           and entry["player"].casefold() == fingerprint[1]
                           and entry["task"] == "vacationMode" and entry["process"].is_alive()
                           for entry in self._daedalus_tasks.values())):
                return {"status": "rejected", "reason": "invalid_configuration"}
            if canonical_name in {"testTelegramBot", "testDiscordBot"} and any(
                    entry["world"].casefold() == fingerprint[0]
                    and entry["player"].casefold() == fingerprint[1]
                    and entry["task"] == canonical_name
                    and (entry["process"].is_alive() or time.time() - entry["started_at"] < 30)
                    for entry in self._daedalus_tasks.values()):
                return {"status": "rejected", "reason": "invalid_configuration"}
            if active_same_account >= 16:
                raise ValueError("Account has reached the active task safety limit")
            if len(self._daedalus_tasks) >= 256:
                raise ValueError("Managed task registry has reached its safety limit")
            if len(self._daedalus_requests) >= 2048:
                raise ValueError("Task receipt cache is full; manual recovery is required")
        if existing_only:
            # Recheck the notification-only prerequisites immediately before
            # prepare. A race between GUI preflight and the dispatch request
            # must not create an ambiguous receipt for this known condition.
            readiness = self._task_preflight_existing(request)
            if not readiness["ready"]:
                return {"status": "rejected", "reason": "notifications_required"}
        prepare = getattr(task_func, "prepare", None)
        if prepare is not None:
            # errors found here go back to the CLI instead of only to the task's log
            try:
                prepared = prepare(session, **clean_config)
            except ValueError:
                if existing_only and canonical_name in {
                    "donate", "modifyProduction", "modifyAcademyWorkers", "modifyTempleWorkers",
                    "reorganizeCityBuildings", "constructBuilding", "stationArmy", "trainArmy", "autoBarbarians", "attackBarbarians", "vacationMode", "sendResources", "testTelegramBot", "testDiscordBot", "research", "tavernManager", "searchForIslandSpaces",
                }:
                    return {"status": "rejected", "reason": "invalid_configuration"}
                raise
            if prepared is not None:
                clean_config = _validate_task_config(canonical_name, task_func, prepared)

        task_id = secrets.token_hex(12) if existing_only else None
        if existing_only and canonical_name == "dumpWorld":
            from ikabot.helpers.nativeWorldReports import ensure_capacity

            if "managed_report_id" in config_dict or any(
                    entry["world"].casefold() == fingerprint[0]
                    and entry["player"].casefold() == fingerprint[1]
                    and entry["task"] == canonical_name and entry["process"].is_alive()
                    for entry in self._daedalus_tasks.values()):
                return {"status": "rejected", "reason": "invalid_configuration"}
            try:
                ensure_capacity(session)
            except (OSError, ValueError):
                return {"status": "rejected", "reason": "invalid_configuration"}
            clean_config["managed_report_id"] = task_id

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
