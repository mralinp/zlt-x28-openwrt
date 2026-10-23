# Logo and brand

<p align="center">
  <img src="logo-horizontal.svg" alt="X28 OpenWrt" width="420">
</p>

## The idea

**Open core.** An X whose four arms stop short of the centre, leaving a small diamond core floating in the
middle: the locked unit, opened up to its core. The teal core is the only accent and carries the idea, so
keep it teal wherever colour is available.

## Colours

| Role | Light backgrounds | Dark backgrounds |
|---|---|---|
| Arms, wordmark | Ink `#0F1B2D` (RGB 15 27 45) | Paper `#E6EDF3` (RGB 230 237 243) |
| Core (accent) | Teal `#14B8A6` (RGB 20 184 166) | Light teal `#2DD4BF` (RGB 45 212 191) |

One-colour versions (`logo-black`, `logo-white`) exist for print, embossing and anywhere a single colour is required.

## Files

| File | Use |
|---|---|
| `logo.svg`, `logo-dark.svg` | the mark on light / dark backgrounds (README uses both via `<picture>`) |
| `logo-small.svg`, `logo-dark-small.svg` | **small-size cut** (bigger core, wider gaps) for anything under ~48 px |
| `logo-horizontal.svg`, `logo-dark-horizontal.svg` | mark + wordmark side by side |
| `logo-stacked.svg`, `logo-dark-stacked.svg` | mark above the wordmark |
| `logo-black*.svg`, `logo-white*.svg` | one-colour versions |
| `favicon.svg`, `favicon.ico` (16/32/48) | browser icon: small cut on an ink tile |
| `app-icon.svg`, `icon-180.png`, `icon-192.png`, `icon-512.png` | app / touch icons |
| `social-preview.png` (1280×640) | GitHub repository social preview (Settings → Social preview) |

## Rules

- **Clear space**: keep at least the width of one arm (about 18 % of the mark's height) free on every side.
- **Minimum size**: the main mark from 32 px; below that use the small cut (it holds at 16 px). The lockups
  from 120 px wide.
- **Wordmark**: "X28" in Inter Bold, "OpenWrt" in Inter Medium (weight 540), outlined to paths. Do not retype
  it in another font.
- **Don't**: recolour the arms teal or the core ink in the colour version, rotate the mark (it is an X, not a
  plus), add outlines, shadows or gradients, squeeze it, or set it on busy photos without an ink or paper tile.

## Rebuilding

All SVGs are generated, not hand-drawn:

```bash
curl -fLo Inter-var.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf"
python3 tools/brand/build_logo.py --font Inter-var.ttf      # writes docs/assets/*.svg
```

Change the geometry in `tools/brand/build_logo.py` (`MAIN`, `SMALL`), not in the SVGs. Render PNGs and the ICO
from the SVGs with any renderer (headless Chrome, `rsvg-convert`, Inkscape). The originals were rendered with
the logo-design skill's `render_png.py` (Chrome).

Inter is © The Inter Project Authors, SIL Open Font License 1.1. Only outlined glyph paths are in this repo, not
the font. The mark was designed for this project; no trademark search has been done.
