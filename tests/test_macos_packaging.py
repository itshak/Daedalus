"""Mac package build helpers: platform-independent safety tests."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def packager():
    location = Path(__file__).resolve().parents[1] / "packaging" / "build_macos_app.py"
    spec = importlib.util.spec_from_file_location("daedalus_macos_packaging", location)
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    return package


def test_launcher_executes_only_renamed_desktop_package(packager):
    source = packager.launcher_source()
    assert "from daedalus.desktop import main" in source
    assert "from ikabot" not in source
    assert "from selenium" not in source
    assert "config.ini" not in source
    compile(source, "<test-launcher>", "exec")


def test_pyinstaller_build_is_native_and_avoids_legacy_scraper(packager, tmp_path):
    cmd = packager.build_command(
        tmp_path / "launcher.py",
        output_dir=tmp_path / "dist",
        work_dir=tmp_path / "build",
        spec_dir=tmp_path / "spec",
    )
    assert "--windowed" in cmd
    assert "Daedalus" in cmd
    assert "io.github.itshak.daedalus" in cmd
    assert "qfluentwidgets" in cmd
    assert "daedalus.desktop.app" in cmd
    assert "selenium" not in cmd
    assert "undetected_chromedriver" not in cmd
    assert "accounts.toml" not in cmd
    assert "/Applications" not in " ".join(cmd)


def test_dry_run_does_not_create_app_or_user_files(packager, tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("dry-run must not invoke PyInstaller")

    monkeypatch.setattr(subprocess, "run", forbidden)
    target = tmp_path / "not-created"
    bundle = packager.build(output_dir=target, dry_run=True)
    assert bundle == target / "Daedalus.app"
    assert not target.exists()


def test_non_macos_build_fails_fast(packager, tmp_path, monkeypatch):
    monkeypatch.setattr(packager.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="require macOS"):
        packager.build(output_dir=tmp_path, dry_run=False)


def test_script_has_no_user_config_side_effects(packager):
    script = Path(packager.__file__).read_text()
    assert "shutil.copytree" not in script
    assert "shutil.copy(" not in script
    assert "seed_config(" not in script
    assert "os.environ[" not in script
