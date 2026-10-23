#!/usr/bin/env python3
"""Rebuild the X28 OpenWrt logo SVGs from parameters (docs/assets/BRAND.md explains the design).

The mark ("Open core") is an X whose four arms stop short of the centre around a diamond core.
Geometry is generated, not hand-drawn, so it stays exact: arms are capsules on the diagonals,
the core a diamond with softened corners. The wordmark is Inter (SIL OFL 1.1) converted to paths.

    python3 tools/brand/build_logo.py --font Inter-var.ttf [--out docs/assets]

Needs fontTools for the wordmark. Get Inter's variable TTF from
https://github.com/google/fonts/tree/main/ofl/inter (Inter 4.001 was used).
PNG/ICO renders are made from these SVGs with any SVG renderer (see BRAND.md).
"""
import argparse
import math
import os
import re

INK, TEAL, PAPER, TEAL_LIGHT = "#0F1B2D", "#14B8A6", "#E6EDF3", "#2DD4BF"
TITLE = "X28 OpenWrt"


def mark(R, INNER, OUTER, CORE, CORNER=3.6, C=128.0):
    """(arms path, core path) in a 256x256 box. INNER/OUTER: arm cap centres from the centre."""
    f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")  # noqa: E731

    def capsule(a):
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        ax, ay, bx, by = C + ux * INNER, C + uy * INNER, C + ux * OUTER, C + uy * OUTER
        p = lambda x, y: f"{f(x)} {f(y)}"  # noqa: E731
        return (f"M{p(ax + nx * R, ay + ny * R)}L{p(bx + nx * R, by + ny * R)}A{f(R)} {f(R)} 0 0 0 {p(bx - nx * R, by - ny * R)}"
                f"L{p(ax - nx * R, ay - ny * R)}A{f(R)} {f(R)} 0 0 0 {p(ax + nx * R, ay + ny * R)}Z")
    pts = [(C, C - CORE), (C + CORE, C), (C, C + CORE), (C - CORE, C)]
    d = []
    for i, (x, y) in enumerate(pts):
        (px, py), (qx, qy) = pts[i - 1], pts[(i + 1) % 4]

        def toward(bx, by):
            k = CORNER * 1.6 / math.hypot(bx - x, by - y)
            return x + (bx - x) * k, y + (by - y) * k
        s, e = toward(px, py), toward(qx, qy)
        d.append(("M" if i == 0 else "L") + f"{f(s[0])} {f(s[1])}Q{f(x)} {f(y)} {f(e[0])} {f(e[1])}")
    return "".join(capsule(math.radians(a)) for a in (45, 135, 225, 315)), "".join(d) + "Z"


MAIN = mark(R=23, INNER=60, OUTER=104, CORE=26)                  # gap core->arm: 11 units
SMALL = mark(R=25, INNER=70, OUTER=102, CORE=30, CORNER=3)       # favicon cut, gap 15 units


def svg(body, vb="0 0 256 256"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="{TITLE}">'
            f"<title>{TITLE}</title>{body}</svg>\n")


def symbol(m, arm, core):
    return f'<path fill="{arm}" d="{m[0]}"/><path fill="{core}" d="{m[1]}"/>'


def wordmark(font_path):
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    fonts = {w: instantiateVariableFont(TTFont(font_path), {"wght": w, "opsz": 32}, inplace=False) for w in (700, 540)}
    cap = fonts[700]["OS/2"].sCapHeight

    def run(weight, text, x, baseline, cap_px, tracking):
        font = fonts[weight]
        s = cap_px / cap
        gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
        d, pen_x = [], x
        for ch in text:
            g = cmap[ord(ch)]
            pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
            gs[g].draw(TransformPen(pen, (s, 0, 0, -s, pen_x, baseline)))
            d.append(pen.getCommands())
            pen_x += hmtx[g][0] * s + tracking
        return "".join(d), pen_x - x - tracking
    return run


def build(out, font_path):
    os.makedirs(out, exist_ok=True)
    w = lambda name, text: open(os.path.join(out, name), "w").write(text)  # noqa: E731
    for name, (arm, core) in {"logo": (INK, TEAL), "logo-dark": (PAPER, TEAL_LIGHT),
                              "logo-black": ("#000", "#000"), "logo-white": ("#FFF", "#FFF")}.items():
        w(f"{name}.svg", svg(symbol(MAIN, arm, core)))
        w(f"{name}-small.svg", svg(symbol(SMALL, arm, core)))
    tile = lambda rx, k: (f'<rect width="256" height="256" rx="{rx}" fill="{INK}"/>'  # noqa: E731
                          f'<g transform="translate({128 * (1 - k):g} {128 * (1 - k):g}) scale({k})">{symbol(SMALL, PAPER, TEAL_LIGHT)}</g>')
    w("favicon.svg", svg(tile(48, 0.9)))
    w("app-icon.svg", svg(tile(56, 0.8)))

    run = wordmark(font_path)
    for name, (arm, core, text) in {"logo": (INK, TEAL, INK), "logo-dark": (PAPER, TEAL_LIGHT, PAPER)}.items():
        # horizontal: wordmark cap height 96, centred on the mark's centre line
        base = 128 + 48
        d1, w1 = run(700, "X28", 296, base, 96, -1.5)
        d2, w2 = run(540, "OpenWrt", 296 + w1 + 30, base, 96, -1.5)
        width = 296 + w1 + 30 + w2 + 8
        w(f"{name}-horizontal.svg", svg(symbol(MAIN, arm, core) + f'<path fill="{text}" d="{d1}"/><path fill="{text}" d="{d2}"/>',
                                        f"0 0 {width:.0f} 256"))
        # stacked: wordmark cap height 64 under the mark
        _, a1 = run(700, "X28", 0, 0, 64, -1)
        _, a2 = run(540, "OpenWrt", 0, 0, 64, -1)
        tw = a1 + 20 + a2
        width2 = max(256, tw + 16)
        ox, mx, base2 = (width2 - tw) / 2, (width2 - 256) / 2, 256 + 36 + 64
        t1, _ = run(700, "X28", ox, base2, 64, -1)
        t2, _ = run(540, "OpenWrt", ox + a1 + 20, base2, 64, -1)
        w(f"{name}-stacked.svg", svg(f'<g transform="translate({mx:.2f} 0)">{symbol(MAIN, arm, core)}</g>'
                                     f'<path fill="{text}" d="{t1}"/><path fill="{text}" d="{t2}"/>',
                                     f"0 0 {width2:.0f} {base2 + 20:.0f}"))
    # social preview (1280x640): dark lockup on ink with a teal rule
    h = open(os.path.join(out, "logo-dark-horizontal.svg")).read()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', h)[1].split()]
    inner = re.search(r"</title>(.*)</svg>", h, re.S)[1]
    k = 0.62
    x, y = (1280 - vb[2] * k) / 2, (640 - vb[3] * k) / 2 - 30
    w("social-preview.svg", f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 640" width="1280" height="640">'
      f'<rect width="1280" height="640" fill="{INK}"/><g transform="translate({x:.1f} {y:.1f}) scale({k})">{inner}</g>'
      f'<rect x="580" y="{y + vb[3] * k + 40:.0f}" width="120" height="6" rx="3" fill="{TEAL_LIGHT}"/></svg>\n')


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--font", required=True, help="Inter variable TTF (OFL)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "..", "docs", "assets"))
    a = ap.parse_args()
    build(os.path.abspath(a.out), a.font)
    print("wrote", os.path.abspath(a.out))
