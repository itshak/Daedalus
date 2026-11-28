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
    assert "daedalus.desktop.task_page" in cmd
    assert "selenium" in cmd
    assert "undetected_chromedriver" in cmd
    assert "webdriver_manager" in cmd
    assert "daedalus.desktop.selenium_worker" in cmd
    assert "accounts.toml" not in cmd
    assert "/Applications" not in " ".join(cmd)


def test_native_icon_and_bundled_qt_resource_are_in_packager(packager, tmp_path):
    cmd = packager.build_command(
        tmp_path / "launcher.py", output_dir=tmp_path / "dist",
        work_dir=tmp_path / "build", spec_dir=tmp_path / "spec",
    )
    icon_path = Path(cmd[cmd.index("--icon") + 1])
    assert icon_path.name == "Daedalus.icns"
    assert icon_path.is_file()
    assert icon_path.read_bytes().startswith(b"icns")
    bundled = cmd[cmd.index("--add-data") + 1]
    assert "daedalus/desktop/resources" in bundled
    assert (packager.ROOT / "src/daedalus/desktop/resources/app-icon-256.png").is_file()


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


def test_native_mac_browser_packaging_requires_renderer_helper(packager, tmp_path):
    bundle = tmp_path / "Daedalus.app"
    bundle.mkdir()
    with pytest.raises(RuntimeError, match="WebEngine browser subprocess"):
        packager.require_native_browser_runtime(bundle)
    helper = bundle / "Contents/Frameworks/QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
    helper.parent.mkdir(parents=True)
    helper.write_bytes(b"synthetic Qt WebEngine helper")
    packager.require_native_browser_runtime(bundle)


def test_direct_dmg_distribution_is_release_only_after_verified_main_build():
    """A release asset is a raw DMG; PRs must never get a write-scoped job."""
    source = (Path(__file__).resolve().parents[1]
              / ".github/workflows/macos-app.yml").read_text()
    assert "  publish-direct-dmg:" in source
    package, publish = source.split("  publish-direct-dmg:", 1)
    assert "permissions:\n  contents: read" in package
    assert "name: Daedalus-macos-dmg" in package
    assert "name: Publish directly downloadable macOS DMG" in publish
    assert "needs: [package]" in publish
    assert "github.ref == 'refs/heads/main'" in publish
    assert "github.event_name == 'push'" in publish
    assert "github.event_name == 'workflow_dispatch'" in publish
    assert "contents: write" in publish
    assert "actions/download-artifact@v4" in publish
    assert "gh release create" in publish
    assert "--prerelease" in publish
    assert "gh release upload" in publish
    assert "Daedalus-macos-preview.dmg.sha256" in publish
    assert ".assets[] | select(.name == \"Daedalus-macos-preview.dmg\")" in publish
    assert "gh release" not in package


def test_direct_dmg_documentation_does_not_promise_gatekeeper_bypass():
    docs = (Path(__file__).resolve().parents[1]
            / "docs/MACOS-BUILD.md").read_text()
    assert "GitHub Releases" in docs
    assert "**not wrapped in an Actions ZIP**" in docs
    assert "not Apple notarized" in docs
    assert "first-launch" in docs



def test_blindbase_first_install_quarantine_flow_is_in_dmg_builder():
    """Copy BlindBase's actual HFS+ and xattr first-run pattern, not auto-execution."""
    source = (Path(__file__).resolve().parents[1]
              / "packaging/build_macos_dmg.py").read_text()
    assert '"-fs", "HFS+"' in source
    assert '"-format", "UDZO"' in source
    assert "readme_first.txt" in source
    assert "xattr -cr /Applications/Daedalus.app" in source
    assert "Install Daedalus.command" in source
    assert "shutil.copy2(INSTALLER_SOURCE" in source
    assert "chmod(0o755)" in source
    assert "subprocess.run([\"ditto\"" in source
    assert "codesign" in source
    assert "os.symlink(\"/Applications\"" in source


def test_verified_dmg_installer_is_tested_with_synthetic_quarantine():
    workflow = (Path(__file__).resolve().parents[1]
                / ".github/workflows/macos-app.yml").read_text()
    assert 'test -x "$mount_dir/Install Daedalus.command"' in workflow
    assert 'test -f "$mount_dir/readme_first.txt"' in workflow
    assert 'grep -F \'xattr -cr /Applications/Daedalus.app\'' in workflow
    assert 'DAEDALUS_INSTALL_ROOT="$RUNNER_TEMP/daedalus-dmg-install-test"' in workflow
    assert 'xattr -w com.apple.quarantine' in workflow
    assert 'DMG installer failed to clear app-specific quarantine' in workflow
    installer = (Path(__file__).resolve().parents[1]
                 / "packaging/Install Daedalus.command").read_text()
    assert 'expected_id="io.github.itshak.daedalus"' in installer
    assert "/usr/bin/codesign --verify --deep --strict" in installer
    assert "/usr/bin/xattr -dr com.apple.quarantine" in installer
    assert "DAEDALUS_INSTALL_ROOT" in installer


def test_blindbase_package_docs_warn_about_gatekeeper():
    docs = (Path(__file__).resolve().parents[1]
            / "docs/MACOS-BUILD.md").read_text()
    assert "BlindBase" in docs
    assert "xattr -cr /Applications/Daedalus.app" in docs
    assert "not permit DMGs to silently auto-execute commands" in docs
    assert "Apple Developer ID signing and notarization" in docs


def test_beta_bundle_metadata_matches_python_project(packager, tmp_path):
    import plistlib
    import tomllib

    contents = tmp_path / "Daedalus.app" / "Contents"
    contents.mkdir(parents=True)
    target = contents / "Info.plist"
    target.write_bytes(plistlib.dumps({"CFBundleIdentifier":packager.BUNDLE_IDENTIFIER}))
    packager.stamp_bundle_metadata(contents.parent,"a"*40)
    data=plistlib.loads(target.read_bytes())
    version=tomllib.loads((packager.ROOT/"pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert data["DaedalusReleaseVersion"]==version
    assert data["CFBundleShortVersionString"]==version.split("b",1)[0]
    assert data["DaedalusSourceRevision"]=="a"*40
    assert data["CFBundleIdentifier"]==packager.BUNDLE_IDENTIFIER
