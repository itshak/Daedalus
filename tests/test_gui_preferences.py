"""Private, nonsecret GUI preferences validated without launching Qt."""

from __future__ import annotations

import json
import os

import pytest

from daedalus.gui_preferences import (
    GuiPreferenceError,
    GuiPreferences,
    backend_scope,
    load_gui_preferences,
    save_gui_preferences,
)


def test_gui_defaults_and_private_round_trip(tmp_path):
    target = tmp_path / "private" / "gui.json"
    assert load_gui_preferences(target) == GuiPreferences()
    prefs = GuiPreferences(theme="dark", only_220k=True, group_by_island=True)
    first = "http://127.0.0.1:8765"
    second = "https://other.example"
    prefs.set_excluded(first, {"alpha", "beta"})
    save_gui_preferences(prefs, target)
    loaded = load_gui_preferences(target)
    assert loaded.theme == "dark"
    assert loaded.only_220k
    assert loaded.group_by_island
    assert loaded.excluded_for(first) == {"alpha", "beta"}
    assert loaded.excluded_for(second) == set()
    raw = target.read_text(encoding="utf-8")
    assert first not in raw
    assert second not in raw
    assert json.loads(raw)["excluded_by_backend"][backend_scope(first)] == ["alpha", "beta"]
    if os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o600
        assert target.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("invalid", [
    {"version": 2, "theme": "auto", "only_220k": False, "group_by_island": False, "excluded_by_backend": {}},
    {"version": 1, "theme": "unknown", "only_220k": False, "group_by_island": False, "excluded_by_backend": {}},
    {"version": 1, "theme": "auto", "only_220k": 0, "group_by_island": False, "excluded_by_backend": {}},
    {"version": 1, "theme": "auto", "only_220k": False, "group_by_island": False, "excluded_by_backend": {"not-a-hash": []}},
    {"version": 1, "theme": "auto", "only_220k": False, "group_by_island": False, "excluded_by_backend": {}, "token": "should-not-be-here"},
])
def test_gui_rejects_unknown_or_invalid_preferences(tmp_path, invalid):
    target = tmp_path / "gui.json"
    target.write_text(json.dumps(invalid), encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o600)
    with pytest.raises(GuiPreferenceError):
        load_gui_preferences(target)


def test_invalid_account_ids_or_unprotected_backend_are_rejected():
    prefs = GuiPreferences()
    with pytest.raises(GuiPreferenceError):
        prefs.set_excluded("http://127.0.0.1:8765", {"user@secret.com"})
    with pytest.raises(ValueError):
        prefs.set_excluded("http://public.example", {"alpha"})
    assert prefs.excluded_by_backend == {}


def test_gui_preference_file_rejects_symlinks_and_public_permissions(tmp_path):
    target = tmp_path / "gui.json"
    save_gui_preferences(GuiPreferences(), target)
    if os.name != "nt":
        target.chmod(0o644)
        with pytest.raises(GuiPreferenceError, match="owner-only"):
            load_gui_preferences(target)
        target.chmod(0o600)
    link = tmp_path / "alias.json"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("No symlink support")
    with pytest.raises(GuiPreferenceError, match="Unsafe"):
        load_gui_preferences(link)
    with pytest.raises(GuiPreferenceError, match="symlinks"):
        save_gui_preferences(GuiPreferences(), link)


def test_gui_preference_values_are_bounded(tmp_path):
    target = tmp_path / "gui.json"
    target.write_bytes(b"x" * 16385)
    if os.name != "nt":
        target.chmod(0o600)
    with pytest.raises(GuiPreferenceError, match="oversized"):
        load_gui_preferences(target)
    prefs = GuiPreferences()
    with pytest.raises(GuiPreferenceError):
        prefs.set_excluded("http://127.0.0.1:8765", {f"acc{i}" for i in range(101)})


def test_ssh_backend_scope_uses_private_stable_host_not_ephemeral_port():
    from daedalus.gui_preferences import GuiPreferences, backend_scope
    prefs = GuiPreferences()
    url = "ssh://debian@aiserver"
    prefs.set_excluded(url, {"alpha"})
    assert prefs.excluded_for("ssh://debian@aiserver") == {"alpha"}
    assert prefs.excluded_for("ssh://other@aiserver") == set()
    assert backend_scope(url) == backend_scope("ssh://debian@AISERVER")
    assert len(backend_scope(url)) == 64
    for bad in ("ssh://-oProxyCommand=x", "ssh://../a", "ssh://host?cookie=secret"):
        with pytest.raises(ValueError):
            backend_scope(bad)


def test_working_scope_round_trip_distinguishes_empty_and_all(tmp_path):
    path = tmp_path / "gui.json"
    url = "https://controller.example"
    prefs = GuiPreferences()
    assert prefs.working_for(url) is None
    for ids in (["alpha", "beta"], ["beta"], []):
        prefs.set_working(url, ids)
        save_gui_preferences(prefs, path)
        assert load_gui_preferences(path).working_for(url) == ids
        assert load_gui_preferences(path).working_for("https://other.example") is None
    prefs.set_working(url, None)
    save_gui_preferences(prefs, path)
    assert load_gui_preferences(path).working_for(url) is None
