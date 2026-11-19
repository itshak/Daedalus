"""Explicit, locally owned SSH tunnel for the native remote controller.

No shell execution, passwords, bearer tokens or Gameforge session data enter
SSH arguments. Requires a trusted SSH host key and an available local SSH key.
The backend remains bound to its server-side 127.0.0.1 address.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path

_SSH_DESTINATION = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_.-]{0,63}@)?[A-Za-z0-9][A-Za-z0-9._-]{0,252}\Z"
)


class SSHConnectionUnavailable(RuntimeError):
    """Safe SSH failure text; never includes shell stderr or secrets."""


def validate_ssh_destination(value: str) -> str:
    if not isinstance(value, str) or not _SSH_DESTINATION.fullmatch(value):
        raise ValueError("Enter a trusted SSH host or user@host from your Mac SSH configuration")
    return value


def _settings_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config").expanduser()
    return root / "daedalus" / "ssh-host.json"


def load_ssh_destination() -> str | None:
    path = _settings_path()
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise SSHConnectionUnavailable("Unsafe saved SSH host preferences")
    try:
        info = path.stat()
        if info.st_size > 1024 or (os.name != "nt" and info.st_mode & 0o077):
            raise ValueError("Unsafe SSH host settings")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"version", "destination"} or data["version"] != 1:
            raise ValueError("Unexpected SSH host settings")
        return validate_ssh_destination(data["destination"])
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise SSHConnectionUnavailable("Saved SSH host preferences are invalid") from exc


def save_ssh_destination(destination: str) -> None:
    destination = validate_ssh_destination(destination)
    path = _settings_path()
    if path.is_symlink() or path.parent.is_symlink():
        raise SSHConnectionUnavailable("Unsafe SSH host preference path")
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.is_symlink():
            raise SSHConnectionUnavailable("Unsafe SSH host preference directory")
        if os.name != "nt":
            os.chmod(path.parent, 0o700)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".ssh-host-")
        try:
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "destination": destination}, handle)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    except OSError as exc:
        raise SSHConnectionUnavailable("Could not save SSH host preferences") from exc


def forget_ssh_destination() -> None:
    path = _settings_path()
    if path.is_symlink() or path.parent.is_symlink():
        raise SSHConnectionUnavailable("Unsafe SSH host preference path")
    try:
        if path.exists():
            path.unlink()
    except OSError as exc:
        raise SSHConnectionUnavailable("Could not clear SSH host preferences") from exc


class LocalSSHTunnel:
    def __init__(self, destination: str, *, server_port: int = 8765) -> None:
        self.destination = validate_ssh_destination(destination)
        if type(server_port) is not int or not 1 <= server_port <= 65535:
            raise ValueError("Invalid backend port")
        self.server_port = server_port
        self._process: subprocess.Popen | None = None
        self.local_port: int | None = None

    @property
    def url(self) -> str:
        if self.local_port is None or self._process is None:
            raise SSHConnectionUnavailable("SSH connection is not established")
        return f"http://127.0.0.1:{self.local_port}"

    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> str:
        if self._process is not None:
            raise SSHConnectionUnavailable("SSH tunnel was already started")
        # Reserve a loopback-only ephemeral port, closing the temporary socket
        # before SSH takes ownership. ExitOnForwardFailure fails closed on races.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            args = [
                "ssh", "-N", "-T", "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=yes",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "ConnectTimeout=8", "-o", "ControlMaster=no",
                "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=2",
                "-L", f"127.0.0.1:{port}:127.0.0.1:{self.server_port}",
                self.destination,
            ]
            self._process = subprocess.Popen(
                args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
            self.local_port = port
            for _ in range(70):
                if not self.running():
                    raise SSHConnectionUnavailable(
                        "SSH connection failed. Check your SSH host, saved key and trusted host key."
                    )
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        return self.url
                except OSError:
                    time.sleep(0.15)
            raise SSHConnectionUnavailable("SSH forwarding did not become ready")
        except (OSError, SSHConnectionUnavailable) as exc:
            self.close()
            if isinstance(exc, SSHConnectionUnavailable):
                raise
            raise SSHConnectionUnavailable("Could not start a trusted SSH connection") from exc

    def close(self) -> None:
        process, self._process = self._process, None
        self.local_port = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
