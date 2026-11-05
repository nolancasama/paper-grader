"""Achievement artwork: choosing, placing and proving the stamps and embroidery.

Art comes from the SVG files in ``assets/``. Placement is deterministic per
student, so reprinting never moves anything.

The scan is examined here for one purpose only: finding blank paper, so art
doesn't cover anybody's writing. That reading never touches a grade, and the
award reaching this module has already been decided from recorded judgments.
"""
from __future__ import annotations

import colorsys
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pymupdf

from .common import ASSETS_DIR, MM, PaperGraderError

STAMP_DIR = ASSETS_DIR / "stamps"
EMBROIDERY_DIR = ASSETS_DIR / "embroidery"

CHARACTERS = ("girl", "boy", "cat", "rabbit", "dragon")
PRAISE_WORDS = ("great_job", "excellent", "amazing", "genius")

PRAISE_WIDTH_MM, PRAISE_RATIO = 36.0, 300.0 / 400.0
PERFECT_WIDTH_MM, PERFECT_RATIO = 50.0, 400.0 / 520.0
TILE_W_MM, TILE_H_MM = 18.0, 7.0
CORNER_MM = 26.0
INK_LIMIT_STAMP = 0.012  # share of dark pixels under the art above which a spot isn't blank
INK_LIMIT_TILE = 0.006

_art_cache: dict[str, pymupdf.Document] = {}


def required_assets() -> list[Path]:
    paths = [STAMP_DIR / f"perfect_{c}.svg" for c in CHARACTERS]
    paths += [STAMP_DIR / f"praise_{w}_{c}.svg" for w in PRAISE_WORDS for c in CHARACTERS]
    paths += [EMBROIDERY_DIR / f"edge_{i}.svg" for i in range(4)]
    paths.append(EMBROIDERY_DIR / "corner_0.svg")
    return paths


def _load_art(asset: str) -> pymupdf.Document:
    if asset not in _art_cache:
        path = ASSETS_DIR / asset
        if not path.is_file():
            raise PaperGraderError(f"Artwork file is missing: {path}. The output would lack required decorations.")
        converted = pymupdf.open("svg", path.read_bytes()).convert_to_pdf()
        _art_cache[asset] = pymupdf.open("pdf", converted)
    return _art_cache[asset]


def place_art(page: pymupdf.Page, asset: str, center: tuple[float, float], w: float, h: float, angle_cw: float) -> None:
    """Draw art centred on ``center``, turned clockwise by ``angle_cw`` degrees.

    show_pdf_page turns counter-clockwise and fits the art to the rotated
    bounding box. Both behaviours were measured, and tests cover them.
    """
    a = math.radians(angle_cw)
    box_w = abs(w * math.cos(a)) + abs(h * math.sin(a))
    box_h = abs(w * math.sin(a)) + abs(h * math.cos(a))
    rect = pymupdf.Rect(center[0] - box_w / 2, center[1] - box_h / 2, center[0] + box_w / 2, center[1] + box_h / 2)
    page.show_pdf_page(rect, _load_art(asset), 0, rotate=-angle_cw)


class InkMap:
    """A grayscale rendering of an upright scan page, for finding blank paper."""

    DARK = 170

    def __init__(self, width: int, height: int, gray: bytes, upright_width_pt: float, upright_height_pt: float) -> None:
        self.width = width
        self.height = height
        self.gray = gray
        self.sx = width / upright_width_pt
        self.sy = height / upright_height_pt

    @classmethod
    def empty(cls) -> "InkMap":
        return cls(1, 1, b"\xff", 1.0, 1.0)

    def fraction(self, box: tuple[float, float, float, float]) -> float:
        x0 = max(0, int(box[0] * self.sx))
        x1 = min(self.width, int(math.ceil(box[2] * self.sx)))
        y0 = max(0, int(box[1] * self.sy))
        y1 = min(self.height, int(math.ceil(box[3] * self.sy)))
        if x1 <= x0 or y1 <= y0:
            return 0.0
        dark = 0
        for y in range(y0, y1):
            row = self.gray[y * self.width + x0 : y * self.width + x1]
            dark += sum(1 for value in row if value < self.DARK)
        return dark / ((x1 - x0) * (y1 - y0))


def _unit(seed: str, tag: str) -> float:
    digest = hashlib.sha256(f"{seed}:{tag}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def stamp_variation(seed: str) -> dict[str, float]:
    """Deterministic hand-stamp jitter: 2-6 mm across, 1-4 mm down, 2-7 degrees either way."""

    def signed(tag: str, low: float, high: float) -> float:
        size = low + _unit(seed, tag) * (high - low)
        return size if _unit(seed, tag + "-sign") < 0.5 else -size

    return {
        "dx_mm": signed("dx", 2.0, 6.0),
        "dy_mm": signed("dy", 1.0, 4.0),
        "angle_deg": signed("angle", 2.0, 7.0),
        "scale": 0.97 + _unit(seed, "scale") * 0.06,
    }


def choose_stamp_asset(kind: str, seed: str) -> str:
    character = CHARACTERS[int(_unit(seed, "character") * len(CHARACTERS))]
    if kind == "perfect":
        return f"stamps/perfect_{character}.svg"
    word = PRAISE_WORDS[int(_unit(seed, "word") * len(PRAISE_WORDS))]
    return f"stamps/praise_{word}_{character}.svg"


def _rotated_box(cx: float, cy: float, w: float, h: float, angle_deg: float) -> tuple[float, float, float, float]:
    a = math.radians(angle_deg)
    bw = abs(w * math.cos(a)) + abs(h * math.sin(a))
    bh = abs(w * math.sin(a)) + abs(h * math.cos(a))
    return cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def plan_stamp(
    kind: str,
    seed: str,
    zone: tuple[float, float, float, float],
    blockers: list[tuple[float, float, float, float]],
    ink: InkMap,
) -> Optional[dict]:
    """Find a position inside ``zone``, shrinking the jitter before shrinking the stamp.

    Returns None when nothing fits. The caller treats that as a blocking defect:
    a stamp that doesn't fit is reported, never dropped quietly.
    """
    variation = stamp_variation(seed)
    base_w = (PERFECT_WIDTH_MM if kind == "perfect" else PRAISE_WIDTH_MM) * MM * variation["scale"]
    ratio = PERFECT_RATIO if kind == "perfect" else PRAISE_RATIO
    cx0, cy0 = (zone[0] + zone[2]) / 2, (zone[1] + zone[3]) / 2
    for size in (1.0, 0.9, 0.8):
        w, h = base_w * size, base_w * size * ratio
        for factor in (1.0, 0.75, 0.5, 0.25, 0.0):
            cx = cx0 + variation["dx_mm"] * MM * factor
            cy = cy0 + variation["dy_mm"] * MM * factor
            angle = variation["angle_deg"] * factor
            box = _rotated_box(cx, cy, w, h, angle)
            if box[0] < zone[0] or box[1] < zone[1] or box[2] > zone[2] or box[3] > zone[3]:
                continue
            if any(_overlaps(box, blocker) for blocker in blockers):
                continue
            if ink.fraction(box) > INK_LIMIT_STAMP:
                continue
            return {
                "kind": kind, "asset": choose_stamp_asset(kind, seed), "cx": cx, "cy": cy, "w": w, "h": h, "angle_cw": angle,
                "box": list(box), "variation_factor": factor, "size_factor": size,
            }
    return None


def _edge_tiles(page_w: float, page_h: float, margin: float, scale: float, corners: dict[str, float]) -> list[dict]:
    """Run motifs between whatever corners actually fit, so a small corner leaves no gap.

    ``corners`` holds each corner's real size, 0 if it was dropped. At a dropped
    corner the horizontal run carries on to the page margin and the vertical run
    stops just short of it, so the two meet instead of overlapping.
    """
    band = TILE_H_MM * MM * scale
    tl, tr, br, bl = corners["top-left"], corners["top-right"], corners["bottom-right"], corners["bottom-left"]
    top_start, top_end = margin + tl, page_w - margin - tr
    bottom_start, bottom_end = margin + bl, page_w - margin - br
    right_start, right_end = margin + (tr or band), page_h - margin - (br or band)
    left_start, left_end = margin + (tl or band), page_h - margin - (bl or band)
    runs = (
        ("top", top_end - top_start, lambda p, h: (top_start + p, margin + h / 2), 0),
        ("right", right_end - right_start, lambda p, h: (page_w - margin - h / 2, right_start + p), 90),
        ("bottom", bottom_end - bottom_start, lambda p, h: (bottom_end - p, page_h - margin - h / 2), 180),
        ("left", left_end - left_start, lambda p, h: (margin + h / 2, left_end - p), 270),
    )
    tiles: list[dict] = []
    index = 0
    for edge, length, place, angle in runs:
        if length <= band:
            continue
        count = max(1, round(length / (TILE_W_MM * MM * scale)))
        w = length / count
        h = w * TILE_H_MM / TILE_W_MM
        for i in range(count):
            cx, cy = place((i + 0.5) * w, h)
            tiles.append({"edge": edge, "asset": f"embroidery/edge_{index % 4}.svg", "cx": cx, "cy": cy, "w": w, "h": h, "angle_cw": angle, "box": list(_rotated_box(cx, cy, w, h, angle))})
            index += 1
    return tiles


def plan_embroidery(
    page_w: float,
    page_h: float,
    blockers: list[tuple[float, float, float, float]],
    ink: InkMap,
    safe_margin_mm: float,
    seed: str,
) -> dict:
    """Lay motifs around the page, dropping any that would touch worksheet content.

    Tries a narrower band when a page's margins are tight, keeping the first
    scale where most motifs fit. Too few survivors comes back as ``sufficient:
    False``, which blocks printing; a thin stub never passes for the border.
    """
    margin = safe_margin_mm * MM
    best: Optional[dict] = None
    for scale in (1.0, 0.85, 0.7):
        corner_tiles: list[dict] = []
        corner_sizes: dict[str, float] = {}
        corners = (
            (margin, margin, 0, "top-left"),
            (page_w - margin, margin, 90, "top-right"),
            (page_w - margin, page_h - margin, 180, "bottom-right"),
            (margin, page_h - margin, 270, "bottom-left"),
        )
        for ax, ay, angle, name in corners:
            corner_sizes[name] = 0.0
            for shrink in (1.0, 0.75, 0.55):
                size = CORNER_MM * MM * scale * shrink
                sx = -1 if ax > page_w / 2 else 1
                sy = -1 if ay > page_h / 2 else 1
                cx, cy = ax + sx * size / 2, ay + sy * size / 2
                box = _rotated_box(cx, cy, size, size, angle)
                if _blocked(box, blockers) or ink.fraction(box) > INK_LIMIT_TILE * 2:
                    continue
                corner_tiles.append({"edge": name, "asset": "embroidery/corner_0.svg", "cx": cx, "cy": cy, "w": size, "h": size, "angle_cw": angle, "box": list(box)})
                corner_sizes[name] = size
                break
        corners_kept = len(corner_tiles)
        planned = _edge_tiles(page_w, page_h, margin, scale, corner_sizes)
        kept = corner_tiles + [t for t in planned if not _blocked(tuple(t["box"]), blockers) and ink.fraction(tuple(t["box"])) <= INK_LIMIT_TILE]
        planned_count = len(planned) + 4
        sides = sorted({t["edge"] for t in kept if t["edge"] in ("top", "right", "bottom", "left")})
        result = {
            "tiles": kept, "planned": planned_count, "kept": len(kept), "corners": corners_kept, "sides": sides, "scale": scale,
            "safe_margin_mm": safe_margin_mm, "sufficient": len(kept) >= planned_count * 0.5 and len(sides) >= 3 and corners_kept >= 2,
        }
        if best is None or len(kept) / planned_count > best["kept"] / best["planned"]:
            best = result
        if result["sufficient"] and len(kept) >= planned_count * 0.7:
            return result
    assert best is not None
    return best


def _blocked(box: tuple[float, float, float, float], blockers: list[tuple[float, float, float, float]]) -> bool:
    return any(_overlaps(box, blocker) for blocker in blockers)


# ---------------------------------------------------------------------------
# Proof that the art really is on the page, measured from rendered output
# ---------------------------------------------------------------------------
@dataclass
class ColorReport:
    coverage: float
    families: int
    red_share: float


def ink_coverage(samples: bytes, width: int, height: int, zoom: float, box: tuple[float, float, float, float]) -> float:
    """Share of a region with ink on it. Much faster than analyze_region when hue doesn't matter."""
    x0, y0 = max(0, int(box[0] * zoom)), max(0, int(box[1] * zoom))
    x1, y1 = min(width, int(math.ceil(box[2] * zoom))), min(height, int(math.ceil(box[3] * zoom)))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inked = 0
    for y in range(y0, y1):
        start = (y * width + x0) * 4 + 3
        inked += sum(1 for alpha in samples[start : (y * width + x1) * 4 : 4] if alpha >= 96)
    return inked / ((x1 - x0) * (y1 - y0))


def analyze_region(samples: bytes, width: int, height: int, zoom: float, box: tuple[float, float, float, float]) -> ColorReport:
    """Measure inked coverage and thread colour variety in an RGBA rendering."""
    x0, y0 = max(0, int(box[0] * zoom)), max(0, int(box[1] * zoom))
    x1, y1 = min(width, int(math.ceil(box[2] * zoom))), min(height, int(math.ceil(box[3] * zoom)))
    if x1 <= x0 or y1 <= y0:
        return ColorReport(0.0, 0, 0.0)
    inked = 0
    bins = [0] * 12
    colored = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * width + x) * 4
            alpha = samples[i + 3]
            if alpha < 96:
                continue
            inked += 1
            # RGBA from MuPDF is premultiplied; undo it before judging the hue.
            r, g, b = samples[i] * 255 / alpha, samples[i + 1] * 255 / alpha, samples[i + 2] * 255 / alpha
            hue, sat, val = colorsys.rgb_to_hsv(min(r, 255) / 255, min(g, 255) / 255, min(b, 255) / 255)
            if sat >= 0.18 and val >= 0.25:
                bins[int(hue * 12) % 12] += 1
                colored += 1
    total = (x1 - x0) * (y1 - y0)
    families = sum(1 for count in bins if colored and count / colored >= 0.02)
    red = (bins[0] + bins[11]) / colored if colored else 0.0
    return ColorReport(inked / total, families, red)
