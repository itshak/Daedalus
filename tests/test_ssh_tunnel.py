"""Safe SSH startup and private remembered host; no real SSH process/network."""
from __future__ import annotations

import json
import os
import re

import pytest

from daedalus.desktop.ssh_tunnel import (
    LocalSSHTunnel,
    SSHConnectionUnavailable,
    forget_ssh_destination,
    load_ssh_destination,
    save_ssh_destination,
    validate_ssh_destination,
)


@pytest.mark.parametrize("host", [
    "", "-oProxyCommand=evil", "user@-evil", "user@server;echo", "user@server extra",
    "../../../x", "user@host/path", "http://host", "user@host\n", "@@host",
])
def test_ssh_invalid_destination_refused_before_command(host):
    with pytest.raises(ValueError):
        LocalSSHTunnel(host)


def test_ssh_destination_is_only_basic_username_and_host():
    assert validate_ssh_destination("aiserver") == "aiserver"
    assert validate_ssh_destination("debian@aiserver") == "debian@aiserver"


def test_saved_ssh_host_only_contains_private_nonsecret_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_ssh_destination("debian@aiserver")
    file = tmp_path / "daedalus" / "ssh-host.json"
    saved = json.loads(file.read_text())
    assert saved == {"version": 1, "destination": "debian@aiserver"}
    assert "token" not in file.read_text().lower()
    assert load_ssh_destination() == "debian@aiserver"
    if os.name != "nt":
        assert file.stat().st_mode & 0o077 == 0
    forget_ssh_destination()
    assert load_ssh_destination() is None


def test_ssh_host_symlinks_and_world_readable_files_are_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_ssh_destination("aiserver")
    path = tmp_path / "daedalus" / "ssh-host.json"
    if os.name != "nt":
        path.chmod(0o644)
        with pytest.raises(SSHConnectionUnavailable):
            load_ssh_destination()
        path.chmod(0o600)
    path.unlink()
    path.symlink_to(tmp_path / "not-there")
    with pytest.raises(SSHConnectionUnavailable):
        load_ssh_destination()


def test_ssh_launch_uses_only_loopback_port_forwarding_and_never_shell(monkeypatch):
    import daedalus.desktop.ssh_tunnel as mod

    commands = []
    class FakeProcess:
        def __init__(self):
            self.stopped = False
        def poll(self):
            return 0 if self.stopped else None
        def terminate(self):
            self.stopped = True
        def wait(self,timeout=None):
            return 0
    fake = FakeProcess()
    def popen(args, **kwargs):
        commands.append((args,kwargs))
        return fake
    monkeypatch.setattr(mod.subprocess, "Popen", popen)
    class EmptyConnection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(mod.socket, "create_connection", lambda *args, **kwargs: EmptyConnection())
    tunnel = LocalSSHTunnel("debian@aiserver")
    try:
        url=tunnel.start()
        assert re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",url)
        args,kw=commands[0]
        assert args[0]=="ssh"
        assert "-N" in args and "-T" in args
        assert "StrictHostKeyChecking=yes" in args
        assert "BatchMode=yes" in args
        forward = args[args.index("-L")+1]
        assert re.fullmatch(r"127\.0\.0\.1:\d+:127\.0\.0\.1:8765", forward)
        assert args[-1] == "debian@aiserver"
        assert kw["stdin"] == mod.subprocess.DEVNULL
        assert "shell" not in kw or kw["shell"] is False
        assert "password" not in str(commands).lower()
    finally:
        tunnel.close()
    assert fake.stopped
    assert not tunnel.running()
