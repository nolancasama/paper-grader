#!/usr/bin/env python3
"""Generate PaperGrader's original vector artwork as plain SVG files.

Everything here is drawn from scratch: no fonts, no third-party art, no raster
images. Lettering comes from a small hand-defined skeleton alphabet, so the art
contains only vector paths and the correction PDFs stay free of text objects.

Run this only when changing the art. The results in ``assets/`` are committed
and bundled; the plugin never needs this script at grading time.

    python scripts/generate_art.py
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAMPS = ROOT / "assets" / "stamps"
EMBROIDERY = ROOT / "assets" / "embroidery"

# --------------------------------------------------------------------------
# SVG helpers
# --------------------------------------------------------------------------


def svg_doc(width: float, height: float, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
        f'viewBox="0 0 {width:g} {height:g}">\n{body}\n</svg>\n'
    )


def group(body: str, transform: str = "") -> str:
    attr = f' transform="{transform}"' if transform else ""
    return f"<g{attr}>{body}</g>"


def path(d: str, fill: str = "none", stroke: str = "none", sw: float = 0.0) -> str:
    stroke_attr = (
        f' stroke="{stroke}" stroke-width="{sw:g}" stroke-linecap="round" stroke-linejoin="round"'
        if stroke != "none"
        else ""
    )
    return f'<path d="{d}" fill="{fill}"{stroke_attr}/>'


def circle(cx: float, cy: float, r: float, fill: str, stroke: str = "none", sw: float = 0.0) -> str:
    stroke_attr = f' stroke="{stroke}" stroke-width="{sw:g}"' if stroke != "none" else ""
    return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}"{stroke_attr}/>'


def ellipse(cx, cy, rx, ry, fill, stroke="none", sw=0.0, rot=0.0) -> str:
    stroke_attr = f' stroke="{stroke}" stroke-width="{sw:g}"' if stroke != "none" else ""
    tf = f' transform="rotate({rot:g} {cx:g} {cy:g})"' if rot else ""
    return f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" fill="{fill}"{stroke_attr}{tf}/>'


INK = "#3a2a3d"  # soft plum outline, kinder than pure black


def star(cx: float, cy: float, r: float, fill: str, stroke: str = INK, sw: float = 1.6, rot: float = -90) -> str:
    points = []
    for i in range(10):
        radius = r if i % 2 == 0 else r * 0.5
        angle = math.radians(rot + i * 36)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    d = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in points) + " Z"
    return path(d, fill, stroke, sw)


def sparkle(cx: float, cy: float, r: float, fill: str) -> str:
    k = r * 0.16
    d = (
        f"M{cx:.2f} {cy - r:.2f} Q{cx + k:.2f} {cy - k:.2f} {cx + r:.2f} {cy:.2f} "
        f"Q{cx + k:.2f} {cy + k:.2f} {cx:.2f} {cy + r:.2f} "
        f"Q{cx - k:.2f} {cy + k:.2f} {cx - r:.2f} {cy:.2f} "
        f"Q{cx - k:.2f} {cy - k:.2f} {cx:.2f} {cy - r:.2f} Z"
    )
    return path(d, fill)


def heart(cx: float, cy: float, s: float, fill: str, stroke: str = INK, sw: float = 1.4) -> str:
    d = (
        f"M{cx:.2f} {cy + s * 0.9:.2f} "
        f"C{cx - s * 1.5:.2f} {cy - s * 0.1:.2f} {cx - s * 0.8:.2f} {cy - s * 1.1:.2f} {cx:.2f} {cy - s * 0.35:.2f} "
        f"C{cx + s * 0.8:.2f} {cy - s * 1.1:.2f} {cx + s * 1.5:.2f} {cy - s * 0.1:.2f} {cx:.2f} {cy + s * 0.9:.2f} Z"
    )
    return path(d, fill, stroke, sw)


# --------------------------------------------------------------------------
# Skeleton alphabet for bubble lettering. Each glyph sits in a 0-100 tall box.
# --------------------------------------------------------------------------
GLYPHS: dict[str, tuple[float, str]] = {
    "A": (66, "M6 96 L33 6 L60 96 M16 66 L50 66"),
    "B": (60, "M10 6 L10 96 M10 6 L34 6 C58 6 58 48 34 48 L10 48 M34 48 C64 48 64 96 34 96 L10 96"),
    "C": (62, "M56 20 C44 0 8 0 6 50 C8 100 44 100 56 80"),
    "E": (54, "M48 6 L10 6 L10 96 L48 96 M10 50 L42 50"),
    "F": (52, "M48 6 L10 6 L10 96 M10 50 L42 50"),
    "G": (68, "M58 20 C46 0 8 0 6 50 C8 100 50 104 60 76 L60 56 L38 56"),
    "I": (22, "M11 6 L11 96"),
    "J": (46, "M36 6 L36 72 C36 100 8 100 6 76"),
    "L": (48, "M10 6 L10 96 L44 96"),
    "M": (84, "M8 96 L14 6 L42 66 L70 6 L76 96"),
    "N": (68, "M9 96 L9 6 L59 96 L59 6"),
    "O": (72, "M36 4 C2 4 2 96 36 96 C70 96 70 4 36 4 Z"),
    "P": (56, "M10 96 L10 6 L32 6 C60 6 60 54 32 54 L10 54"),
    "R": (62, "M10 96 L10 6 L32 6 C60 6 60 52 32 52 L10 52 M30 52 L56 96"),
    "T": (58, "M4 8 L54 8 M29 8 L29 96"),
    "X": (62, "M8 6 L54 96 M54 6 L8 96"),
    "Z": (60, "M8 8 L52 8 L8 94 L54 94"),
    "S": (58, "M50 20 C42 0 8 2 8 26 C8 52 52 46 52 74 C52 100 14 102 6 78"),
    "U": (64, "M9 6 L9 64 C9 104 55 104 55 64 L55 6"),
    "!": (22, "M11 6 L11 66 M11 90 L11 91"),
    " ": (26, ""),
}


def bubble_word(
    text: str,
    x: float,
    y: float,
    height: float,
    fill: str,
    outline: str = INK,
    highlight: str = "#ffffff",
    arc: float = 0.0,
    bounce: float = 0.0,
    spacing: float = 10.0,
    seed: int = 1,
) -> tuple[str, float]:
    """Return ``(svg, width)`` for ``text`` as chunky rounded bubble letters."""
    rng = random.Random(seed)
    scale = height / 100.0
    total = sum(GLYPHS[c][0] + spacing for c in text) - spacing
    width = total * scale
    out: list[str] = []
    cursor = 0.0
    for index, char in enumerate(text):
        advance, d = GLYPHS[char]
        if d:
            mid = (cursor + advance / 2.0) / total - 0.5 if total else 0.0
            arc_rise = -arc * (1 - (2 * mid) ** 2)
            angle = (mid * arc * 0.9) + rng.uniform(-3, 3)
            wob = (bounce if index % 2 else -bounce) + rng.uniform(-bounce, bounce) * 0.4
            tx = x + cursor * scale
            ty = y + arc_rise + wob
            transform = (
                f"translate({tx:.2f} {ty:.2f}) rotate({angle:.2f} {advance * scale / 2:.2f} {height / 2:.2f}) "
                f"scale({scale:.4f})"
            )
            layers = (
                path(d, "none", outline, 34)
                + path(d, "none", fill, 20)
                + group(path(d, "none", highlight, 5), "translate(-3 -4)")
            )
            out.append(group(layers, transform))
        cursor += advance + spacing
    return "".join(out), width


# --------------------------------------------------------------------------
# Chibi characters: all original, drawn on a 200 x 220 canvas.
# --------------------------------------------------------------------------
SKIN = "#ffe3cf"
SKIN_SHADE = "#f7c7ad"
BLUSH = "#ff9db0"


def eyes(lx: float, rx: float, y: float, rw: float = 13, rh: float = 16, iris: str = "#5a3a7a", happy: bool = False) -> str:
    if happy:  # closed happy ^ ^ eyes
        arc = lambda cx: path(f"M{cx - rw:.1f} {y + 4:.1f} Q{cx:.1f} {y - rh:.1f} {cx + rw:.1f} {y + 4:.1f}", "none", INK, 5)
        return arc(lx) + arc(rx)
    out = ""
    for cx in (lx, rx):
        out += ellipse(cx, y, rw, rh, INK)
        out += ellipse(cx, y + 1.5, rw - 2.5, rh - 2.5, iris)
        out += ellipse(cx, y + 6, rw - 5.5, rh - 8.5, "#a98bd6")
        out += circle(cx - rw * 0.36, y - rh * 0.4, rw * 0.38, "#ffffff")
        out += circle(cx + rw * 0.34, y + rh * 0.34, rw * 0.17, "#ffffff")
    return out


def face(cy: float = 100, iris: str = "#5a3a7a", happy: bool = False, mouth: str = "open") -> str:
    out = eyes(70, 130, cy, iris=iris, happy=happy)
    out += ellipse(50, cy + 21, 12, 7, BLUSH) + ellipse(150, cy + 21, 12, 7, BLUSH)
    if mouth == "open":
        out += path(f"M88 {cy + 20} Q100 {cy + 44} 112 {cy + 20} Z", "#c8384f", INK, 3.2)
        out += ellipse(100, cy + 31, 6, 4.2, "#ff8fa0")
    elif mouth == "cat":
        out += path(f"M90 {cy + 24} Q95 {cy + 33} 100 {cy + 25} Q105 {cy + 33} 110 {cy + 24}", "none", INK, 3.6)
    else:
        out += path(f"M90 {cy + 24} Q100 {cy + 36} 110 {cy + 24}", "none", INK, 3.6)
    return out


def chibi_girl(hair: str = "#7a4f9e", hair_hi: str = "#a57fcb", bow: str = "#ff6f91", uniform: str = "#5b7fc7") -> str:
    b = ""
    # twin tails behind the head
    b += path("M34 74 C4 86 2 150 26 176 C34 152 44 122 50 96 Z", hair, INK, 3.4)
    b += path("M166 74 C196 86 198 150 174 176 C166 152 156 122 150 96 Z", hair, INK, 3.4)
    # raised arm holding a star, then body
    b += path("M60 168 C42 158 30 140 26 122", "none", INK, 16)
    b += path("M60 168 C42 158 30 140 26 122", "none", SKIN, 10)
    b += path("M140 168 C158 158 170 140 174 122", "none", INK, 16)
    b += path("M140 168 C158 158 170 140 174 122", "none", SKIN, 10)
    b += path("M64 160 Q100 150 136 160 L150 208 Q100 220 50 208 Z", uniform, INK, 3.4)
    b += path("M80 158 L100 180 L120 158 L112 154 L100 166 L88 154 Z", "#ffffff", INK, 2.4)
    b += path("M96 176 L104 176 L108 192 L100 198 L92 192 Z", "#ff6f91", INK, 2.2)
    # head
    b += ellipse(100, 92, 74, 68, SKIN, INK, 3.6)
    # fringe
    b += path(
        "M28 92 C22 34 62 16 100 16 C138 16 178 34 172 92 C162 66 150 56 134 50 C136 62 128 68 120 70 "
        "C118 58 110 50 100 46 C96 58 84 68 66 68 C64 62 66 56 68 50 C50 56 38 68 28 92 Z",
        hair, INK, 3.4,
    )
    b += path("M52 44 C66 30 84 26 98 26", "none", hair_hi, 5)
    # bows
    b += path("M34 56 L10 42 L12 72 Z M34 56 L56 40 L56 72 Z", bow, INK, 3)
    b += circle(34, 56, 7, "#ffd166", INK, 2.6)
    b += path("M166 56 L190 42 L188 72 Z M166 56 L144 40 L144 72 Z", bow, INK, 3)
    b += circle(166, 56, 7, "#ffd166", INK, 2.6)
    b += face(100)
    b += star(22, 112, 15, "#ffd166") + star(178, 112, 15, "#ffd166")
    return b


def chibi_boy(hair: str = "#3f6f9f", hair_hi: str = "#79a5cf", cap: str = "#ff9f43", uniform: str = "#3ea98a") -> str:
    b = ""
    b += path("M62 168 C46 176 36 186 30 196", "none", INK, 16) + path("M62 168 C46 176 36 186 30 196", "none", SKIN, 10)
    b += path("M138 166 C158 154 170 136 174 112", "none", INK, 16) + path("M138 166 C158 154 170 136 174 112", "none", SKIN, 10)
    b += path("M66 160 Q100 150 134 160 L146 210 Q100 220 54 210 Z", uniform, INK, 3.4)
    b += path("M82 156 L100 176 L118 156", "none", "#ffffff", 7)
    b += path("M82 156 L100 176 L118 156", "none", INK, 2)
    b += ellipse(100, 94, 72, 66, SKIN, INK, 3.6)
    # spiky hair poking from beneath the cap
    b += path(
        "M30 92 L24 70 L40 76 L36 56 L170 56 L164 76 L178 70 L170 92 C160 74 150 68 138 66 L132 78 L120 66 "
        "L108 80 L96 66 L82 80 L72 66 C56 68 42 76 30 92 Z",
        hair, INK, 3.2,
    )
    # cap with a star badge
    b += path("M34 58 C36 12 164 12 166 58 C130 46 70 46 34 58 Z", cap, INK, 3.4)
    b += path("M34 58 C70 46 130 46 166 58 C176 62 190 66 192 74 C160 62 40 62 8 74 C10 66 24 62 34 58 Z", "#e67e22", INK, 3.2)
    b += star(100, 36, 12, "#fff3b0", INK, 2)
    b += face(102, iris="#2f6a8f")
    b += star(180, 100, 16, "#ffd166")
    return b


def chibi_cat(fur: str = "#ffc98b", patch: str = "#f49d5a", ribbon: str = "#7fc7ff") -> str:
    b = ""
    b += path("M150 190 C186 190 196 156 180 134 C172 146 172 160 154 168 Z", fur, INK, 3.4)
    b += path("M178 140 C182 146 184 150 184 156", "none", patch, 7)
    b += path("M66 160 Q100 148 134 160 L142 206 Q100 218 58 206 Z", fur, INK, 3.4)
    b += ellipse(100, 186, 24, 19, "#fff3e2")
    b += ellipse(68, 208, 15, 10, fur, INK, 3) + ellipse(132, 208, 15, 10, fur, INK, 3)
    b += path("M62 168 C46 158 38 142 36 124", "none", INK, 17) + path("M62 168 C46 158 38 142 36 124", "none", fur, 11)
    b += path("M138 168 C154 158 162 142 164 124", "none", INK, 17) + path("M138 168 C154 158 162 142 164 124", "none", fur, 11)
    b += path("M30 62 L26 8 L76 34 Z", fur, INK, 3.4) + path("M170 62 L174 8 L124 34 Z", fur, INK, 3.4)
    b += path("M38 48 L36 24 L60 38 Z", "#ffb3c1") + path("M162 48 L164 24 L140 38 Z", "#ffb3c1")
    b += ellipse(100, 94, 76, 66, fur, INK, 3.6)
    b += path("M100 28 C86 36 84 50 100 58 C116 50 114 36 100 28 Z", patch)
    b += path("M34 74 C46 70 54 74 58 82", "none", patch, 7) + path("M166 74 C154 70 146 74 142 82", "none", patch, 7)
    b += face(98, iris="#3f8f6a", mouth="cat")
    b += ellipse(100, 112, 4.6, 3.2, "#ff7f96")
    for side, sign in ((26, -1), (174, 1)):
        for dy in (-6, 6):
            b += path(f"M{side + sign * -16} {110 + dy / 2} L{side + sign * 12} {110 + dy}", "none", INK, 2.6)
    b += path("M70 156 Q100 170 130 156 L126 146 Q100 158 74 146 Z", ribbon, INK, 2.6)
    b += circle(100, 160, 7, "#ffd166", INK, 2.4)
    b += heart(36, 112, 11, "#ff8fa8") + heart(164, 112, 11, "#ff8fa8")
    return b


def chibi_rabbit(fur: str = "#fdf7ff", inner: str = "#ffc2d4", vest: str = "#b08de0") -> str:
    b = ""
    b += path("M64 66 C46 12 54 -12 70 0 C88 12 90 44 88 62 Z", fur, INK, 3.4)
    b += path("M70 56 C60 26 62 12 70 14 C78 22 80 42 80 56 Z", inner)
    b += path("M136 66 C150 28 166 8 176 18 C186 32 160 58 114 62 Z", fur, INK, 3.4)
    b += path("M134 56 C146 36 160 24 168 26 C172 34 152 50 126 56 Z", inner)
    b += circle(150, 196, 14, fur, INK, 3)
    b += path("M66 160 Q100 148 134 160 L142 206 Q100 218 58 206 Z", vest, INK, 3.4)
    b += ellipse(100, 186, 19, 19, "#ffffff", INK, 2)
    b += path("M62 168 C46 158 36 142 30 124", "none", INK, 17) + path("M62 168 C46 158 36 142 30 124", "none", fur, 11)
    b += path("M138 168 C154 158 164 142 170 124", "none", INK, 17) + path("M138 168 C154 158 164 142 170 124", "none", fur, 11)
    b += ellipse(100, 96, 74, 64, fur, INK, 3.6)
    b += face(98, iris="#b0456f", mouth="cat")
    b += ellipse(100, 112, 4.6, 3.2, "#ff7f96")
    # carrot held up high
    b += path("M172 124 L190 86 L198 94 Z", "#ff9f43", INK, 2.8)
    b += path("M194 88 L204 76 M194 88 L208 84 M194 88 L198 72", "none", "#59b56f", 4)
    b += star(26, 110, 15, "#ffd166")
    return b


def chibi_dragon(scale: str = "#7fd6a4", belly: str = "#fff4c2", wing: str = "#ffb3c7") -> str:
    b = ""
    b += path("M146 190 C184 196 198 168 188 144 L180 160 L172 148 L166 166 L154 164 Z", scale, INK, 3.4)
    b += path("M50 150 C14 136 8 104 14 88 C24 96 30 94 38 100 C40 92 48 90 56 96 L66 130 Z", wing, INK, 3.4)
    b += path("M150 150 C186 136 192 104 186 88 C176 96 170 94 162 100 C160 92 152 90 144 96 L134 130 Z", wing, INK, 3.4)
    b += path("M66 160 Q100 148 134 160 L142 206 Q100 218 58 206 Z", scale, INK, 3.4)
    b += ellipse(100, 188, 24, 22, belly, INK, 2.2)
    for y in (176, 186, 196):
        b += path(f"M84 {y} Q100 {y + 5} 116 {y}", "none", "#e8c97a", 2.4)
    b += ellipse(100, 94, 74, 64, scale, INK, 3.6)
    b += path("M62 42 L54 12 L82 32 Z", "#ffd166", INK, 3) + path("M138 42 L146 12 L118 32 Z", "#ffd166", INK, 3)
    b += path("M100 30 L90 16 L100 22 L110 16 Z", "#ff9fb7", INK, 2.4)
    b += face(98, iris="#b5651d", mouth="open")
    b += star(30, 66, 11, "#ffd166") + star(172, 66, 11, "#ffd166")
    return b


CHARACTERS = {
    "girl": chibi_girl,
    "boy": chibi_boy,
    "cat": chibi_cat,
    "rabbit": chibi_rabbit,
    "dragon": chibi_dragon,
}

PRAISE = {
    "great_job": ("GREAT JOB!", "#ff6f91"),
    "excellent": ("EXCELLENT!", "#3fa7d6"),
    "amazing": ("AMAZING!", "#a56de2"),
    "genius": ("GENIUS!", "#f4933b"),
}


def scallop_ring(cx: float, cy: float, rx: float, ry: float, bumps: int, fill: str, stroke: str, sw: float) -> str:
    """A closed cookie-cutter edge, the classic shape of a Japanese teacher's stamp."""
    pts = []
    for i in range(bumps):
        a0 = 2 * math.pi * i / bumps
        pts.append((cx + rx * math.cos(a0), cy + ry * math.sin(a0)))
    d = f"M{pts[0][0]:.2f} {pts[0][1]:.2f} "
    for i in range(bumps):
        a_mid = 2 * math.pi * (i + 0.5) / bumps
        qx = cx + (rx * 1.12) * math.cos(a_mid)
        qy = cy + (ry * 1.12) * math.sin(a_mid)
        nx, ny = pts[(i + 1) % bumps]
        d += f"Q{qx:.2f} {qy:.2f} {nx:.2f} {ny:.2f} "
    return path(d + "Z", fill, stroke, sw)


def praise_stamp(character: str, word_key: str) -> str:
    text, color = PRAISE[word_key]
    w, h = 400.0, 300.0
    seed = sum(map(ord, character + word_key))
    b = scallop_ring(200, 150, 182, 132, 34, "#fffaf0", color, 5)
    b += scallop_ring(200, 150, 164, 116, 34, "none", color, 1.8)
    b += group(CHARACTERS[character](), "translate(112 16) scale(0.80)")
    lettering, lw = bubble_word(text, 0, 0, 58, color, arc=12, bounce=1.5, seed=seed)
    fit = min(1.0, 330.0 / lw)
    b += group(lettering, f"translate({200 - lw * fit / 2:.2f} {214 + (1 - fit) * 20:.2f}) scale({fit:.3f})")
    b += sparkle(62, 92, 15, "#ffd166") + sparkle(340, 86, 17, "#ffd166") + sparkle(84, 54, 8, color) + sparkle(318, 50, 9, color)
    b += heart(50, 150, 9, "#ff8fa8") + heart(352, 148, 9, "#ff8fa8")
    return svg_doc(w, h, b)


RAINBOW = ["#ff6f91", "#ff9f43", "#e0b100", "#3ea98a", "#3fa7d6", "#a56de2", "#ff6f91", "#ff9f43"]


def perfect_stamp(character: str) -> str:
    w, h = 520.0, 400.0
    b = scallop_ring(260, 200, 240, 178, 42, "#fffaf0", "#e0b100", 6)
    b += scallop_ring(260, 200, 218, 158, 42, "none", "#ff6f91", 2.2)
    # ribbon banner
    b += path("M34 262 L92 248 L92 330 L60 316 L34 342 Z", "#ff8fa8", INK, 3.4)
    b += path("M486 262 L428 248 L428 330 L460 316 L486 342 Z", "#ff8fa8", INK, 3.4)
    b += path("M70 244 Q260 288 450 244 L450 334 Q260 378 70 334 Z", "#fff0a8", INK, 3.6)
    b += group(CHARACTERS[character](), "translate(148 18) scale(1.06)")
    # rainbow PERFECT! lettering, one letter at a time
    letters = "PERFECT!"
    cursor = 92.0
    height = 66.0
    total = sum(GLYPHS[c][0] + 12 for c in letters) * height / 100.0
    cursor = 260 - total / 2
    for index, char in enumerate(letters):
        mid = (cursor + GLYPHS[char][0] * height / 200.0 - 260) / 190.0
        rise = 30 * (1 - mid * mid)
        svg, width = bubble_word(char, 0, 0, height, RAINBOW[index], seed=index + 3)
        b += group(svg, f"translate({cursor:.2f} {252 + rise:.2f}) rotate({-mid * 7:.2f})")
        cursor += width + 12 * height / 100.0
    b += star(62, 118, 24, "#ffd166") + star(458, 118, 24, "#ffd166")
    b += star(108, 56, 15, "#ff9fb7") + star(412, 56, 15, "#8fd3ff")
    b += sparkle(36, 196, 15, "#a56de2") + sparkle(484, 196, 15, "#3ea98a")
    b += sparkle(150, 26, 11, "#ff9f43") + sparkle(372, 26, 11, "#3fa7d6")
    b += heart(112, 206, 11, "#ff8fa8") + heart(408, 206, 11, "#ff8fa8")
    return svg_doc(w, h, b)


# --------------------------------------------------------------------------
# Embroidery. Each stitch is its own short stroke, so vines, satin leaves and
# lazy-daisy petals read as thread instead of as flat clip-art shapes.
# Tile units are tenths of a millimetre; 1 unit = 0.1 mm at placement time.
# --------------------------------------------------------------------------
THREAD = {
    "green": ["#5f8f63", "#79a878", "#4d7a54"],
    "sage": ["#8fae85", "#a6c09b", "#7a9a72"],
    "lilac": ["#a98bd0", "#c4aee3", "#8f70bb"],
    "coral": ["#ee8b78", "#f6a998", "#d9705f"],
    "pink": ["#ec9ab5", "#f6bccd", "#d97c9c"],
    "blue": ["#8cb8dc", "#aed0ea", "#6f9fc8"],
    "gold": ["#d9b04a", "#ecca6e", "#bd932f"],
}


def stitch(x0: float, y0: float, x1: float, y1: float, color: str, sw: float) -> str:
    return (
        f'<path d="M{x0:.2f} {y0:.2f} L{x1:.2f} {y1:.2f}" fill="none" stroke="{color}" '
        f'stroke-width="{sw:.2f}" stroke-linecap="round"/>'
    )


def stem_stitch(points: list[tuple[float, float]], family: str, rng: random.Random, sw: float = 2.1, step: float = 5.6) -> str:
    """Overlapping slanted stitches along a polyline, like a real stem stitch."""
    out = []
    shades = THREAD[family]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        count = max(1, int(length / step))
        for i in range(count):
            t0 = i / count
            t1 = min(1.0, (i + 1.5) / count)
            ax, ay = x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0
            bx, by = x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1
            nx, ny = -(y1 - y0) / (length or 1), (x1 - x0) / (length or 1)
            lean = 0.6
            out.append(stitch(ax + nx * lean, ay + ny * lean, bx - nx * lean, by - ny * lean, shades[rng.randrange(3)], sw))
    return "".join(out)


def satin_leaf(cx: float, cy: float, length: float, width: float, angle_deg: float, family: str, rng: random.Random) -> str:
    """A leaf filled with parallel satin stitches and a darker midrib."""
    out = []
    shades = THREAD[family]
    a = math.radians(angle_deg)
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy, ux
    count = max(5, int(length / 1.5))
    for i in range(count + 1):
        t = i / count
        half = width / 2 * math.sin(math.pi * t) ** 0.8
        bx, by = cx + ux * length * t, cy + uy * length * t
        tip = length * 0.08
        out.append(stitch(bx - px * half, by - py * half, bx + px * half + ux * tip, by + py * half + uy * tip, shades[i % 2], 1.5))
    out.append(stitch(cx, cy, cx + ux * length * 0.95, cy + uy * length * 0.95, shades[2], 0.8))
    return "".join(out)


def french_knot(cx: float, cy: float, r: float, family: str) -> str:
    shades = THREAD[family]
    return circle(cx, cy, r, shades[2]) + circle(cx - r * 0.2, cy - r * 0.2, r * 0.62, shades[0]) + circle(cx - r * 0.35, cy - r * 0.35, r * 0.25, shades[1])


def lazy_daisy(cx: float, cy: float, r: float, petals: int, family: str, center: str, rng: random.Random, rot: float = 0.0) -> str:
    """Petals of radial satin stitches around a cluster of French knots."""
    out = []
    shades = THREAD[family]
    half_angle = 150.0 / petals  # petals nearly touch, whatever their number
    stitches = max(5, int(r * 0.85)) | 1  # bigger petals need more thread to stay solid
    for p in range(petals):
        base = rot + p * 360.0 / petals
        for s in range(stitches):
            u = (s / (stitches - 1)) * 2 - 1  # -1 .. 1 across the petal
            a = math.radians(base + u * half_angle)
            reach = r * (0.62 + 0.38 * math.sqrt(max(0.0, 1 - u * u)))  # rounded petal tip
            out.append(stitch(cx + math.cos(a) * r * 0.22, cy + math.sin(a) * r * 0.22, cx + math.cos(a) * reach, cy + math.sin(a) * reach, shades[s % 2], 1.4))
        a = math.radians(base)
        out.append(stitch(cx + math.cos(a) * r * 0.3, cy + math.sin(a) * r * 0.3, cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82, shades[2], 0.55))
    out.append(french_knot(cx, cy, r * 0.26, center))
    for k in range(5):
        a = math.radians(rot + k * 72 + 18)
        out.append(circle(cx + math.cos(a) * r * 0.2, cy + math.sin(a) * r * 0.2, r * 0.05, THREAD[center][1]))
    return "".join(out)


def rosebud(cx: float, cy: float, r: float, family: str, rng: random.Random) -> str:
    """A spiral of short stitches in layered shades."""
    out = []
    shades = THREAD[family]
    turns = 2.6
    steps = 26
    for i in range(steps):
        t = i / steps
        a0 = t * turns * 2 * math.pi
        a1 = (t + 1.4 / steps) * turns * 2 * math.pi
        r0 = r * (0.14 + t * 0.86)
        r1 = r * (0.14 + (t + 1 / steps) * 0.86)
        out.append(stitch(cx + math.cos(a0) * r0, cy + math.sin(a0) * r0, cx + math.cos(a1) * r1, cy + math.sin(a1) * r1, shades[i % 3], 1.45))
    return "".join(out)


def scallop_edge(length: float, y: float, family: str, rng: random.Random, period: float = 19.0, depth: float = 8.0) -> str:
    """Lace scallops with blanket-stitch teeth and tiny picot knots."""
    out = []
    shades = THREAD[family]
    count = max(1, round(length / period))
    period = length / count
    for i in range(count):
        x0 = i * period
        segs = 8
        last = None
        for s in range(segs + 1):
            t = s / segs
            px = x0 + t * period
            py = y - math.sin(t * math.pi) * depth
            if last:
                out.append(stitch(last[0], last[1], px, py, shades[s % 2], 1.05))
            if s % 2 == 0 and 0 < s < segs:
                out.append(stitch(px, py, px, py + 2.6, shades[1], 0.6))
            last = (px, py)
        out.append(circle(x0 + period / 2, y - depth - 2.0, 1.25, THREAD["gold"][0]))
        out.append(circle(x0, y - 0.6, 0.95, THREAD["gold"][2]))
    return "".join(out)


TILE_W, TILE_H = 180.0, 70.0  # 18 mm x 7 mm


def edge_tile(variant: int) -> str:
    """One repeat of the running border. The left and right ends join seamlessly."""
    rng = random.Random(1000 + variant)
    body = ""
    vine_y = 42.0
    amp = 7.5
    # two intertwined vines that meet the neighbouring tile at matching phases
    vine_a = [(x, vine_y + amp * math.sin(2 * math.pi * x / TILE_W)) for x in [i * TILE_W / 36 for i in range(37)]]
    vine_b = [(x, vine_y - amp * math.sin(2 * math.pi * x / TILE_W)) for x in [i * TILE_W / 36 for i in range(37)]]
    body += scallop_edge(TILE_W, 15.0, "lilac" if variant % 2 else "blue", rng)
    body += stem_stitch(vine_b, "sage", rng, sw=1.6)
    body += stem_stitch(vine_a, "green", rng, sw=1.9)
    flowers = [
        (("coral", "gold", 5), ("lilac", "gold", 5)),
        (("pink", "gold", 6), ("blue", "gold", 5)),
        (("lilac", "gold", 5), ("coral", "gold", 6)),
        (("blue", "gold", 6), ("pink", "gold", 5)),
    ][variant % 4]
    body += satin_leaf(30, 37, 21, 8, -38, "green", rng) + satin_leaf(30, 47, 19, 7, 34, "sage", rng)
    body += satin_leaf(150, 37, 21, 8, 218, "sage", rng) + satin_leaf(150, 47, 19, 7, 146, "green", rng)
    body += satin_leaf(82, 34, 15, 6, -150, "sage", rng) + satin_leaf(98, 50, 15, 6, 30, "green", rng)
    body += lazy_daisy(46, vine_y, 12.5, flowers[0][2], flowers[0][0], flowers[0][1], rng, rot=variant * 17)
    body += lazy_daisy(134, vine_y, 11.5, flowers[1][2], flowers[1][0], flowers[1][1], rng, rot=40 + variant * 11)
    body += rosebud(90, vine_y, 8.6, "pink" if variant % 2 else "coral", rng)
    for kx, ky, fam in ((14, 55, "gold"), (68, 58, "lilac"), (112, 27, "blue"), (166, 55, "gold"), (6, 30, "coral"), (174, 30, "pink")):
        body += french_knot(kx, ky, 2.3, fam)
    body += scallop_edge(TILE_W, 67.0, "gold", rng, period=14.0, depth=3.0)
    return svg_doc(TILE_W, TILE_H, body)


CORNER = 260.0  # 26 mm


def corner_tile(variant: int = 0) -> str:
    """A botanical corner: curling vines, a full bloom and a spray of small flowers."""
    rng = random.Random(77 + variant)
    b = ""
    # sweeping vines leaving along both edges so the corner joins the running tiles
    arm_a = [(46 + t * (CORNER - 46), 44 + 12 * math.sin(t * 2 * math.pi) * (1 - t * 0.4) - 2 * t) for t in [i / 30 for i in range(31)]]
    arm_b = [(44 + 12 * math.sin(t * 2 * math.pi) * (1 - t * 0.4) - 2 * t, 46 + t * (CORNER - 46)) for t in [i / 30 for i in range(31)]]
    b += stem_stitch(arm_a, "green", rng, sw=2.3) + stem_stitch(arm_b, "green", rng, sw=2.3)
    # A second strand leaves each arm where the edge tile's twin vines begin, so the join reads as one vine.
    twin_a = [(150 + t * (CORNER - 150), 42 - 7.5 * math.sin(t * math.pi * 2)) for t in [i / 16 for i in range(17)]]
    twin_b = [(42 - 7.5 * math.sin(t * math.pi * 2), 150 + t * (CORNER - 150)) for t in [i / 16 for i in range(17)]]
    b += stem_stitch(twin_a, "sage", rng, sw=1.6) + stem_stitch(twin_b, "sage", rng, sw=1.6)
    spiral = [(84 + (30 - t * 22) * math.cos(t * 7.4), 84 + (30 - t * 22) * math.sin(t * 7.4)) for t in [i / 40 for i in range(41)]]
    b += stem_stitch(spiral, "sage", rng, sw=1.6, step=4.5)
    for x, y, length, wid, angle, fam in (
        (112, 38, 30, 11, -28, "green"), (150, 48, 26, 9, 22, "sage"), (190, 40, 24, 9, -24, "green"), (226, 50, 20, 7, 20, "sage"),
        (38, 112, 30, 11, 118, "sage"), (48, 150, 26, 9, 68, "green"), (40, 190, 24, 9, 114, "sage"), (50, 226, 20, 7, 70, "green"),
        (78, 118, 26, 10, 62, "green"), (118, 78, 26, 10, 28, "sage"), (108, 108, 24, 9, 45, "green"),
    ):
        b += satin_leaf(x, y, length, wid, angle, fam, rng)
    b += lazy_daisy(58, 58, 33, 7, "coral", "gold", rng, rot=12)
    b += lazy_daisy(58, 58, 18, 7, "pink", "gold", rng, rot=38)
    b += lazy_daisy(130, 60, 18, 6, "lilac", "gold", rng, rot=20)
    b += lazy_daisy(60, 130, 18, 6, "blue", "gold", rng, rot=5)
    b += lazy_daisy(196, 64, 13, 5, "pink", "gold", rng, rot=30)
    b += lazy_daisy(64, 196, 13, 5, "lilac", "gold", rng, rot=10)
    b += lazy_daisy(238, 42, 10, 5, "blue", "gold", rng, rot=14)
    b += lazy_daisy(42, 238, 10, 5, "coral", "gold", rng, rot=50)
    b += rosebud(112, 112, 13, "pink", rng)
    b += rosebud(160, 92, 9, "coral", rng)
    b += rosebud(92, 160, 9, "coral", rng)
    for kx, ky, fam in ((90, 24, "gold"), (24, 90, "gold"), (146, 24, "blue"), (24, 146, "lilac"), (138, 122, "gold"), (122, 138, "gold"), (228, 26, "coral"), (26, 228, "pink"), (172, 36, "lilac"), (36, 172, "blue")):
        b += french_knot(kx, ky, 2.8, fam)
    # scalloped lace following the outside of the corner
    outer = group(scallop_edge(CORNER, 15.0, "lilac", rng), "")
    b += outer
    b += group(scallop_edge(CORNER, 15.0, "blue", rng), f"matrix(0 1 1 0 0 0)")
    return svg_doc(CORNER, CORNER, b)


def main() -> int:
    STAMPS.mkdir(parents=True, exist_ok=True)
    EMBROIDERY.mkdir(parents=True, exist_ok=True)
    count = 0
    for character in CHARACTERS:
        for word in PRAISE:
            (STAMPS / f"praise_{word}_{character}.svg").write_text(praise_stamp(character, word), encoding="utf-8")
            count += 1
        (STAMPS / f"perfect_{character}.svg").write_text(perfect_stamp(character), encoding="utf-8")
        count += 1
    for variant in range(4):
        (EMBROIDERY / f"edge_{variant}.svg").write_text(edge_tile(variant), encoding="utf-8")
        count += 1
    (EMBROIDERY / "corner_0.svg").write_text(corner_tile(0), encoding="utf-8")
    count += 1
    print(f"wrote {count} SVG files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
