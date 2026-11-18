"""Brand asset checks that work without GUI or graphics dependencies."""
from __future__ import annotations

import json
import struct
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"


def test_editable_svg_masters_are_present_and_valid():
    required = (
        "daedalus-logo-light.svg", "daedalus-logo-dark.svg",
        "daedalus-horizontal-light.svg", "daedalus-horizontal-dark.svg",
        "daedalus-app-icon.svg", "daedalus-app-icon-square.svg",
        "daedalus-maskable-icon.svg", "favicon.svg",
    )
    for filename in required:
        source = BRAND / "svg" / filename
        root = ElementTree.parse(source).getroot()
        assert root.tag.endswith("svg")
    assert (BRAND / "svg" / required[0]).read_bytes() != (
        BRAND / "svg" / required[1]
    ).read_bytes()


def test_desktop_resource_is_real_256px_png():
    target = ROOT / "src" / "daedalus" / "desktop" / "resources" / "app-icon-256.png"
    payload = target.read_bytes()
    assert payload[:8] == bytes((137, 80, 78, 71, 13, 10, 26, 10))
    assert struct.unpack(">II", payload[16:24]) == (256, 256)


def test_native_mac_icon_has_all_retina_sizes():
    payload = (BRAND / "app-icons" / "macos" / "Daedalus.icns").read_bytes()
    assert payload[:4] == b"icns"
    assert struct.unpack(">I", payload[4:8])[0] == len(payload)
    kinds = set()
    pos = 8
    while pos < len(payload):
        name = payload[pos:pos+4]
        length = struct.unpack(">I", payload[pos+4:pos+8])[0]
        assert length >= 8
        assert payload[pos+8:pos+16] == bytes((137, 80, 78, 71, 13, 10, 26, 10))
        kinds.add(name)
        pos += length
    assert pos == len(payload)
    assert {b"icp4", b"icp5", b"icp6", b"ic07", b"ic08",
            b"ic09", b"ic10"} <= kinds


def test_web_manifest_references_shipped_png_files():
    folder = BRAND / "app-icons" / "web"
    manifest = json.loads((folder / "site.webmanifest").read_text())
    assert manifest["short_name"] == "Daedalus"
    for entry in manifest["icons"]:
        assert (folder / entry["src"]).is_file()
        assert entry["type"] == "image/png"
    assert (folder / "favicon.ico").read_bytes().startswith(bytes((0, 0, 1, 0)))


def test_mobile_app_icon_exports_exist():
    assert (BRAND / "app-icons" / "ios" / "app-icon-1024.png").exists()
    for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
        assert (BRAND / "app-icons" / "android" /
                f"mipmap-{density}" / "ic_launcher.png").is_file()
