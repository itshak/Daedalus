# Daedalus production brand assets

Original winged-D artwork inspired by Greek mythology, Ikariam, and IkaBot. The master artwork is the transparent, path-only SVG in `svg/`; do not use concept raster drafts as masters. The refined application icon has a simpler sun and omits the tiny Greek-key base.

| Usage | Asset |
|---|---|
| Light UI surfaces | `svg/daedalus-logo-light.svg` |
| Dark UI surfaces | `svg/daedalus-logo-dark.svg` |
| Horizontal lockup | `svg/daedalus-horizontal-{light,dark}.svg` |
| Small-size icon | `svg/favicon.svg` |
| App icon | `svg/daedalus-app-icon.svg`, `png/app-icon-1024.png` |
| Native macOS bundle | `app-icons/macos/Daedalus.icns` |
| Windows executable | `app-icons/windows/daedalus.ico` |
| Website/PWA | `app-icons/web/` (favicon, touch, manifest, maskable) |
| iOS | `app-icons/ios/` (opaque 1024px and touch) |
| Android | `app-icons/android/` (density launchers and adaptive icons) |
| Desktop Qt | `src/daedalus/desktop/resources/app-icon-256.png` |

All output files are regenerated from the SVG masters by:

```bash
python -m pip install -e ".[desktop]"
python packaging/generate_brand_assets.py
```

Theme colors: Midnight `#0C2031`, Aegean Navy `#102F46`, Aegean Blue `#176184`, Sun Gold `#FFC764`, Ivory `#FFF4DE`.

For a web client, place the files in `app-icons/web/` at the web server's static root and reference `favicon.ico`, `apple-touch-icon.png`, and `site.webmanifest`. This repo currently ships a native Qt desktop (not an active web frontend), so the web assets are ready for later adoption but are not advertised as a currently running PWA.

The artwork has no dependence on image URLs or external fonts. Consider trademark clearance before public branding.
