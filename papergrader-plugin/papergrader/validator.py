"""Fail-closed quality control.

Input checks run before anything is drawn. Output checks open the finished files
and measure what is really on each page by rendering it: they don't believe the
generator's account of what it drew. A correction PDF that fails is never
presented as ready to print.

Image measurement here answers only "is the planned artwork on the page?". No
grade is ever read from pixels; ``check_no_grading_from_images`` enforces that
on this package's own source.
"""
from __future__ import annotations

import ast
import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pymupdf

from . import decorations, vision_check
from .common import MM, Issues, sha256_file
from .correction_overlay import planned_rects
from .grading_models import Grading, Outcome, PageMap, TestDefinition, compute_outcome, format_points
from .job import Job, check_profile
from .pdf_processor import page_fingerprint

FORBIDDEN_TEXT = re.compile(r"review|pending|provisional|unverified|unresolved|要確認|保留|\?|？", re.IGNORECASE)
AUTOMATED_GRADING_NOTE = re.compile(r"\b(ocr|tesseract|easyocr|pixel|threshold|image.?diff\w*|circle detection|line detection)\b", re.IGNORECASE)
FORBIDDEN_MODULES = {"pytesseract", "tesseract", "easyocr", "paddleocr", "cv2", "skimage", "sklearn", "torch", "tensorflow", "keras", "transformers", "openai", "anthropic", "requests", "httpx", "urllib3"}
# These modules may never read images at all: judgments and arithmetic stay pixel-free.
PIXEL_FREE_MODULES = {"grading_models.py"}

RENDER_DPI = 96
ALPHA_MIN = 16


@dataclass
class InputBundle:
    test: Optional[TestDefinition]
    page_map: Optional[PageMap]
    grading: Optional[Grading]
    outcomes: dict[int, Outcome]
    profile: dict[str, Any]
    issues: Issues


def check_no_grading_from_images(issues: Issues) -> None:
    """Static guard on this package: no OCR or vision libraries, no network clients."""
    package = Path(__file__).resolve().parent
    for source in sorted(package.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    issues.error("forbidden_import", f"{source.name} imports {name}. Grades can't come from OCR or computer vision, and no network clients are allowed.", source.name)
                if source.name in PIXEL_FREE_MODULES and root in {"pymupdf", "fitz", "PIL"}:
                    issues.error("forbidden_import", f"{source.name} must not read images, but it imports {name}.", source.name)


def validate_inputs(job: Job, class_id: str) -> InputBundle:
    issues = Issues()
    check_no_grading_from_images(issues)
    test = job.load_test(issues)
    page_map = job.load_page_map(class_id, issues)
    grading = job.load_grading(class_id, issues)
    profile = job.load_profile()
    check_profile(profile, issues)
    if test:
        _check_references(job, test, issues)
    if page_map:
        _check_page_map(job, test, page_map, class_id, issues)
    outcomes: dict[int, Outcome] = {}
    if test and page_map and grading:
        _check_grading(job, test, page_map, grading, class_id, issues)
        outcomes = {s.student_order: compute_outcome(s, test) for s in grading.students}
        _check_quality_signals(test, grading, issues)
    return InputBundle(test, page_map, grading, outcomes, profile, issues)


def _check_references(job: Job, test: TestDefinition, issues: Issues) -> None:
    if not test.confirmed or not test.teacher_statement.strip():
        issues.error("references_unconfirmed", "The teacher hasn't explicitly confirmed the blank and key page ranges for this test version. Stop and ask.", "references")
    for name, reference in (("blank", test.blank), ("key", test.key)):
        if reference.kind != "scan":
            continue
        if not reference.source_pdf:
            continue
        path = job.source_path(reference.source_pdf)
        if not path.is_file():
            issues.error("reference_missing", f"The {name} file {reference.source_pdf} isn't in sources/.", f"references.{name}")
        elif reference.sha256 != sha256_file(path):
            issues.error("reference_hash_mismatch", f"The {name} file differs from the one the teacher confirmed.", f"references.{name}")
    if test.key.kind == "teacher_entered_list" and not test.confirmed:
        issues.error("references_unconfirmed", "A teacher-entered key still needs the teacher's approval.", "references.key")
    if (
        test.blank.source_pdf and test.blank.source_pdf == test.key.source_pdf and set(test.blank.pages) & set(test.key.pages)
    ):
        issues.error("reference_pages_overlap", "The blank and key claim the same PDF pages.", "references")
    if test.key.kind == "scan" and test.key.pages and len(test.key.pages) != test.template_pages:
        issues.error("reference_incomplete", f"The key lists {len(test.key.pages)} page(s), but the test has {test.template_pages}.", "references.key")
    if test.blank.pages and len(test.blank.pages) != test.template_pages:
        issues.error("reference_incomplete", f"The blank lists {len(test.blank.pages)} page(s), but the test has {test.template_pages}.", "references.blank")
    if test.rubric_status != "approved":
        issues.error("rubric_not_approved", "The rubric is still a draft. Review rule-level questions with the teacher first.", "rubric")
    if test.open_rubric_questions:
        issues.error("rubric_open_questions", f"Open rubric questions remain: {'; '.join(test.open_rubric_questions)}", "rubric")
    for question in test.questions:
        if question.kind == "ambiguous":
            issues.error("rubric_ambiguous_question", f"Question {question.id} is marked ambiguous. Ask the teacher, then give it a real kind.", "rubric")


def _check_page_map(job: Job, test: Optional[TestDefinition], page_map: PageMap, class_id: str, issues: Issues) -> None:
    if page_map.class_id != class_id:
        issues.error("class_id_mismatch", f"page_map.json says class {page_map.class_id}, expected {class_id}.", "page_map")
    if test and (page_map.test_id != test.test_id or page_map.test_version != test.test_version):
        issues.error("test_version_mismatch", "The page map belongs to a different test version.", "page_map")

    source_index = {source.file: index for index, source in enumerate(page_map.sources)}
    for source in page_map.sources:
        path = job.source_path(source.file)
        if not path.is_file():
            issues.error("source_missing", f"Student scan {source.file} isn't in sources/.", "page_map.sources")
        elif sha256_file(path) != source.sha256:
            issues.error("source_hash_mismatch", f"{source.file} changed after it was mapped. Map it again.", "page_map.sources")

    expected = [s.slot for s in page_map.slots]
    if expected != list(range(1, len(expected) + 1)):
        issues.error("slot_sequence_broken", "Slots must run 1, 2, 3 ... with no gaps, repeats or reordering. Page order is locked to normal order.", "page_map.slots")

    seen: dict[tuple[str, int], int] = {}
    last_key: Optional[tuple[int, int]] = None
    unconfirmed: list[int] = []
    for slot in page_map.slots:
        if slot.kind != "scan":
            continue
        if slot.rotation_status != "visually_confirmed":
            unconfirmed.append(slot.slot)
        key = (slot.source_pdf or "", slot.source_page or 0)
        if key in seen:
            issues.error("student_page_duplicated", f"{key[0]} page {key[1]} is mapped to both slot {seen[key]} and slot {slot.slot}.", f"slot {slot.slot}")
        seen[key] = slot.slot
        if slot.source_pdf not in source_index:
            issues.error("source_page_invalid", f"Slot {slot.slot} refers to an undeclared file {slot.source_pdf}.", f"slot {slot.slot}")
            continue
        order_key = (source_index[slot.source_pdf], slot.source_page or 0)
        if last_key is not None and order_key <= last_key:
            issues.error("scan_order_violation", f"Slot {slot.slot} ({slot.source_pdf} page {slot.source_page}) breaks the original scan order.", f"slot {slot.slot}")
        last_key = order_key
    if unconfirmed:
        issues.error("rotation_unconfirmed", f"Nobody has confirmed the orientation of slots {_compact(unconfirmed)}. Look at each page, then run set-rotation.", "page_map.slots")

    fingerprints: dict[str, int] = {}
    acknowledged = {tuple(sorted(pair)) for pair in page_map.acknowledged_duplicates if isinstance(pair, list)}
    for source in page_map.sources:
        path = job.source_path(source.file)
        if not path.is_file() or sha256_file(path) != source.sha256:
            continue
        for page in range(1, source.page_count + 1):
            mapped = (source.file, page) in seen
            excluded = page in source.excluded_pages
            if not mapped and not excluded:
                issues.error("student_page_unmapped", f"{source.file} page {page} is neither a student page nor a confirmed reference. A lost page would shift every later correction.", "page_map.sources")
            if mapped and excluded:
                issues.error("reference_page_in_student_slots", f"{source.file} page {page} is declared as {source.excluded_pages[page]} but also mapped as a student page.", "page_map.sources")
            if test and mapped:
                for name, reference in (("blank", test.blank), ("key", test.key)):
                    if reference.sha256 == source.sha256 and page in reference.pages:
                        issues.error("reference_page_in_student_slots", f"{source.file} page {page} is the {name} reference and can't be a student page.", "page_map.sources")
            if mapped:
                slot_number = seen[(source.file, page)]
                try:
                    with pymupdf.open(path) as doc:
                        rect = doc[page - 1].rect
                except (IndexError, ValueError):
                    issues.error("source_page_invalid", f"{source.file} has no page {page}.", f"slot {slot_number}")
                    continue
                slot = page_map.slots[slot_number - 1] if slot_number <= len(page_map.slots) else None
                if slot and (abs(rect.width - slot.page_width_pt) > 0.75 or abs(rect.height - slot.page_height_pt) > 0.75):
                    issues.error("page_size_mismatch", f"Slot {slot_number} records {slot.page_width_pt:.1f} x {slot.page_height_pt:.1f} pt, but the scan page is {rect.width:.1f} x {rect.height:.1f} pt.", f"slot {slot_number}")
                print_id = page_fingerprint(path, page)
                if print_id is None:
                    continue
                if print_id in fingerprints:
                    pair = tuple(sorted((fingerprints[print_id], slot_number)))
                    if pair not in acknowledged:
                        issues.error("duplicate_page_content", f"Slots {pair[0]} and {pair[1]} have identical scans, which may be a double-fed sheet. Check the paper. If they are truly separate sheets, add {list(pair)} to acknowledged_duplicates.", f"slot {slot_number}")
                else:
                    fingerprints[print_id] = slot_number
    for (name, page), slot_number in seen.items():
        source = next((s for s in page_map.sources if s.file == name), None)
        if source and not 1 <= page <= source.page_count:
            issues.error("source_page_invalid", f"Slot {slot_number} refers to {name} page {page}, but that file has {source.page_count} page(s).", f"slot {slot_number}")

    if test:
        _check_packets(test, page_map, issues)


def _check_packets(test: TestDefinition, page_map: PageMap, issues: Issues) -> None:
    orders = page_map.student_orders()
    if orders != list(range(1, len(orders) + 1)):
        issues.error("student_order_broken", f"Test order must start at 1 for each class and run without gaps. Found {_compact(orders)}.", "page_map.slots")
    position = 0
    for order in orders:
        packet = page_map.slots_for_student(order)
        slots_expected = list(range(packet[0].slot, packet[0].slot + len(packet)))
        if [s.slot for s in packet] != slots_expected:
            issues.error("packet_not_contiguous", f"Student {order}'s pages are interleaved with another student's.", f"student {order}")
        position += len(packet)
        scanned = [s for s in packet if s.kind == "scan"]
        template = [s.template_page for s in scanned]
        if sorted(template) != list(range(1, test.template_pages + 1)):
            issues.error("packet_incomplete", f"Student {order} has template pages {template}, but the test has pages 1 to {test.template_pages}. Hold printing until the sheets are accounted for.", f"student {order}")
        if [s.page_in_packet for s in packet] != list(range(1, len(packet) + 1)):
            issues.error("packet_order_broken", f"Student {order}'s page_in_packet values aren't 1, 2, 3 ...", f"student {order}")
    if page_map.paper_mode == "simplex":
        sheets = [s.physical_sheet for s in page_map.slots]
        if len(set(sheets)) != len(sheets) or any(s.side != "front" for s in page_map.slots):
            issues.error("simplex_sheet_conflict", "In simplex mode, each slot must be the front of its own sheet.", "page_map.slots")
    else:
        sides: dict[int, list[str]] = defaultdict(list)
        for slot in page_map.slots:
            sides[slot.physical_sheet].append(slot.side)
        for sheet, faces in sides.items():
            if faces != ["front", "back"]:
                issues.error("duplex_side_missing", f"Sheet {sheet} has sides {faces}. Duplex needs front then back; add a blank_filler slot for an unscanned blank back.", f"sheet {sheet}")
        issues.warning("duplex_unverified", "Duplex output needs its own photocopy test. Sheet pairing and the printer's duplex behaviour are unconfirmed.", "page_map")


def _check_grading(job: Job, test: TestDefinition, page_map: PageMap, grading: Grading, class_id: str, issues: Issues) -> None:
    if grading.class_id != class_id:
        issues.error("class_id_mismatch", f"grading.json says class {grading.class_id}, expected {class_id}.", "grading")
    if grading.test_id != test.test_id or grading.test_version != test.test_version:
        issues.error("test_version_mismatch", "The grades belong to a different test version.", "grading")
    if grading.rubric_hash != test.rubric_hash():
        changed = sorted(q.id for q in test.questions if grading.question_hashes.get(q.id) != q.rubric_hash())
        issues.error("rubric_changed_since_grading", f"The rubric changed after grading (questions: {', '.join(changed) or 'structure'}). Run rebase-grading, then look at those answers again.", "grading")
    if grading.grader_type == "chatgpt_visual" and not vision_check.has_passed(job.vision_path):
        issues.error("vision_preflight_missing", "This session hasn't proven it can see images. Run vision-check before accepting visual grades.", "grading")
    if grading.grader_type == "synthetic_fixture":
        issues.warning("synthetic_grades", "These grades are synthetic fixture data, not anyone's reading of real work.", "grading")

    orders = page_map.student_orders()
    by_order = Counter(s.student_order for s in grading.students)
    for order, count in by_order.items():
        if count > 1:
            issues.error("student_duplicated", f"Student {order} has {count} grading records.", f"student {order}")
    for order in orders:
        if order not in by_order:
            issues.error("student_grading_missing", f"Student {order} has pages but no grading record. Every student stays in the output.", f"student {order}")
    for order in by_order:
        if order not in orders:
            issues.error("student_without_pages", f"Grading record {order} has no pages in the page map.", f"student {order}")

    renders = job.load_renders(class_id)
    render_hashes_checked: dict[str, bool] = {}
    known_ids = {q.id for q in test.questions}
    for student in grading.students:
        where = f"student {student.student_order}"
        actual = [
            (s.source_pdf, s.source_page) for s in page_map.slots_for_student(student.student_order) if s.kind == "scan"
        ]
        recorded = [(p.get("source_pdf"), p.get("source_page")) for p in student.source_pages if isinstance(p, dict)]
        if recorded != actual:
            issues.error("source_page_mismatch", f"The grading record says pages {recorded}, but the page map says {actual}. The grades might belong to another paper.", where)
        counts = Counter(a.question_id for a in student.answers)
        for question_id, count in counts.items():
            if count > 1:
                issues.error("answer_duplicated", f"Question {question_id} has {count} judgments.", where)
            if question_id not in known_ids:
                issues.error("answer_unknown_question", f"Question {question_id} isn't in the rubric.", where)
        for question in test.questions:
            answer = student.answer(question.id)
            if answer is None:
                issues.error("judgment_missing", f"Question {question.id} has no judgment. It stays unresolved, never zero. Record it, or record it as pending.", where)
                continue
            if answer.max_points != question.points:
                issues.error("max_points_mismatch", f"Question {question.id} records a maximum of {format_points(answer.max_points)}, but the rubric says {format_points(question.points)}.", where)
            if answer.image_ref:
                _check_image_ref(answer.image_ref, question.id, question.template_page, student.student_order, page_map, renders, render_hashes_checked, issues, where)
            for crop in answer.crop_refs:
                _check_image_ref(crop, question.id, question.template_page, student.student_order, page_map, renders, render_hashes_checked, issues, where)
            if answer.decision != "pending" and AUTOMATED_GRADING_NOTE.search(answer.notes):
                issues.warning("note_mentions_automation", f"Question {question.id}'s notes mention an automated tool. Confirm that the answer was read by eye.", where)
        outcome = compute_outcome(student, test)
        if student.declared_total is not None:
            if not outcome.resolved:
                issues.error("pending_has_total", f"A total was declared, but questions {', '.join(outcome.unresolved)} are unresolved.", where)
            elif student.declared_total != outcome.total:
                issues.error("score_arithmetic_mismatch", f"Declared total {format_points(student.declared_total)} doesn't match {format_points(outcome.total)}, the sum of the recorded judgments.", where)
        if student.name.status != "read" or student.number.status != "read":
            issues.warning("identity_not_read", "The name or number isn't readable. The report shows that instead of a guess.", where)


def _check_image_ref(ref: str, question_id: str, template_page: int, order: int, page_map: PageMap, renders: dict, checked: dict[str, bool], issues: Issues, where: str) -> None:
    entry = renders.get(ref)
    if entry is None:
        issues.error("image_ref_unknown", f"Question {question_id} cites image '{ref}', which was never rendered in this job.", where)
        return
    if entry.get("student_order") != order:
        issues.error("image_ref_wrong_student", f"Question {question_id} cites an image of student {entry.get('student_order')}, not student {order}.", where)
        return
    expected = next((s.slot for s in page_map.slots_for_student(order) if s.kind == "scan" and s.template_page == template_page), None)
    if entry.get("slot") != expected:
        issues.error("image_ref_wrong_page", f"Question {question_id} is on slot {expected}, but cites an image of slot {entry.get('slot')}.", where)
        return
    if ref not in checked:
        path = Path(entry.get("path", ""))
        checked[ref] = path.is_file() and sha256_file(path) == entry.get("sha256")
    if not checked[ref]:
        issues.error("image_ref_file_changed", f"The image '{ref}' behind question {question_id} is missing or changed since it was rendered.", where)


def _check_quality_signals(test: TestDefinition, grading: Grading, issues: Issues) -> None:
    """Advisory statistics. They ask a human to look; they never change a grade."""
    count = len(grading.students)
    if count < 2:
        return
    for question in test.questions:
        wrong = blank = 0
        decisions: dict[str, set[str]] = defaultdict(set)
        for student in grading.students:
            answer = student.answer(question.id)
            if answer is None or answer.decision == "pending":
                continue
            if answer.decision == "incorrect":
                wrong += 1
                if answer.observed_kind == "blank":
                    blank += 1
            if question.kind in {"fixed", "multiple_acceptable"} and answer.observed_kind != "blank":
                decisions[answer.observed_answer.strip().lower()].add(answer.decision)
        if count >= 4 and blank / count >= 0.4:
            issues.warning("class_wide_blank_cluster", f"{blank} of {count} students appear blank on question {question.id}. Look at those scans again: this was the signature of the earlier OCR failure.", f"question {question.id}")
        elif count >= 4 and wrong / count >= 0.7:
            issues.warning("class_wide_error_cluster", f"{wrong} of {count} students are wrong on question {question.id}. Check the rubric and re-inspect a sample.", f"question {question.id}")
        for observed, seen in decisions.items():
            if len(seen) > 1:
                issues.warning("inconsistent_decision", f"On question {question.id}, the answer '{observed}' was graded {sorted(seen)}. Check that the rubric was applied consistently.", f"question {question.id}")


def _compact(values: list[int]) -> str:
    return ", ".join(map(str, values[:20])) + (" ..." if len(values) > 20 else "")


# ---------------------------------------------------------------------------
# Output checks: open the file, render it, measure it
# ---------------------------------------------------------------------------
def validate_plans(plans: list[dict], test: TestDefinition, page_map: PageMap, outcomes: dict[int, Outcome], issues: Issues) -> None:
    """Check the plan against rules recomputed from recorded grades, independent of the planner."""
    if len(plans) != len(page_map.slots):
        issues.error("page_count_mismatch", f"Planned {len(plans)} pages for {len(page_map.slots)} slots.", "plans")
    score_slots: Counter[int] = Counter()
    for plan in plans:
        order = plan["student_order"]
        outcome = outcomes.get(order)
        where = f"slot {plan['slot']}"
        if outcome is None:
            continue
        if plan["score"]:
            score_slots[order] += 1
            if not outcome.resolved:
                issues.error("pending_has_score", f"Student {order} has unresolved answers, yet a score is planned.", where)
            elif plan["score"]["text"].split("/")[0] != format_points(outcome.total):
                issues.error("score_mismatch", f"Student {order}: planned score {plan['score']['text']}, computed {format_points(outcome.total)}.", where)
        if not outcome.resolved and (plan["stamp"] or plan["embroidery"]):
            issues.error("pending_has_decoration", f"Student {order} is unresolved and can't receive achievement art.", where)
        if outcome.resolved and outcome.award == "none" and (plan["stamp"] or plan["embroidery"]):
            issues.error("ineligible_decoration", f"Student {order} scored below 90% and can't receive achievement art.", where)
        if outcome.award == "praise" and plan["embroidery"]:
            issues.error("ineligible_decoration", f"Student {order} scored below 100% and can't receive the embroidered border.", where)
    for order, outcome in outcomes.items():
        if outcome.resolved and score_slots[order] != 1:
            issues.error("score_count_wrong", f"Student {order} needs exactly one printed score; found {score_slots[order]}.", f"student {order}")
        if outcome.award != "none":
            packet = [p for p in plans if p["student_order"] == order]
            stamps = [p for p in packet if p["stamp"]]
            borders = [p for p in packet if p["embroidery"]]
            if len(stamps) != 1 or stamps[0]["stamp"]["kind"] != outcome.award:
                issues.error("award_missing", f"Student {order} earned a {outcome.award} stamp, but the plan doesn't contain exactly one.", f"student {order}")
            if outcome.award == "perfect" and len(borders) != 1:
                issues.error("embroidery_missing", f"Student {order} scored 100%, but no embroidered border is planned.", f"student {order}")


def validate_correction_pdf(path: Path, plans: list[dict], offset_mm: tuple[float, float], issues: Issues) -> None:
    """Render the printable file, and confirm that it holds only what was planned."""
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        issues.error("pdf_unreadable", f"The correction PDF can't be opened: {exc}", path.name)
        return
    with doc:
        if doc.page_count != len(plans):
            issues.error("page_count_mismatch", f"The correction PDF has {doc.page_count} pages, but the student stack needs {len(plans)}.", path.name)
        for index, page in enumerate(doc):
            if index >= len(plans):
                break
            _check_correction_page(page, plans[index], offset_mm, issues)


def _check_correction_page(page: pymupdf.Page, plan: dict, offset_mm: tuple[float, float], issues: Issues) -> None:
    where = f"page {page.number + 1}"
    if abs(page.rect.width - plan["page_width_pt"]) > 0.75 or abs(page.rect.height - plan["page_height_pt"]) > 0.75 or page.rotation != 0:
        issues.error("page_size_mismatch", f"The page is {page.rect.width:.1f} x {page.rect.height:.1f} pt (rotation {page.rotation}), but the scan is {plan['page_width_pt']:.1f} x {plan['page_height_pt']:.1f} pt.", where)

    text = page.get_text().strip()
    if text:
        if FORBIDDEN_TEXT.search(text):
            issues.error("forbidden_status_text", f"The correction page contains forbidden status text: {text[:60]!r}. This must never print on a student's test.", where)
        else:
            issues.error("correction_contains_text", f"The correction page contains unexpected text: {text[:60]!r}. Marks are vector paths only.", where)
    if page.get_images(full=True):
        issues.error("correction_contains_image", "The correction page contains an image. It must not reprint the scan or any raster art.", where)
    if page.first_annot is not None or page.first_widget is not None:
        issues.error("correction_contains_annotation", "The correction page contains annotations or form fields.", where)

    zoom = RENDER_DPI / 72.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
    samples, width, height = bytes(pix.samples), pix.width, pix.height
    ox, oy = offset_mm[0] * MM, offset_mm[1] * MM
    rects = planned_rects(plan)

    def shifted(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        return box[0] + ox, box[1] + oy, box[2] + ox, box[3] + oy

    for box, mark in zip(rects["marks"], plan["marks"]):
        report = decorations.analyze_region(samples, width, height, zoom, shifted(box))
        if report.coverage < 0.01:
            issues.error("mark_missing", f"The mark for question {mark['question_id']} isn't where it was planned.", where)
        elif report.red_share < 0.9:
            issues.error("mark_not_red", f"The mark for question {mark['question_id']} isn't red.", where)
    for box in rects["score"]:
        if decorations.analyze_region(samples, width, height, zoom, shifted(box)).coverage < 0.005:
            issues.error("score_missing", "The planned score isn't inside the score box.", where)
    for box in rects["stamp"]:
        report = decorations.analyze_region(samples, width, height, zoom, shifted(box))
        if report.coverage < 0.15:
            issues.error("stamp_missing", "The planned achievement stamp isn't visible on the rendered page.", where)
        elif report.families < 3:
            issues.error("stamp_not_illustrated", f"The stamp shows only {report.families} colour families, so it isn't the illustrated character art.", where)
    if plan["embroidery"]:
        _check_embroidery(samples, width, height, zoom, rects["embroidery"], plan["embroidery"], shifted, issues, where)

    # Anything inked outside the planned shapes doesn't belong on a student's paper.
    mask = bytearray(width * height)
    pad = 3.0
    for group in rects.values():
        for box in group:
            b = shifted(box)
            x0, y0 = max(0, int((b[0] - pad) * zoom)), max(0, int((b[1] - pad) * zoom))
            x1, y1 = min(width, int((b[2] + pad) * zoom) + 1), min(height, int((b[3] + pad) * zoom) + 1)
            for y in range(y0, y1):
                mask[y * width + x0 : y * width + x1] = b"\x01" * (x1 - x0)
    alpha = samples[3::4]
    stray = 0
    for y in range(height):
        row = alpha[y * width : (y + 1) * width]
        if not any(row):
            continue
        guard = mask[y * width : (y + 1) * width]
        stray += sum(1 for a, g in zip(row, guard) if a >= ALPHA_MIN and not g)
    if stray:
        issues.error("ink_outside_planned_areas", f"{stray} inked pixels lie outside every planned mark, score and decoration.", where)


def _check_embroidery(samples: bytes, width: int, height: int, zoom: float, boxes: list, embroidery: dict, shifted, issues: Issues, where: str) -> None:
    if not boxes:
        issues.error("embroidery_missing", "The plan calls for an embroidered border, but it has no motifs.", where)
        return
    missing = sum(1 for box in boxes if decorations.ink_coverage(samples, width, height, zoom, shifted(box)) < 0.012)
    if missing:
        issues.error("embroidery_missing", f"{missing} of {len(boxes)} planned embroidery motifs aren't on the rendered page.", where)
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    ring = decorations.analyze_region(samples, width, height, zoom, shifted((x0, y0, x1, y1)))
    if not missing and ring.families < 4:
        issues.error("embroidery_not_multicolor", f"The border shows only {ring.families} thread colour families. It must be multicoloured needlework, not a plain frame.", where)


def validate_preview_pdf(path: Path, plans: list[dict], issues: Issues) -> None:
    """The preview must show the same art over the scan, in the same order."""
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        issues.error("pdf_unreadable", f"The preview PDF can't be opened: {exc}", path.name)
        return
    with doc:
        if doc.page_count != len(plans):
            issues.error("preview_page_count_mismatch", f"The preview has {doc.page_count} pages, expected {len(plans)}.", path.name)
        for index, page in enumerate(doc):
            if index >= len(plans):
                break
            plan = plans[index]
            where = f"preview page {index + 1}"
            text = page.get_text().strip()
            if FORBIDDEN_TEXT.search(text):
                issues.error("forbidden_status_text", f"The preview contains forbidden status text: {text[:60]!r}.", where)
            elif text:
                issues.error("preview_contains_text", f"The preview contains unexpected text: {text[:60]!r}.", where)
            if not plan["stamp"] and not plan["embroidery"]:
                continue
            zoom = RENDER_DPI / 72.0
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            pix = pymupdf.Pixmap(pix, 1)  # opaque RGBA, the form analyze_region expects
            samples = bytes(pix.samples)
            rects = planned_rects(plan)
            for box in rects["stamp"]:
                if decorations.analyze_region(samples, pix.width, pix.height, zoom, box).families < 3:
                    issues.error("preview_stamp_missing", "The stamp doesn't appear on the superimposed preview.", where)
            if plan["embroidery"]:
                boxes = rects["embroidery"]
                missing = sum(1 for box in boxes if decorations.analyze_region(samples, pix.width, pix.height, zoom, box).families < 1)
                if not boxes or missing > len(boxes) * 0.1:
                    issues.error("preview_embroidery_missing", "The embroidered border doesn't appear on the superimposed preview.", where)


def validate_reports(paths: dict[str, Path], page_map: PageMap, grading: Grading, test: TestDefinition, outcomes: dict[int, Outcome], issues: Issues) -> None:
    for name, path in paths.items():
        if not path.is_file():
            issues.error("output_missing", f"Required output {path.name} wasn't created.", name)
            continue
        if path.suffix == ".pdf":
            try:
                with pymupdf.open(path) as doc:
                    if doc.page_count < 1:
                        raise ValueError("no pages")
                    for page in doc:
                        page.get_pixmap(dpi=20)
            except Exception as exc:
                issues.error("pdf_unreadable", f"{path.name} can't be opened and rendered: {exc}", name)
    roster = paths.get("roster")
    if roster and roster.is_file():
        with pymupdf.open(roster) as doc:
            text = "\n".join(page.get_text() for page in doc)
        pending = sum(1 for o in outcomes.values() if not o.resolved)
        if text.count("Pending review") != pending:
            issues.error("roster_pending_mismatch", f"The roster shows {text.count('Pending review')} pending entries, expected {pending}.", "roster")
        for outcome in outcomes.values():
            if outcome.resolved:
                needle = f"{format_points(outcome.total)}/{format_points(outcome.max_points)}"
                if needle not in text:
                    issues.error("roster_score_missing", f"The roster is missing student {outcome.student_order}'s score {needle}.", "roster")
    key_list = paths.get("answer_key")
    if key_list and key_list.is_file():
        with pymupdf.open(key_list) as doc:
            text = "\n".join(page.get_text() for page in doc)
        for question in test.questions:
            if question.id not in text:
                issues.error("answer_key_incomplete", f"The answer-key list is missing question {question.id}.", "answer_key")
    results = paths.get("results_csv")
    if results and results.is_file():
        with open(results, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if [int(r["test_order"]) for r in rows] != page_map.student_orders():
            issues.error("results_order_mismatch", "The results CSV doesn't list every student in scan order.", "results_csv")
        for row in rows:
            outcome = outcomes.get(int(row["test_order"]))
            if outcome and not outcome.resolved and row["total"] not in ("", "Pending review"):
                issues.error("results_pending_has_total", f"Student {row['test_order']} is pending but has a total in the CSV.", "results_csv")
            if outcome and outcome.resolved and row["total"] != format_points(outcome.total):
                issues.error("results_total_mismatch", f"Student {row['test_order']}'s CSV total doesn't match the computed score.", "results_csv")


# Named checks for the machine-readable report: each lists the codes that fail it.
CHECKS: dict[str, set[str]] = {
    "teacher_confirmed_references": {"references_unconfirmed", "reference_missing", "reference_hash_mismatch", "reference_incomplete", "reference_pages_overlap", "test_missing", "rubric_not_approved", "rubric_open_questions", "rubric_ambiguous_question", "rubric_rule_missing", "rubric_points_mismatch"},
    "every_student_page_mapped": {"student_page_unmapped", "student_page_duplicated", "source_page_invalid", "source_missing", "source_hash_mismatch", "reference_page_in_student_slots", "packet_incomplete", "packet_not_contiguous", "packet_order_broken", "duplicate_page_content", "page_map_missing", "simplex_sheet_conflict", "duplex_side_missing"},
    "scan_order_preserved": {"scan_order_violation", "slot_sequence_broken", "student_order_broken", "results_order_mismatch"},
    "orientation_confirmed": {"rotation_unconfirmed"},
    "no_grades_from_image_measurement": {"forbidden_import", "judgment_bad_method", "judgment_not_verified", "judgment_no_image_ref"},
    "scores_from_visual_judgments": {"judgment_missing", "judgment_missing_points", "judgment_on_unseen_answer", "judgment_no_observation", "judgment_low_confidence", "image_ref_unknown", "image_ref_wrong_student", "image_ref_wrong_page", "image_ref_file_changed", "vision_preflight_missing", "source_page_mismatch", "rubric_changed_since_grading", "grading_missing", "student_grading_missing", "student_without_pages"},
    "scores_arithmetically_correct": {"score_arithmetic_mismatch", "score_mismatch", "points_decision_mismatch", "max_points_mismatch", "results_total_mismatch", "score_count_wrong"},
    "pending_has_no_score_or_art": {"pending_has_total", "pending_has_score", "pending_has_decoration", "pending_has_points", "results_pending_has_total", "roster_pending_mismatch", "ineligible_decoration"},
    "no_status_labels_on_overlays": {"forbidden_status_text", "correction_contains_text", "preview_contains_text", "correction_contains_annotation"},
    "marks_in_answer_areas": {"mark_outside_answer_region", "mark_missing", "mark_not_red", "score_missing", "ink_outside_planned_areas", "offset_pushes_art_off_page"},
    "praise_stamps_present": {"award_missing", "stamp_missing", "stamp_not_illustrated", "stamp_no_safe_position", "preview_stamp_missing"},
    "perfect_has_stamp_and_embroidery": {"embroidery_missing", "embroidery_not_multicolor", "embroidery_no_safe_area", "preview_embroidery_missing", "art_asset_missing"},
    "all_outputs_exist_and_render": {"output_missing", "pdf_unreadable", "answer_key_incomplete", "roster_score_missing"},
    "page_count_matches_stack": {"page_count_mismatch", "preview_page_count_mismatch", "page_size_mismatch"},
    "no_scan_in_correction_pdf": {"correction_contains_image"},
}


def checks_summary(issues: Issues, outputs_checked: bool) -> dict[str, str]:
    """Report each named check. A check that never ran says so, rather than claiming success."""
    failed = {i.code for i in issues.errors}
    output_only = {"all_outputs_exist_and_render", "page_count_matches_stack", "no_scan_in_correction_pdf", "no_status_labels_on_overlays", "marks_in_answer_areas", "praise_stamps_present", "perfect_has_stamp_and_embroidery", "pending_has_no_score_or_art"}
    out = {}
    for name, codes in CHECKS.items():
        if codes & failed:
            out[name] = "failed"
        elif not outputs_checked and name in output_only:
            out[name] = "not_run"
        else:
            out[name] = "passed"
    return out
