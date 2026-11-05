"""Synthetic worksheets, scans and grades, for tests and the end-to-end demonstration.

Everything is invented. Handwriting is drawn as pen strokes and flattened into a
raster image, so these "scans" have no text layer, just like real ones.

The grades below are typed in by hand as the fixture's known truth, and they are
labelled ``synthetic_fixture``. Python doesn't read these pages to produce them.
This demonstrates the PDF and validation pipeline, not visual grading accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pymupdf

from . import SCHEMA_VERSION
from .common import MM, save_json, sha256_file
from .correction_overlay import digit_paths, draw_strokes
from .job import Job, source_pages_for
from .grading_models import Issues, format_points, parse_page_map
from .common import load_json

A4_W, A4_H = 210 * MM, 297 * MM
PENCIL = (0.13, 0.14, 0.3)
PINK = (0.93, 0.25, 0.5)
PRINTED = (0.05, 0.05, 0.05)
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

Q1_ROWS = [("1.1", "three", "3", 16.0), ("1.2", "seven", "7", 22.0), ("1.3", "one", "1", 28.0), ("1.4", "nine", "9", 34.0), ("1.5", "two", "2", 40.0)]
Q2_ROWS = [("2.1", "a cat", "a dog", "cat", 52.0), ("2.2", "red", "blue", "blue", 58.0)]
Q3_LEFT = [("3.1", "apple", 66.0, "fruit"), ("3.2", "bus", 72.0, "vehicle")]
Q3_RIGHT = [("vehicle", 66.0), ("fruit", 72.0)]


def question_table(template_pages: int = 1) -> list[dict[str, Any]]:
    second = 2 if template_pages == 2 else 1
    questions: list[dict[str, Any]] = []
    for qid, word, digit, y in Q1_ROWS:
        questions.append(_question(qid, 1, "fixed", f"Write the number for '{word}'.", [digit], "The written number must be the accepted digit.", 10, (28, y - 3, 16, 5.6), (36, y - 0.2)))
    for qid, first, other, right, y in Q2_ROWS:
        questions.append(_question(qid, 1, "fixed", f"Circle: {first} / {other}.", [right], "The circled word must be the accepted word.", 10, (10, y - 3, 42, 5.6), (47, y - 0.2)))
    for qid, word, y, target in Q3_LEFT:
        questions.append(_question(qid, second, "matching", f"Match '{word}' to its category.", [f"{word} - {target}"], "Trace the line from its source to its actual destination, including where lines cross.", 10, (30, y - 3, 50, 6), (76, y - 0.2)))
    questions.append(
        _question(
            "4", second, "personal", "Circle your birth month and write its number.", ["Any month whose circled name and written number agree"],
            "Accept any month if the circled month and written number agree. The key's September/9 is only the teacher's example.", 10, (10, 79, 75, 14), (80, 90),
            rationale="This is a personal response, so the student needn't share the teacher's birthday.",
        )
    )
    return questions


def _question(qid: str, page: int, kind: str, prompt: str, accepted: list[str], rule: str, points: int, region: tuple, anchor: tuple, rationale: str = "") -> dict[str, Any]:
    return {
        "id": qid, "template_page": page, "kind": kind, "prompt": prompt, "accepted_answers": accepted, "rule": rule, "rationale": rationale,
        "points": points, "answer_region": {"x_pct": region[0], "y_pct": region[1], "w_pct": region[2], "h_pct": region[3]},
        "mark_anchor": {"x_pct": anchor[0], "y_pct": anchor[1]}, "mark_size_mm": 9.0,
    }


def _text(page: pymupdf.Page, x_pct: float, y_pct: float, text: str, size: float = 12.0, color: tuple = PRINTED, font: str = "helv") -> None:
    page.insert_text((x_pct * A4_W / 100, y_pct * A4_H / 100), text, fontsize=size, color=color, fontname=font)


def draw_printed_page(page: pymupdf.Page, number: int, template_pages: int) -> None:
    """The printed worksheet, with nothing filled in."""
    if number == 1:
        _text(page, 9, 8.2, "English Check-Up", 18, font="hebo")
        _text(page, 9, 11.2, "Class ______    No. ____    Name ____________________", 10.5)
        box = pymupdf.Rect(70 * A4_W / 100, 5.5 * A4_H / 100, 88 * A4_W / 100, 10.5 * A4_H / 100)
        page.draw_rect(box, color=PRINTED, width=1.1)
        page.draw_line((box.x0 + 2, box.y1 - 2), (box.x1 - 2, box.y0 + 2), color=(0.55, 0.55, 0.55), width=0.5)
        _text(page, 81.5, 10.0, "/100", 10)
        _text(page, 9, 14.2, "1. Write the number.", 11, font="hebo")
        for _, word, _digit, y in Q1_ROWS:
            _text(page, 12, y + 0.6, word, 13)
            page.draw_rect(pymupdf.Rect(30 * A4_W / 100, (y - 2.6) * A4_H / 100, 42 * A4_W / 100, (y + 2) * A4_H / 100), color=PRINTED, width=0.8)
        _text(page, 9, 48.6, "2. Circle the right word.", 11, font="hebo")
        for _, first, other, _right, y in Q2_ROWS:
            _text(page, 14, y + 0.6, first, 13)
            _text(page, 33, y + 0.6, other, 13)
    if number == template_pages or template_pages == 1:
        _text(page, 9, 63.2, "3. Draw a line to match.", 11, font="hebo")
        for _, word, y, _target in Q3_LEFT:
            _text(page, 14, y + 0.6, word, 13)
            page.draw_circle((32 * A4_W / 100, y * A4_H / 100), 2, color=PRINTED, fill=PRINTED)
        for word, y in Q3_RIGHT:
            page.draw_circle((58 * A4_W / 100, y * A4_H / 100), 2, color=PRINTED, fill=PRINTED)
            _text(page, 60, y + 0.6, word, 13)
        _text(page, 9, 77.8, "4. Circle your birth month. Write its number.", 11, font="hebo")
        for i, month in enumerate(MONTHS):
            _text(page, 12 + (i % 6) * 12, 82 + (i // 6) * 3.4, month[:3], 11)
        page.draw_rect(pymupdf.Rect(60 * A4_W / 100, 88.4 * A4_H / 100, 74 * A4_W / 100, 91.4 * A4_H / 100), color=PRINTED, width=0.8)
        _text(page, 48, 90.4, "Number:", 10)


def _write_digits(page: pymupdf.Page, text: str, x_pct: float, y_pct: float, height_pt: float = 18.0, color: tuple = PENCIL) -> None:
    x = x_pct * A4_W / 100
    y = y_pct * A4_H / 100 - height_pt / 2
    shape = page.new_shape()
    draw_strokes(shape, digit_paths(text, x, y, height_pt), 1.5, color, lambda a, b: (a, b))
    shape.commit()


def _pen_circle(page: pymupdf.Page, x_pct: float, y_pct: float, width_pt: float, height_pt: float, color: tuple = PENCIL) -> None:
    x, y = x_pct * A4_W / 100, y_pct * A4_H / 100
    page.draw_oval(pymupdf.Rect(x - width_pt / 2, y - height_pt / 2, x + width_pt / 2, y + height_pt / 2), color=color, width=1.2)


def draw_answers(page: pymupdf.Page, number: int, template_pages: int, written: dict[str, str], color: tuple = PENCIL) -> None:
    """Fill in a page by hand. ``written`` maps a question id to what the "student" wrote."""
    if number == 1:
        for qid, _word, _digit, y in Q1_ROWS:
            if written.get(qid):
                _write_digits(page, written[qid], 34, y - 0.2, color=color)
        for qid, first, other, _right, y in Q2_ROWS:
            answer = written.get(qid)
            if answer:
                x = 17.5 if answer in first else 36
                _pen_circle(page, x, y, 62, 22, color)
    if number == template_pages or template_pages == 1:
        destinations = dict(Q3_RIGHT)
        for qid, _word, y, _target in Q3_LEFT:
            answer = written.get(qid)
            if answer:
                page.draw_line((33 * A4_W / 100, y * A4_H / 100), (57.5 * A4_W / 100, destinations[answer] * A4_H / 100), color=color, width=1.2)
        month = written.get("4")
        if month:
            name, _, digit = month.partition("/")
            index = MONTHS.index(name)
            _pen_circle(page, 14.5 + (index % 6) * 12, 81.6 + (index // 6) * 3.4, 34, 16, color)
            _write_digits(page, digit, 64, 90.0, height_pt=16, color=color)


def scanify(page: pymupdf.Page, out: pymupdf.Document, raster_rotation: int = 0, stored_rotation: int = 0, dpi: int = 110) -> None:
    """Flatten a page into a grayscale image-only page, the way a scanner would."""
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom).prerotate(raster_rotation), colorspace=pymupdf.csGRAY, alpha=False)
    swapped = raster_rotation in (90, 270)
    width, height = (page.rect.height, page.rect.width) if swapped else (page.rect.width, page.rect.height)
    new = out.new_page(width=width, height=height)
    new.insert_image(new.rect, pixmap=pix)
    if stored_rotation:
        new.set_rotation(stored_rotation)


@dataclass
class SyntheticStudent:
    name: Optional[str]
    number: Optional[str]
    written: dict[str, str]  # what is physically on the page
    judgments: dict[str, tuple[str, Any]]  # question id -> (decision, points); fixture truth
    raster_rotation: int = 0
    stored_rotation: int = 0
    pending_reason: dict[str, str] = field(default_factory=dict)
    uninspected: bool = False


def _all_correct_written() -> dict[str, str]:
    return {"1.1": "3", "1.2": "7", "1.3": "1", "1.4": "9", "1.5": "2", "2.1": "a cat", "2.2": "blue", "3.1": "fruit", "3.2": "vehicle", "4": "April/4"}


def _judged(overrides: Optional[dict[str, tuple[str, Any]]] = None) -> dict[str, tuple[str, Any]]:
    judged: dict[str, tuple[str, Any]] = {qid: ("correct", 10) for qid in ("1.1", "1.2", "1.3", "1.4", "1.5", "2.1", "2.2", "3.1", "3.2", "4")}
    judged.update(overrides or {})
    return judged


def class_a_students() -> list[SyntheticStudent]:
    """One student per scenario the plan requires."""
    perfect = SyntheticStudent("Aiko Sample", "1", _all_correct_written(), _judged())
    ninety = SyntheticStudent("山田 花子", "2", {**_all_correct_written(), "1.5": "5"}, _judged({"1.5": ("incorrect", 0)}))
    below = SyntheticStudent(
        "Ben Example", "3", {**_all_correct_written(), "1.2": "1", "2.1": "a dog", "3.1": "vehicle"},
        _judged({"1.2": ("incorrect", 0), "2.1": ("incorrect", 0), "3.1": ("incorrect", 0)}),
    )
    pending = SyntheticStudent(
        "Chie Fixture", None, {**_all_correct_written(), "1.3": "8"}, _judged({"1.3": ("pending", None)}),
        pending_reason={"1.3": "The stroke could be 1 or 7, and it stays unreadable when enlarged. Ask the teacher."},
    )
    ungraded = SyntheticStudent(None, None, {"1.1": "4"}, {}, uninspected=True)
    upside_down = SyntheticStudent("Dai Mock", "6", _all_correct_written(), _judged(), raster_rotation=180)
    partial = SyntheticStudent("Emi Dummy", "7", {**_all_correct_written(), "4": "April/5"}, _judged({"4": ("partial", 5)}))
    return [perfect, ninety, below, pending, ungraded, upside_down, partial]


def class_b_students() -> list[SyntheticStudent]:
    return [
        SyntheticStudent("Fumi Test", "1", {**_all_correct_written(), "4": "June/6"}, _judged()),
        SyntheticStudent("Gen Placeholder", "2", {**_all_correct_written(), "1.1": "8"}, _judged({"1.1": ("incorrect", 0)})),
    ]


def make_blank_pdf(path: Path, template_pages: int = 1) -> Path:
    out = pymupdf.open()
    for number in range(1, template_pages + 1):
        source = pymupdf.open()
        page = source.new_page(width=A4_W, height=A4_H)
        draw_printed_page(page, number, template_pages)
        scanify(page, out)
        source.close()
    out.save(path, garbage=4, deflate=True)
    out.close()
    return path


def make_key_pdf(path: Path, template_pages: int = 1) -> Path:
    out = pymupdf.open()
    for number in range(1, template_pages + 1):
        source = pymupdf.open()
        page = source.new_page(width=A4_W, height=A4_H)
        draw_printed_page(page, number, template_pages)
        draw_answers(page, number, template_pages, {**_all_correct_written(), "4": "September/9"}, PINK)
        scanify(page, out)
        source.close()
    out.save(path, garbage=4, deflate=True)
    out.close()
    return path


def _student_pages(out: pymupdf.Document, student: SyntheticStudent, template_pages: int) -> None:
    for number in range(1, template_pages + 1):
        source = pymupdf.open()
        page = source.new_page(width=A4_W, height=A4_H)
        draw_printed_page(page, number, template_pages)
        draw_answers(page, number, template_pages, student.written)
        if number == 1:
            if student.name:
                page.insert_font(fontname="pgcjk", fontbuffer=pymupdf.Font("cjk").buffer)
                page.insert_text((43 * A4_W / 100, 10.9 * A4_H / 100), student.name, fontsize=11, color=PENCIL, fontname="pgcjk")
            if student.number:
                page.insert_text((29.5 * A4_W / 100, 10.9 * A4_H / 100), student.number, fontsize=11, color=PENCIL)
        scanify(page, out, student.raster_rotation, student.stored_rotation)
        source.close()


def make_student_pdf(path: Path, students: list[SyntheticStudent], template_pages: int = 1) -> Path:
    out = pymupdf.open()
    for student in students:
        _student_pages(out, student, template_pages)
    out.save(path, garbage=4, deflate=True)
    out.close()
    return path


def base_test_json(blank: Path, key: Path, template_pages: int = 1, blank_pages: Optional[list[int]] = None, key_pages: Optional[list[int]] = None) -> dict[str, Any]:
    pages = list(range(1, template_pages + 1))
    return {
        "schema_version": SCHEMA_VERSION,
        "test_id": "demo-english-check",
        "test_version": f"v1-{template_pages}p",
        "title": "English Check-Up (synthetic)",
        "template_pages": template_pages,
        "max_points": 100,
        "references": {
            "blank": {"kind": "scan", "source_pdf": blank.name, "sha256": sha256_file(blank), "pages": blank_pages or pages},
            "key": {"kind": "scan", "source_pdf": key.name, "sha256": sha256_file(key), "pages": key_pages or pages},
            "teacher_confirmation": {"confirmed": True, "confirmed_at": "2026-11-05T00:00:00+00:00", "teacher_statement": "SYNTHETIC FIXTURE: no teacher involved."},
        },
        "rubric_status": "approved",
        "open_rubric_questions": [],
        "score_box": {"template_page": 1, "x_pct": 70, "y_pct": 5.5, "w_pct": 11.0, "h_pct": 5.0, "denominator_printed": True},
        "stamp_zone": {"template_page": 1, "x_pct": 50, "y_pct": 12, "w_pct": 44, "h_pct": 36},
        "protected_regions": [
            {"template_page": 1, "x_pct": 9, "y_pct": 5, "w_pct": 40, "h_pct": 7, "label": "title, class, number and name"},
            {"template_page": 1, "x_pct": 70, "y_pct": 5.5, "w_pct": 18, "h_pct": 5, "label": "score box"},
        ],
        "questions": question_table(template_pages),
    }


def scaffold_answer(question: dict[str, Any], student: SyntheticStudent, slot_number: Optional[int]) -> dict[str, Any]:
    """Turn fixture truth into a grading record. Nothing here looks at an image."""
    qid = question["id"]
    points = question["points"]
    if student.uninspected or qid not in student.judgments:
        return {
            "question_id": qid, "observed_kind": "not_inspected", "observed_answer": "", "decision": "pending", "awarded_points": None, "max_points": points,
            "verification": {"status": "not_inspected", "method": None, "image_ref": None},
            "confidence": {"alignment": "low", "reading": "low", "interpretation": "low"}, "notes": "This page hasn't been inspected yet.",
        }
    decision, awarded = student.judgments[qid]
    ref = f"slot-{slot_number:04d}"
    if decision == "pending":
        return {
            "question_id": qid, "observed_kind": "unreadable", "observed_answer": student.written.get(qid, ""), "decision": "pending", "awarded_points": None, "max_points": points,
            "verification": {"status": "unreadable", "method": "direct_visual", "image_ref": ref},
            "confidence": {"alignment": "high", "reading": "low", "interpretation": "high"}, "notes": student.pending_reason.get(qid, ""),
        }
    return {
        "question_id": qid, "observed_kind": "written", "observed_answer": student.written.get(qid, "(fixture)"), "decision": decision, "awarded_points": awarded, "max_points": points,
        "verification": {"status": "visually_verified", "method": "direct_visual", "image_ref": ref},
        "confidence": {"alignment": "high", "reading": "high", "interpretation": "high"}, "notes": "",
    }


def setup_test(job: Job, work_dir: Path, template_pages: int = 1) -> dict[str, Any]:
    blank = make_blank_pdf(work_dir / "demo_blank.pdf", template_pages)
    key = make_key_pdf(work_dir / "demo_key.pdf", template_pages)
    job.add_source(blank)
    job.add_source(key)
    test = base_test_json(blank, key, template_pages)
    save_json(job.test_path, test)
    return test


def setup_class(job: Job, work_dir: Path, class_id: str, class_label: str, students: list[SyntheticStudent], test: dict[str, Any], paper_mode: str = "simplex", render: bool = True) -> None:
    """Map, confirm rotation, render and record fixture grades for one synthetic class."""
    template_pages = test["template_pages"]
    scan = make_student_pdf(work_dir / f"demo_{class_id}_students.pdf", students, template_pages)
    job.add_source(scan)
    job.propose_map(class_id, class_label, [scan.name], paper_mode=paper_mode)
    # A person or model would determine these by looking. The fixture knows them.
    slots_by_rotation: dict[int, list[int]] = {}
    slot = 0
    for student in students:
        for _ in range(template_pages):
            slot += 1
            shown = (student.raster_rotation + student.stored_rotation) % 360
            slots_by_rotation.setdefault((360 - shown) % 360, []).append(slot)
    for rotation, slots in slots_by_rotation.items():
        job.set_rotation(class_id, rotation, slots)
    issues = Issues()
    page_map = parse_page_map(load_json(job.page_map_path(class_id)), issues)
    assert page_map is not None and issues.ok, issues.to_json()
    if render:
        for entry in page_map.slots:
            job.render_slot(class_id, entry.slot, dpi=72)
    records = []
    for index, student in enumerate(students):
        order = index + 1
        slot_for_page = {s.template_page: s.slot for s in page_map.slots_for_student(order)}
        records.append({
            "student_order": order,
            "name": {"status": "read", "value": student.name} if student.name else {"status": "unreadable"},
            "number": {"status": "read", "value": student.number} if student.number else {"status": "not_provided"},
            "source_pages": source_pages_for(page_map, order),
            "answers": [scaffold_answer(q, student, slot_for_page.get(q["template_page"])) for q in test["questions"]],
        })
    from .grading_models import parse_test

    parsed = parse_test(test, issues)
    assert parsed is not None
    save_json(job.grading_path(class_id), {
        "schema_version": SCHEMA_VERSION, "class_id": class_id, "test_id": test["test_id"], "test_version": test["test_version"],
        "rubric_hash": parsed.rubric_hash(), "question_hashes": {q.id: q.rubric_hash() for q in parsed.questions},
        "grader": {"type": "synthetic_fixture", "name": "typed-in fixture data; no visual reading took place"}, "students": records,
    })


def run_demo(root: Path) -> dict[str, dict]:
    """Build two synthetic classes from one confirmed test, and return their reports."""
    from .pipeline import build_class

    job = Job.create(root)
    work = root / "_fixture_inputs"
    work.mkdir(exist_ok=True)
    test = setup_test(job, work)
    setup_class(job, work, "demo-class-a", "Demo Class A", class_a_students(), test)
    setup_class(job, work, "demo-class-b", "Demo Class B", class_b_students(), test)
    return {cid: build_class(job, cid) for cid in ("demo-class-a", "demo-class-b")}
