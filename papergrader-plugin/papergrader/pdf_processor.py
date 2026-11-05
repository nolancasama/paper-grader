"""PDF mechanics: inventory, rendering, crops, grids and page-map proposals.

No function here reads an answer. Rendering exists so someone can look at a page.
Pages always go through rendered pixels instead of show_pdf_page, because
show_pdf_page ignores a source page's /Rotate flag (measured, and covered by a
test) and that would silently misalign the preview on rotated scans.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Optional

import pymupdf

from . import SCHEMA_VERSION
from .common import PaperGraderError, sha256_file
from .decorations import InkMap


def inventory_pdf(path: Path) -> dict:
    """Facts about a PDF: page sizes, stored rotation, and whether it holds images or text."""
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # PyMuPDF raises several types for broken files
        raise PaperGraderError(f"Can't open {path}: {exc}") from exc
    with doc:
        pages = []
        for index, page in enumerate(doc):
            pages.append({
                "page": index + 1,
                "width_pt": round(page.rect.width, 3),
                "height_pt": round(page.rect.height, 3),
                "stored_rotation": page.rotation,
                "image_count": len(page.get_images()),
                "has_text_layer": bool(page.get_text().strip()),
            })
        return {"file": path.name, "sha256": sha256_file(path), "page_count": len(pages), "pages": pages}


def _upright_pixmap(page: pymupdf.Page, rotation: int, dpi: int) -> pymupdf.Pixmap:
    zoom = dpi / 72.0
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom).prerotate(rotation), alpha=False)


def _grid_step(span_pct: float) -> float:
    for step in (0.5, 1.0, 2.0, 5.0, 10.0):
        if span_pct / step <= 12:
            return step
    return 20.0


def render_view(
    pdf_path: Path,
    page_number: int,
    rotation: int,
    out_path: Path,
    dpi: int = 200,
    rect_pct: Optional[tuple[float, float, float, float]] = None,
    zoom: float = 1.0,
    grid: bool = False,
) -> dict:
    """Save an upright view of a page or a crop, with an optional percent grid.

    The grid labels use the same x_pct / y_pct system as the grading records, so
    a position read off an image can go straight into the JSON.
    """
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise PaperGraderError(f"{pdf_path.name} has no page {page_number}.")
        pix = _upright_pixmap(doc[page_number - 1], rotation, dpi)
    px_per_pt = dpi / 72.0
    width_pt, height_pt = pix.width / px_per_pt, pix.height / px_per_pt
    x, y, w, h = rect_pct or (0.0, 0.0, 100.0, 100.0)
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 100.001 or y + h > 100.001:
        raise PaperGraderError(f"Crop {rect_pct} isn't inside the page (use percentages from 0 to 100).")

    # Compose on a clean upright page, so crop maths never involves the scan's rotation.
    canvas = pymupdf.open()
    sheet = canvas.new_page(width=width_pt, height=height_pt)
    sheet.insert_image(sheet.rect, pixmap=pix)
    clip = pymupdf.Rect(x * width_pt / 100, y * height_pt / 100, (x + w) * width_pt / 100, (y + h) * height_pt / 100)
    if grid:
        _draw_grid(sheet, clip, width_pt, height_pt, zoom, px_per_pt, (x, y, w, h))
    out_scale = px_per_pt * zoom
    result = sheet.get_pixmap(matrix=pymupdf.Matrix(out_scale, out_scale), clip=clip, alpha=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(out_path)
    canvas.close()
    return {"file": out_path.name, "width_px": result.width, "height_px": result.height, "dpi": dpi, "zoom": zoom, "rect_pct": [x, y, w, h], "grid": grid}


def _draw_grid(sheet: pymupdf.Page, clip: pymupdf.Rect, width_pt: float, height_pt: float, zoom: float, px_per_pt: float, rect: tuple[float, float, float, float]) -> None:
    """Thin blue lines with percent labels, on the temporary view only. Never reaches a print file."""
    x, y, w, h = rect
    color = (0.05, 0.3, 0.85)
    pts_per_output_px = 1.0 / (px_per_pt * zoom)
    label = max(5.0, 13 * pts_per_output_px)
    line = max(0.15, 0.9 * pts_per_output_px)
    for axis, start, span, full in (("x", x, w, width_pt), ("y", y, h, height_pt)):
        step = _grid_step(span)
        value = (int(start / step) + (0 if start % step == 0 else 1)) * step
        while value <= start + span + 1e-6:
            if axis == "x":
                px = value * full / 100
                sheet.draw_line((px, clip.y0), (px, clip.y1), color=color, width=line)
                sheet.insert_text((px + label * 0.2, clip.y0 + label * 1.05), f"{value:g}", fontsize=label, color=color)
            else:
                py = value * full / 100
                sheet.draw_line((clip.x0, py), (clip.x1, py), color=color, width=line)
                sheet.insert_text((clip.x0 + label * 0.2, py - label * 0.15), f"{value:g}", fontsize=label, color=color)
            value += step


def page_jpeg(pdf_path: Path, page_number: int, dpi: int = 150, quality: int = 82) -> bytes:
    """The page as displayed (honouring /Rotate), for the preview background."""
    with pymupdf.open(pdf_path) as doc:
        zoom = dpi / 72.0
        pix = doc[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("jpeg", jpg_quality=quality)


def ink_map(pdf_path: Path, page_number: int, rotation: int, dpi: int = 72) -> InkMap:
    """Upright grayscale, used only to keep decorations off existing writing."""
    with pymupdf.open(pdf_path) as doc:
        page = doc[page_number - 1]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom).prerotate(rotation), colorspace=pymupdf.csGRAY, alpha=False)
        return InkMap(pix.width, pix.height, bytes(pix.samples), pix.width / zoom, pix.height / zoom)


def page_fingerprint(pdf_path: Path, page_number: int) -> Optional[str]:
    """Hash a low-resolution rendering, to detect a page scanned or copied twice.

    Identity only, never grading. Returns None for an empty page: blank sheets and
    blank duplex backs legitimately look alike, so they aren't duplicates.
    """
    with pymupdf.open(pdf_path) as doc:
        pix = doc[page_number - 1].get_pixmap(dpi=40, colorspace=pymupdf.csGRAY, alpha=False)
        samples = bytes(pix.samples)
        if min(samples) > 200:
            return None
        return hashlib.sha256(samples).hexdigest()


def propose_page_map(
    source_paths: Iterable[Path],
    class_id: str,
    class_label: str,
    test_id: str,
    test_version: str,
    template_pages: int,
    excluded: Optional[dict[str, dict[int, str]]] = None,
    paper_mode: str = "simplex",
) -> dict:
    """Group student pages into packets, keeping scan order.

    This is a proposal, not a finding. Every rotation starts unconfirmed, and the
    validator refuses to build until someone has looked at each page.
    """
    excluded = excluded or {}
    sources = []
    slots = []
    student_pages = 0
    sheet = 0
    for path in source_paths:
        info = inventory_pdf(path)
        skip = excluded.get(path.name, {})
        sources.append({
            "file": path.name, "sha256": info["sha256"], "page_count": info["page_count"],
            "excluded_pages": [{"page": page, "role": role} for page, role in sorted(skip.items())],
        })
        for page in info["pages"]:
            if page["page"] in skip:
                continue
            order = student_pages // template_pages + 1
            in_packet = student_pages % template_pages + 1
            # Odd packet pages start a new sheet in duplex. Simplex uses one sheet per page.
            side = "back" if paper_mode == "duplex" and in_packet % 2 == 0 else "front"
            if side == "front":
                sheet += 1
            student_pages += 1
            slots.append({
                "slot": student_pages, "kind": "scan", "student_order": order, "page_in_packet": in_packet, "template_page": in_packet,
                "physical_sheet": sheet, "side": side, "source_pdf": path.name, "source_page": page["page"], "scan_rotation": 0,
                "rotation_status": "unconfirmed", "content_offset_pct": {"dx": 0, "dy": 0},
                "page_width_pt": page["width_pt"], "page_height_pt": page["height_pt"],
            })
    return {
        "schema_version": SCHEMA_VERSION, "class_id": class_id, "class_label": class_label, "test_id": test_id, "test_version": test_version,
        "paper_mode": paper_mode, "sources": sources, "slots": slots,
    }


