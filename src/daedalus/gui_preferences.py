"""Local-only native GUI choices; no passwords, bearer tokens or cookies.

The active backend owns authentication and task dispatch. This versioned private
file stores display options and *excluded* report accounts per backend identity.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from daedalus.client import _validated_url

_ACCOUNT_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
_SCOPE = re.compile(r"[0-9a-f]{64}\Z")
_THEMES = {"auto", "light", "dark"}


class GuiPreferenceError(RuntimeError):
    """Nonsecret, safe-to-display local settings error."""


@dataclass
class GuiPreferences:
    theme: str = "auto"
    only_220k: bool = False
    group_by_island: bool = False
    excluded_by_backend: dict[str, list[str]] = field(default_factory=dict)

    def excluded_for(self, server_url: str) -> set[str]:
        return set(self.excluded_by_backend.get(backend_scope(server_url), []))

    def set_excluded(self, server_url: str, excluded: set[str]) -> None:
        if len(excluded) > 100 or any(not _ACCOUNT_ID.fullmatch(x) for x in excluded):
            raise GuiPreferenceError("Invalid report account selection")
        scope = backend_scope(server_url)
        if scope not in self.excluded_by_backend and len(self.excluded_by_backend) >= 16:
            # No unbounded accumulation of backend metadata.
            self.excluded_by_backend.pop(next(iter(self.excluded_by_backend)))
        self.excluded_by_backend[scope] = sorted(excluded)


def backend_scope(server_url: str) -> str:
    """Hash only a validated stable endpoint identity, never a bearer token.

    An SSH tunnel uses an ephemeral port and therefore cannot be scoped by its
    loopback URL; prefer the authenticated SSH host alias. Do not persist the
    raw SSH target or leak it into reports, only its opaque SHA-256 digest.
    """
    if server_url.startswith("ssh://"):
        destination = server_url[len("ssh://"):]
        if not re.fullmatch(
            r"(?:[A-Za-z_][A-Za-z0-9_.-]{0,63}@)?[A-Za-z0-9][A-Za-z0-9._-]{0,252}\Z",
            destination,
        ):
            raise ValueError("Invalid SSH backend identity")
        normalized = "ssh://" + destination.casefold()
    else:
        normalized = _validated_url(server_url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def default_gui_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config").expanduser()
    return root / "daedalus" / "gui.json"


def _resolve(path: str | Path | None) -> Path:
    return Path(path).expanduser() if path is not None else default_gui_path()


def _validate(data: object) -> GuiPreferences:
    if not isinstance(data, dict) or set(data) != {
        "version", "theme", "only_220k", "group_by_island", "excluded_by_backend"
    } or type(data["version"]) is not int or data["version"] != 1:
        raise GuiPreferenceError("Invalid GUI preference format")
    if data["theme"] not in _THEMES:
        raise GuiPreferenceError("Invalid appearance preference")
    if type(data["only_220k"]) is not bool or type(data["group_by_island"]) is not bool:
        raise GuiPreferenceError("Invalid report preference")
    scopes = data["excluded_by_backend"]
    if not isinstance(scopes, dict) or len(scopes) > 16:
        raise GuiPreferenceError("Invalid report account selections")
    for scope, values in scopes.items():
        if (
            not isinstance(scope, str) or not _SCOPE.fullmatch(scope)
            or not isinstance(values, list) or len(values) > 100
            or any(not isinstance(v, str) or not _ACCOUNT_ID.fullmatch(v) for v in values)
            or len(values) != len(set(values))
        ):
            raise GuiPreferenceError("Invalid report account selections")
    return GuiPreferences(
        theme=data["theme"],
        only_220k=data["only_220k"],
        group_by_island=data["group_by_island"],
        excluded_by_backend={key: list(values) for key, values in scopes.items()},
    )


def load_gui_preferences(path: str | Path | None = None) -> GuiPreferences:
    target = _resolve(path)
    if not target.exists() and not target.is_symlink():
        return GuiPreferences()
    if target.is_symlink() or target.parent.is_symlink() or not target.is_file():
        raise GuiPreferenceError("Unsafe GUI preference file")
    try:
        info = target.stat()
        if os.name != "nt" and info.st_mode & 0o077:
            raise GuiPreferenceError("GUI preference file must be owner-only")
        if info.st_size > 16384:
            raise GuiPreferenceError("GUI preference file is oversized")
        return _validate(json.loads(target.read_text(encoding="utf-8")))
    except GuiPreferenceError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise GuiPreferenceError("Stored GUI preferences are invalid") from exc


def save_gui_preferences(prefs: GuiPreferences, path: str | Path | None = None) -> None:
    target = _resolve(path)
    parent = target.parent
    # Validate before attempting to touch existing settings.
    document = {
        "version": 1,
        "theme": prefs.theme,
        "only_220k": prefs.only_220k,
        "group_by_island": prefs.group_by_island,
        "excluded_by_backend": prefs.excluded_by_backend,
    }
    _validate(document)
    if parent.is_symlink() or target.is_symlink():
        raise GuiPreferenceError("GUI preference path must not use symlinks")
    try:
        parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if parent.is_symlink() or not parent.is_dir():
            raise GuiPreferenceError("Unsafe GUI preference folder")
        if os.name != "nt":
            os.chmod(parent, 0o700)
        handle, temporary = tempfile.mkstemp(prefix=".gui-", suffix=".json", dir=parent)
        try:
            if os.name != "nt":
                os.fchmod(handle, 0o600)
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump(document, out, sort_keys=True)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    except GuiPreferenceError:
        raise
    except OSError as exc:
        raise GuiPreferenceError("Unable to save GUI preferences") from exc
