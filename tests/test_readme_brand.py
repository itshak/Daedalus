"""README branding must use checked-in, theme-appropriate raster assets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_hero_uses_light_and_dark_stacked_png_logos():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for theme in ("light", "dark"):
        image = f"assets/brand/png/daedalus-logo-{theme}-1600.png"
        assert (ROOT / image).is_file()
        assert image in readme

    assert 'media="(prefers-color-scheme: dark)"' in readme
    assert 'media="(prefers-color-scheme: light)"' in readme
    assert 'width="700"' in readme
    assert 'alt="Daedalus:' in readme
    assert 'assets/brand/svg/daedalus-horizontal-light.svg' not in readme
