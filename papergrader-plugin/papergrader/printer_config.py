"""Printer profiles and the photocopy calibration sheet.

A profile records how the teacher's printer is set up. It deliberately starts
with ``physically_verified: false``, and changing an offset resets that flag:
only the teacher can say that a real print landed in the right place.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pymupdf

from .common import MM, PRINTERS_DIR, PaperGraderError, load_json, save_json

DEFAULT_PROFILE = "riso_orphis_gl7430"
PAPER_SIZES_MM = {"A5": (148, 210), "B5": (182, 257), "A4": (210, 297), "B4": (257, 364), "A3": (297, 420), "Letter": (215.9, 279.4)}


def bundled_profile(profile_id: str = DEFAULT_PROFILE) -> dict[str, Any]:
    return load_json(PRINTERS_DIR / f"{profile_id}.json")


def validate_profile(profile: dict[str, Any]) -> list[str]:
    """Reject any profile that would silently break the locked print rules."""
    problems = []
    if profile.get("pdf_order") != "normal":
        problems.append("pdf_order must be 'normal'. PaperGrader never reverses pages automatically.")
    offsets = profile.get("offset_mm", {})
    for axis in ("x", "y"):
        value = offsets.get(axis)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or abs(value) > 25:
            problems.append(f"offset_mm.{axis} must be a number within +/-25 mm.")
    margin = profile.get("safe_margin_mm")
    if not isinstance(margin, (int, float)) or isinstance(margin, bool) or not 0 <= margin <= 30:
        problems.append("safe_margin_mm must be a number from 0 to 30.")
    if not isinstance(profile.get("calibration", {}).get("physically_verified"), bool):
        problems.append("calibration.physically_verified must be true or false.")
    return problems


def load_profile(path: Path) -> dict[str, Any]:
    profile = load_json(path)
    problems = validate_profile(profile)
    if problems:
        raise PaperGraderError(f"{path}: " + " ".join(problems))
    return profile


def set_offsets(path: Path, x_mm: float, y_mm: float) -> dict[str, Any]:
    profile = load_profile(path)
    profile["offset_mm"] = {"x": x_mm, "y": y_mm}
    # New offsets mean the old proof no longer describes this configuration.
    profile["calibration"] = {"physically_verified": False, "confirmed_at": None, "teacher_statement": None}
    if problems := validate_profile(profile):
        raise PaperGraderError(" ".join(problems))
    save_json(path, profile)
    return profile


def confirm_calibration(path: Path, teacher_statement: str) -> dict[str, Any]:
    """Record the teacher's report of a successful physical test. Nothing else may set this."""
    if not teacher_statement.strip():
        raise PaperGraderError("Confirming calibration requires the teacher's own words about the physical test.")
    profile = load_profile(path)
    profile["calibration"] = {
        "physically_verified": True,
        "confirmed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "teacher_statement": teacher_statement.strip(),
    }
    save_json(path, profile)
    return profile


def _crosshair(page: pymupdf.Page, x: float, y: float, color: tuple[float, float, float], size: float = 5 * MM, width: float = 0.5) -> None:
    page.draw_line((x - size, y), (x + size, y), color=color, width=width)
    page.draw_line((x, y - size), (x, y + size), color=color, width=width)
    page.draw_circle((x, y), size * 0.5, color=color, width=width)


def _rulers(page: pymupdf.Page, width: float, height: float, offset: tuple[float, float]) -> None:
    """Millimetre ticks measured from the nominal page edge, along all four sides."""
    ox, oy = offset
    black = (0, 0, 0)
    for mm in range(0, int(width / MM) + 1):
        tick = (6 if mm % 10 == 0 else (4 if mm % 5 == 0 else 2)) * MM
        x = mm * MM + ox
        page.draw_line((x, oy), (x, oy + tick), color=black, width=0.3)
        page.draw_line((x, height + oy), (x, height + oy - tick), color=black, width=0.3)
        if mm % 10 == 0 and 0 < mm:
            page.insert_text((x + 1, oy + 8 * MM), str(mm), fontsize=6, color=black)
    for mm in range(0, int(height / MM) + 1):
        tick = (6 if mm % 10 == 0 else (4 if mm % 5 == 0 else 2)) * MM
        y = mm * MM + oy
        page.draw_line((ox, y), (ox + tick, y), color=black, width=0.3)
        page.draw_line((width + ox, y), (width + ox - tick, y), color=black, width=0.3)
        if mm % 10 == 0 and 0 < mm:
            page.insert_text((ox + 7 * MM, y + 2), str(mm), fontsize=6, color=black)


def build_calibration_pdf(
    out_path: Path,
    paper: str = "A4",
    pages: int = 5,
    profile: Optional[dict[str, Any]] = None,
    size_pt: Optional[tuple[float, float]] = None,
    targets: Optional[dict[int, list[tuple[str, float, float]]]] = None,
    template_pages: int = 1,
) -> Path:
    """Numbered test sheets for checking feed order, face, scale and offsets on photocopies.

    ``targets`` maps a template page to labelled points, so the score box and
    marks of a real test can be checked against a photocopy of its blank.
    """
    if paper not in PAPER_SIZES_MM and size_pt is None:
        raise PaperGraderError(f"Unknown paper size {paper}. Choose from {', '.join(PAPER_SIZES_MM)}.")
    if pages < 1:
        raise PaperGraderError("A calibration test needs at least one page.")
    width, height = size_pt or (PAPER_SIZES_MM[paper][0] * MM, PAPER_SIZES_MM[paper][1] * MM)
    profile = profile or bundled_profile()
    ox, oy = profile["offset_mm"]["x"] * MM, profile["offset_mm"]["y"] * MM
    red = (0.84, 0.04, 0.10)
    doc = pymupdf.open()
    for number in range(1, pages + 1):
        page = doc.new_page(width=width, height=height)
        _rulers(page, width, height, (ox, oy))
        for mx, my in ((20, 20), (width / MM - 20, 20), (20, height / MM - 20), (width / MM - 20, height / MM - 20), (width / MM / 2, height / MM / 2)):
            _crosshair(page, mx * MM + ox, my * MM + oy, red)
            # Labels on the right-hand crosses go to their left, clear of the page edge.
            label_x = mx * MM + ox + (6 * MM if mx < width / MM - 40 else -21 * MM)
            page.insert_text((label_x, my * MM + oy - 2 * MM), f"{mx:g}, {my:g} mm", fontsize=7, color=red)
        page.insert_text((width / 2 - 22 + ox, 72 + oy), "TOP", fontsize=22, color=red)
        page.draw_line((width / 2 + ox + 32, 80 + oy), (width / 2 + ox + 32, 48 + oy), color=red, width=1.4)
        page.draw_line((width / 2 + ox + 32, 48 + oy), (width / 2 + ox + 26, 58 + oy), color=red, width=1.4)
        page.draw_line((width / 2 + ox + 32, 48 + oy), (width / 2 + ox + 38, 58 + oy), color=red, width=1.4)
        page.insert_text((width / 2 - 30 + ox, height / 2 - 30 + oy), str(number), fontsize=72, color=(0.1, 0.1, 0.1))
        lines = [
            f"PHOTOCOPIES ONLY. Calibration sheet {number} of {pages}. PDF page {number} must land on the sheet you numbered {number}.",
            f"Printer: {profile.get('printer', 'unknown')}. Tray: {profile.get('tray', '')}. Paper: {profile.get('paper_face', '')}.",
            f"Print at {profile.get('scale', 'actual size / 100%')}. Reverse Order / 逆順印刷 must be OFF. Offset in this file: X {profile['offset_mm']['x']:+g} mm, Y {profile['offset_mm']['y']:+g} mm.",
            "Measure each cross from the paper edge. Printed 22 mm where the label says 20? New X = current X - 2 (same for Y).",
        ]
        y = height / 2 + 40 + oy
        page.insert_font(fontname="pgcjk", fontbuffer=pymupdf.Font("cjk").buffer)  # embedded, unlike the "japan" alias
        for line in lines:
            page.insert_text((34 * MM / 1.5 + ox, y), line, fontsize=7.5, color=(0.1, 0.1, 0.1), fontname="pgcjk")
            y += 12
        if targets:
            template_page = (number - 1) % template_pages + 1
            for label, tx_pct, ty_pct in targets.get(template_page, []):
                tx, ty = tx_pct * width / 100 + ox, ty_pct * height / 100 + oy
                _crosshair(page, tx, ty, (0.05, 0.3, 0.85), size=3 * MM, width=0.4)
                page.insert_text((tx + 3.4 * MM, ty - 2), label, fontsize=6, color=(0.05, 0.3, 0.85))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.set_metadata({"title": "PaperGrader calibration test: photocopies only", "producer": "PaperGrader"})
    doc.subset_fonts()
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path
