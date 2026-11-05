"""Plan and draw correction overlays. Mechanics only; never a grading judgment.

Every position starts in *upright* coordinates: the worksheet as a person reads
it. ``PageFrame`` maps those onto the scan's own orientation, because the paper
goes back through the printer the way it was scanned. An upside-down scan needs
upside-down marks.

All marks are vector paths, and the page has no background. A correction page
therefore contains no text objects and no images at all, which is what lets the
validator reject any text or scan that turns up on one.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import pymupdf

from . import decorations
from .common import MM, Issues
from .grading_models import Outcome, PageMap, Rect, Slot, TestDefinition, Grading, format_points

RED = (0.84, 0.04, 0.10)
Point = tuple[float, float]


@dataclass(frozen=True)
class PageFrame:
    """Maps upright worksheet points onto a scan page's displayed orientation.

    ``rotation`` is how far the displayed scan must turn clockwise to be upright.
    """

    width: float
    height: float
    rotation: int = 0

    @property
    def upright_width(self) -> float:
        return self.height if self.rotation in (90, 270) else self.width

    @property
    def upright_height(self) -> float:
        return self.width if self.rotation in (90, 270) else self.height

    def to_display(self, u: float, v: float) -> Point:
        if self.rotation == 0:
            return u, v
        if self.rotation == 180:
            return self.width - u, self.height - v
        if self.rotation == 90:
            return v, self.height - u
        return self.width - v, u  # 270

    def pct(self, x_pct: float, y_pct: float) -> Point:
        return x_pct * self.upright_width / 100.0, y_pct * self.upright_height / 100.0

    def rect_pts(self, rect: Rect, dx_pct: float = 0.0, dy_pct: float = 0.0) -> tuple[float, float, float, float]:
        x0, y0 = self.pct(rect.x + dx_pct, rect.y + dy_pct)
        x1, y1 = self.pct(rect.x1 + dx_pct, rect.y1 + dy_pct)
        return x0, y0, x1, y1

    def display_bbox(self, box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        corners = [self.to_display(box[i], box[j]) for i, j in ((0, 1), (2, 1), (2, 3), (0, 3))]
        xs, ys = zip(*corners)
        return min(xs), min(ys), max(xs), max(ys)


def frame_for_slot(slot: Slot) -> PageFrame:
    return PageFrame(slot.page_width_pt, slot.page_height_pt, slot.scan_rotation)


# ---------------------------------------------------------------------------
# Hand-drawn strokes
# ---------------------------------------------------------------------------
def _chaikin(points: list[Point], rounds: int = 3) -> list[Point]:
    """Round a polyline while keeping its end points, like a pen moving at speed."""
    for _ in range(rounds):
        if len(points) < 3:
            return points
        out = [points[0]]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            out.append((x0 * 0.75 + x1 * 0.25, y0 * 0.75 + y1 * 0.25))
            out.append((x0 * 0.25 + x1 * 0.75, y0 * 0.25 + y1 * 0.75))
        out.append(points[-1])
        points = out
    return points


# Pen strokes for a teacher-style numeral, in a box 1 wide and 1 tall. These are
# vector paths, so no font or text object ever reaches the correction page.
DIGIT_STROKES: dict[str, list[list[Point]]] = {
    "0": [[(0.52, 0.02), (0.14, 0.14), (0.06, 0.55), (0.24, 0.96), (0.62, 0.98), (0.92, 0.6), (0.86, 0.18), (0.48, 0.0)]],
    "1": [[(0.26, 0.24), (0.54, 0.02), (0.54, 1.0)]],
    "2": [[(0.1, 0.28), (0.26, 0.04), (0.64, 0.0), (0.86, 0.24), (0.66, 0.56), (0.08, 1.0), (0.08, 1.0), (0.94, 0.96)]],
    "3": [[(0.12, 0.14), (0.46, 0.0), (0.82, 0.12), (0.76, 0.38), (0.42, 0.48), (0.42, 0.48), (0.86, 0.6), (0.84, 0.88), (0.48, 1.0), (0.08, 0.86)]],
    "4": [[(0.66, 0.0), (0.66, 0.0), (0.06, 0.68), (0.06, 0.68), (0.96, 0.68)], [(0.68, 0.34), (0.68, 1.0)]],
    "5": [[(0.82, 0.02), (0.82, 0.02), (0.22, 0.04), (0.22, 0.04), (0.16, 0.44), (0.16, 0.44), (0.6, 0.38), (0.9, 0.62), (0.76, 0.92), (0.4, 1.0), (0.08, 0.86)]],
    "6": [[(0.76, 0.02), (0.34, 0.2), (0.12, 0.62), (0.28, 0.96), (0.66, 0.98), (0.88, 0.72), (0.66, 0.46), (0.3, 0.48), (0.13, 0.66)]],
    "7": [[(0.08, 0.04), (0.08, 0.04), (0.92, 0.02), (0.92, 0.02), (0.4, 1.0)]],
    "8": [[(0.72, 0.14), (0.48, 0.0), (0.2, 0.14), (0.3, 0.4), (0.7, 0.58), (0.84, 0.82), (0.5, 1.0), (0.16, 0.82), (0.3, 0.58), (0.7, 0.4), (0.78, 0.18), (0.56, 0.0)]],
    "9": [[(0.82, 0.3), (0.56, 0.02), (0.2, 0.08), (0.14, 0.38), (0.44, 0.52), (0.82, 0.3), (0.82, 0.3), (0.76, 0.7), (0.56, 1.0)]],
    ".": [[(0.46, 0.92), (0.54, 0.98), (0.46, 0.98), (0.46, 0.92)]],
    "/": [[(0.86, 0.0), (0.14, 1.0)]],
}


def digit_paths(text: str, x: float, y: float, height: float) -> list[list[Point]]:
    """Smoothed strokes for ``text``, with its top left at (x, y)."""
    glyph_w = height * 0.62
    gap = height * 0.1
    strokes: list[list[Point]] = []
    cursor = x
    for char in text:
        width = glyph_w * (0.45 if char == "." else 1.0)
        for stroke in DIGIT_STROKES[char]:
            strokes.append([(cursor + px * width, y + py * height) for px, py in _chaikin(list(stroke))])
        cursor += width + gap
    return strokes


def digits_width(text: str, height: float) -> float:
    glyph_w = height * 0.62
    gap = height * 0.1
    return sum(glyph_w * (0.45 if c == "." else 1.0) for c in text) + gap * max(0, len(text) - 1)


def _wobble(key: str) -> Callable[[int], float]:
    seed = hashlib.sha256(key.encode("utf-8")).digest()

    def value(i: int) -> float:
        return seed[i % len(seed)] / 255.0 * 2 - 1

    return value


def mark_paths(symbol: str, cx: float, cy: float, size: float, key: str) -> list[list[Point]]:
    """Strokes for a red mark. The wobble is seeded, so a rebuild draws it identically."""
    wob = _wobble(key)
    r = size / 2.0
    if symbol == "correct":  # ○, drawn with a small overlap where the pen closes the loop
        start = -2.0 + wob(0) * 0.3
        steps = 44
        points = []
        for i in range(steps + 1):
            t = i / steps
            a = start + t * (2 * math.pi + 0.28)
            rr = r * (1 + 0.035 * wob(1) * math.sin(a * 2 + wob(2)) + 0.05 * t)
            points.append((cx + rr * math.cos(a), cy + rr * 0.96 * math.sin(a)))
        return [points]
    if symbol == "partial":  # △
        top = (cx + wob(0) * r * 0.05, cy - r)
        right = (cx + r * 0.98, cy + r * 0.8)
        left = (cx - r * 0.98, cy + r * 0.8)
        return [[top, top, right, right, left, left, (top[0] - r * 0.04, top[1] - r * 0.03)]]
    if symbol == "incorrect":  # ×
        s = r * 0.86
        return [
            [(cx - s, cy - s + wob(0) * r * 0.06), (cx + wob(1) * r * 0.05, cy), (cx + s, cy + s)],
            [(cx + s, cy - s + wob(2) * r * 0.06), (cx + wob(3) * r * 0.05, cy), (cx - s, cy + s)],
        ]
    raise ValueError(f"No correction mark exists for '{symbol}'.")


def draw_strokes(shape: pymupdf.Shape, strokes: Iterable[list[Point]], width: float, color: tuple[float, float, float], map_point: Callable[[float, float], Point]) -> None:
    for stroke in strokes:
        smooth = _chaikin(list(stroke), 2)
        shape.draw_polyline([pymupdf.Point(*map_point(x, y)) for x, y in smooth])
        shape.finish(color=color, width=width, lineCap=1, lineJoin=1, closePath=False, fill=None)


# ---------------------------------------------------------------------------
# Planning: decide everything first, as data, then draw it twice
# ---------------------------------------------------------------------------
def _pad(box: tuple[float, float, float, float], amount: float) -> tuple[float, float, float, float]:
    return box[0] - amount, box[1] - amount, box[2] + amount, box[3] + amount


def plan_class(
    test: TestDefinition,
    page_map: PageMap,
    grading: Grading,
    outcomes: dict[int, Outcome],
    ink_for_slot: Callable[[Slot], decorations.InkMap],
    safe_margin_mm: float,
    issues: Issues,
) -> list[dict]:
    """Return one plan per slot. Pending answers simply have no mark entry."""
    plans: list[dict] = []
    students = {s.student_order: s for s in grading.students}
    for slot in page_map.slots:
        frame = frame_for_slot(slot)
        plan: dict = {
            "slot": slot.slot,
            "student_order": slot.student_order,
            "page_in_packet": slot.page_in_packet,
            "template_page": slot.template_page,
            "page_width_pt": slot.page_width_pt,
            "page_height_pt": slot.page_height_pt,
            "rotation": slot.scan_rotation,
            "marks": [],
            "score": None,
            "stamp": None,
            "embroidery": None,
        }
        plans.append(plan)
        student = students.get(slot.student_order)
        outcome = outcomes.get(slot.student_order)
        if slot.kind == "blank_filler" or student is None or outcome is None:
            continue

        dx, dy = slot.offset_dx_pct, slot.offset_dy_pct
        blockers: list[tuple[float, float, float, float]] = []
        for question in test.questions:
            if question.template_page != slot.template_page:
                continue
            blockers.append(frame.rect_pts(question.answer_region, dx, dy))
            answer = student.answer(question.id)
            if answer is None or answer.decision == "pending":
                continue  # the mark stays unprinted: never a '?', never a label
            mx, my = answer.mark if answer.mark else question.mark_anchor
            mx, my = mx + dx, my + dy
            if not question.answer_region.contains(mx - dx, my - dy, tolerance=2.0):
                issues.error(
                    "mark_outside_answer_region",
                    f"Student {slot.student_order} question {question.id}: the mark at ({mx - dx:.1f}%, {my - dy:.1f}%) lies outside its answer region.",
                    f"slot {slot.slot}",
                )
            u, v = frame.pct(mx, my)
            size = question.mark_size_mm * MM
            plan["marks"].append(
                {"question_id": question.id, "symbol": answer.decision, "u": u, "v": v, "size_pt": size,
                 "box": _pad((u - size / 2, v - size / 2, u + size / 2, v + size / 2), 2.0)}
            )
            blockers.append(plan["marks"][-1]["box"])
        for zone in test.protected_regions:
            if zone.template_page == slot.template_page:
                blockers.append(frame.rect_pts(zone.rect, dx, dy))

        if slot.template_page != test.score_box.template_page:
            continue

        score_box = frame.rect_pts(test.score_box.rect, dx, dy)
        blockers.append(score_box)
        if outcome.resolved and outcome.total is not None:
            text = format_points(outcome.total)
            if test.score_box.append_denominator:
                text += "/" + format_points(test.max_points)
            plan["score"] = {"text": text, "box": score_box}
        if outcome.award == "none":
            continue

        ink = ink_for_slot(slot)
        zone = test.stamp_zone
        if outcome.award == "perfect" and test.perfect_stamp_zone:
            zone = test.perfect_stamp_zone
        zone_rect = student.stamp_zone or zone.rect
        seed = f"{test.test_id}|{test.test_version}|{page_map.class_id}|{slot.student_order}"
        stamp = decorations.plan_stamp(outcome.award, seed, frame.rect_pts(zone_rect, dx, dy), blockers, ink)
        if stamp is None:
            issues.error(
                "stamp_no_safe_position",
                f"Student {slot.student_order} earned a stamp, but no position in the stamp zone stays clear of answers and printed content. Move stamp_zone for this student.",
                f"slot {slot.slot}",
            )
        else:
            plan["stamp"] = stamp
            blockers.append(tuple(stamp["box"]))
            if stamp["variation_factor"] == 0:
                issues.warning("stamp_variation_removed", f"Student {slot.student_order}'s stamp had to sit dead centre to stay clear of other content.", f"slot {slot.slot}")
        if outcome.award == "perfect":
            border = decorations.plan_embroidery(frame.upright_width, frame.upright_height, blockers, ink, safe_margin_mm, seed)
            plan["embroidery"] = border
            if not border["sufficient"]:
                issues.error(
                    "embroidery_no_safe_area",
                    f"Student {slot.student_order} earned the embroidered border, but only {border['kept']} of {border['planned']} motifs fit without touching page content ({len(border['sides'])} sides). Adjust protected_regions, or tell the teacher this page can't carry the border.",
                    f"slot {slot.slot}",
                )
    return plans


def render_slot(page: pymupdf.Page, plan: dict, printer_offset_pt: Point = (0.0, 0.0), skip_embroidery: bool = False, skip_stamp: bool = False) -> None:
    """Draw one slot's plan. The offset applies only to the printable correction PDF."""
    frame = PageFrame(plan["page_width_pt"], plan["page_height_pt"], plan["rotation"])
    ox, oy = printer_offset_pt

    def to_page(u: float, v: float) -> Point:
        x, y = frame.to_display(u, v)
        return x + ox, y + oy

    # Decorations go first, so the red marks and score always sit on top.
    if plan["embroidery"] and not skip_embroidery:
        for tile in plan["embroidery"]["tiles"]:
            decorations.place_art(page, tile["asset"], to_page(tile["cx"], tile["cy"]), tile["w"], tile["h"], tile["angle_cw"] - frame.rotation)
    if plan["stamp"] and not skip_stamp:
        stamp = plan["stamp"]
        decorations.place_art(page, stamp["asset"], to_page(stamp["cx"], stamp["cy"]), stamp["w"], stamp["h"], stamp["angle_cw"] - frame.rotation)

    shape = page.new_shape()
    for mark in plan["marks"]:
        strokes = mark_paths(mark["symbol"], mark["u"], mark["v"], mark["size_pt"], f"{plan['slot']}:{mark['question_id']}")
        draw_strokes(shape, strokes, max(1.5, mark["size_pt"] * 0.075), RED, to_page)
    if plan["score"]:
        box = plan["score"]["box"]
        text = plan["score"]["text"]
        box_w, box_h = box[2] - box[0], box[3] - box[1]
        height = box_h * 0.72
        width = digits_width(text, height)
        if width > box_w * 0.92:
            height *= box_w * 0.92 / width
            width = digits_width(text, height)
        x = box[0] + (box_w - width) / 2
        y = box[1] + (box_h - height) / 2
        draw_strokes(shape, digit_paths(text, x, y, height), max(1.5, height * 0.085), RED, to_page)
    shape.commit()


def planned_rects(plan: dict) -> dict[str, list[tuple[float, float, float, float]]]:
    """Each planned element's display-space rectangle, without any printer offset."""
    frame = PageFrame(plan["page_width_pt"], plan["page_height_pt"], plan["rotation"])
    out: dict[str, list[tuple[float, float, float, float]]] = {"marks": [], "score": [], "stamp": [], "embroidery": []}
    for mark in plan["marks"]:
        out["marks"].append(frame.display_bbox(tuple(mark["box"])))
    if plan["score"]:
        out["score"].append(frame.display_bbox(tuple(plan["score"]["box"])))
    if plan["stamp"]:
        out["stamp"].append(frame.display_bbox(tuple(plan["stamp"]["box"])))
    if plan["embroidery"]:
        for tile in plan["embroidery"]["tiles"]:
            out["embroidery"].append(frame.display_bbox(tuple(tile["box"])))
    return out


def build_correction_pdf(plans: list[dict], printer_offset_mm: tuple[float, float] = (0.0, 0.0), metadata_title: str = "", skip_embroidery: bool = False, skip_stamp: bool = False) -> pymupdf.Document:
    """One page per slot, in normal order. A slot with nothing to print stays an empty page."""
    doc = pymupdf.open()
    offset = (printer_offset_mm[0] * MM, printer_offset_mm[1] * MM)
    for plan in plans:
        page = doc.new_page(width=plan["page_width_pt"], height=plan["page_height_pt"])
        render_slot(page, plan, offset, skip_embroidery, skip_stamp)
    doc.set_metadata({"title": metadata_title, "producer": "PaperGrader", "creator": "PaperGrader"})
    return doc


def build_preview_pdf(plans: list[dict], slot_images: Callable[[int], Optional[bytes]], metadata_title: str = "") -> pymupdf.Document:
    """Scan plus overlay, always without the printer offset: this shows the intended result."""
    doc = pymupdf.open()
    for plan in plans:
        page = doc.new_page(width=plan["page_width_pt"], height=plan["page_height_pt"])
        image = slot_images(plan["slot"])
        if image:
            page.insert_image(page.rect, stream=image, keep_proportion=False)
        render_slot(page, plan)
    doc.set_metadata({"title": metadata_title, "producer": "PaperGrader", "creator": "PaperGrader"})
    return doc
