#!/usr/bin/env python3
"""Rebuild Daedalus raster/native icons from the committed vector masters.

Requires PySide6 (available with `pip install -e ".[desktop]"`).
Never downloads any artwork or uses system fonts.
"""
from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
SVG = BRAND / "svg"
PNG = BRAND / "png"
NATIVE = BRAND / "app-icons"
RESOURCE = ROOT / "src" / "daedalus" / "desktop" / "resources"


def render(name: str, target: Path, size: int) -> bytes:
    """Export a square icon or width-constrained logo with transparent alpha."""
    renderer = QSvgRenderer(str(SVG / name))
    if not renderer.isValid():
        raise ValueError(f"Invalid brand vector: {name}")
    natural = renderer.defaultSize()
    height = round(size * natural.height() / natural.width())
    image = QImage(size, height, QImage.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(target), "PNG"):
        raise OSError(f"Unable to save brand asset {target}")
    return target.read_bytes()


def icon_file(target: Path, sizes: list[int], sources: dict[int, Path]) -> None:
    """ICO with exact source size per entry (never upscale the 16 px icon)."""
    images = [sources[s].read_bytes() for s in sizes]
    start = 6 + 16 * len(images)
    entries = []
    for size, data in zip(sizes, images):
        entries.append(struct.pack("<BBBBHHII", size if size < 256 else 0,
                                   size if size < 256 else 0, 0, 0, 1, 32,
                                   len(data), start))
        start += len(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(struct.pack("<HHH", 0, 1, len(images))
                       + b"".join(entries) + b"".join(images))


def mac_icon(target: Path, sources: dict[int, Path]) -> None:
    """Build the standard PNG-backed Retina family of macOS ICNS chunks."""
    types = [(16, b"icp4"), (32, b"icp5"), (64, b"icp6"), (128, b"ic07"),
             (256, b"ic08"), (512, b"ic09"), (1024, b"ic10")]
    chunks = []
    for size, tag in types:
        data = sources[size].read_bytes()
        chunks.append(tag + struct.pack(">I", len(data) + 8) + data)
    payload = b"".join(chunks)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"icns" + struct.pack(">I", len(payload) + 8) + payload)


def generate() -> None:
    for theme in ("light", "dark"):
        for prefix, width in (("daedalus-logo", 1600),
                              ("daedalus-horizontal", 1600),
                              ("daedalus-mark", 1024)):
            name = f"{prefix}-{theme}"
            render(name + ".svg", PNG / f"{name}-{width}.png", width)

    icon_sizes = [16, 20, 24, 32, 40, 48, 64, 72, 96, 128, 144,
                  180, 192, 256, 384, 512, 1024]
    sources = {}
    for size in icon_sizes:
        source = "favicon.svg" if size <= 32 else "daedalus-app-icon.svg"
        sources[size] = PNG / f"app-icon-{size}.png"
        render(source, sources[size], size)
    for size in (256, 512, 1024):
        render("daedalus-app-icon-light.svg",
               PNG / f"app-icon-light-{size}.png", size)

    mac_icon(NATIVE / "macos" / "Daedalus.icns", sources)
    favicon_sources = {}
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        path = NATIVE / "web" / f"favicon-{size}.png"
        render("favicon.svg", path, size)
        favicon_sources[size] = path
    ico_sources = {s: favicon_sources[s] if s <= 48 else sources[s]
                   for s in (16, 24, 32, 48, 64, 128, 256)}
    icon_file(NATIVE / "windows" / "daedalus.ico",
              [16, 24, 32, 48, 64, 128, 256], ico_sources)
    icon_file(NATIVE / "web" / "favicon.ico",
              [16, 24, 32, 48], favicon_sources)
    shutil.copyfile(NATIVE / "web" / "favicon.ico", BRAND / "favicon.ico")

    render("daedalus-app-icon-square.svg",
           NATIVE / "ios" / "app-icon-1024.png", 1024)
    render("daedalus-app-icon-square.svg",
           NATIVE / "ios" / "apple-touch-icon-180.png", 180)
    shutil.copyfile(NATIVE / "ios" / "apple-touch-icon-180.png",
                    NATIVE / "web" / "apple-touch-icon.png")
    for size in (192, 512):
        render("daedalus-app-icon-square.svg",
               NATIVE / "web" / f"icon-{size}.png", size)
    render("daedalus-maskable-icon.svg",
           NATIVE / "web" / "maskable-icon-512.png", 512)
    (NATIVE / "web" / "site.webmanifest").write_text(json.dumps({
        "name": "Daedalus", "short_name": "Daedalus",
        "description": "Daedalus application",
        "start_url": "/", "display": "standalone",
        "background_color": "#0C2031", "theme_color": "#0C2031",
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192",
             "type": "image/png", "purpose": "any"},
            {"src": "icon-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "any"},
            {"src": "maskable-icon-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    }, indent=2) + "\n", encoding="utf-8")

    for density, size in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96),
                          ("xxhdpi", 144), ("xxxhdpi", 192)):
        folder = NATIVE / "android" / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        for name in ("ic_launcher.png", "ic_launcher_round.png"):
            shutil.copyfile(sources[size], folder / name)
    render("android-adaptive-foreground.svg",
           NATIVE / "android" / "ic_launcher_foreground.png", 432)
    background = QImage(432, 432, QImage.Format_ARGB32)
    background.fill("#0C2031")
    background.save(str(NATIVE / "android" / "ic_launcher_background.png"), "PNG")
    (NATIVE / "android" / "ic_launcher.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '  <background android:drawable="@drawable/ic_launcher_background"/>\n'
        '  <foreground android:drawable="@drawable/ic_launcher_foreground"/>\n'
        '</adaptive-icon>\n', encoding="utf-8")

    RESOURCE.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sources[256], RESOURCE / "app-icon-256.png")
    print("Generated Daedalus logos, native app icons, mobile icons, and favicons.")


if __name__ == "__main__":
    generate()
