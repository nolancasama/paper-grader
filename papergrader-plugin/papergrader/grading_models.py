"""Strict data models for tests, page maps and visually recorded grades.

Nothing here reads an image. Grades enter the system only as explicit records,
and these parsers reject anything ambiguous instead of filling in a default:

* unknown fields are errors, so a stray ``ocr_text`` can't slip through;
* a missing judgment is an error, never a zero;
* ``pending`` means no points at all (``null``), which is different from 0.

Totals use exact fractions, so 0.1 + 0.2 can't produce a wrong printed score.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Optional

from . import SCHEMA_VERSION
from .common import SAFE_ID, Issues, sha256_text

DECISIONS = {"correct", "partial", "incorrect", "pending"}
QUESTION_KINDS = {"fixed", "multiple_acceptable", "personal", "matching", "open", "ambiguous"}
OBSERVED_KINDS = {"written", "circled", "checked", "selected", "matched", "drawn", "blank", "unreadable", "not_inspected"}
VERIFICATION_STATUSES = {"visually_verified", "unreadable", "low_confidence", "not_inspected"}
VERIFICATION_METHODS = {"direct_visual", "teacher_override"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
GRADER_TYPES = {"chatgpt_visual", "teacher_manual", "synthetic_fixture"}
IDENTITY_STATUSES = {"read", "unreadable", "not_provided"}
PAPER_MODES = {"simplex", "duplex"}
ROTATIONS = {0, 90, 180, 270}
ROTATION_STATUSES = {"unconfirmed", "visually_confirmed"}
SIDES = {"front", "back"}
SLOT_KINDS = {"scan", "blank_filler"}


def to_points(value: Any) -> Optional[Fraction]:
    """Exact points from a JSON number or numeric string; None if it isn't a finite number."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (int, float, str)):
        try:
            return Fraction(str(value))
        except (ValueError, ZeroDivisionError):
            return None
    return None


def format_points(value: Fraction) -> str:
    """Render points for humans and for printing: 90, 87.5, 33.33."""
    if value.denominator == 1:
        return str(value.numerator)
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_keys(obj: Any, required: set[str], optional: set[str], where: str, issues: Issues) -> bool:
    if not isinstance(obj, dict):
        issues.error("schema_type", f"Expected an object, found {type(obj).__name__}.", where)
        return False
    for key in sorted(required - obj.keys()):
        issues.error("schema_missing_field", f"Required field '{key}' is missing.", where)
    for key in sorted(obj.keys() - required - optional):
        issues.error("schema_unknown_field", f"Unknown field '{key}'. Fix the spelling or remove it.", where)
    return required <= obj.keys()


def _text(obj: dict, key: str, where: str, issues: Issues, empty_ok: bool = False) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or (not empty_ok and not value.strip()):
        issues.error("schema_type", f"'{key}' must be a {'' if empty_ok else 'non-empty '}string.", where)
        return ""
    return value


def _choice(obj: dict, key: str, allowed: set, where: str, issues: Issues) -> Any:
    value = obj.get(key)
    if isinstance(value, (list, dict)) or value not in allowed:
        issues.error("schema_bad_value", f"'{key}' is {value!r}; expected one of {sorted(map(str, allowed))}.", where)
        return None
    return value


def _pct(value: Any, name: str, where: str, issues: Issues) -> float:
    if not _is_number(value) or not 0 <= value <= 100:
        issues.error("schema_bad_value", f"'{name}' must be a percentage from 0 to 100, found {value!r}.", where)
        return 0.0
    return float(value)


@dataclass(frozen=True)
class Rect:
    """A rectangle in percent of the upright page, with the origin at the top left."""

    x: float
    y: float
    w: float
    h: float

    @property
    def x1(self) -> float:
        return self.x + self.w

    @property
    def y1(self) -> float:
        return self.y + self.h

    def contains(self, px: float, py: float, tolerance: float = 0.0) -> bool:
        return self.x - tolerance <= px <= self.x1 + tolerance and self.y - tolerance <= py <= self.y1 + tolerance

    def intersects(self, other: "Rect") -> bool:
        return self.x < other.x1 and other.x < self.x1 and self.y < other.y1 and other.y < self.y1

    def to_json(self) -> dict[str, float]:
        return {"x_pct": self.x, "y_pct": self.y, "w_pct": self.w, "h_pct": self.h}


def _rect(obj: Any, where: str, issues: Issues, extra: Optional[set[str]] = None) -> Rect:
    keys = {"x_pct", "y_pct", "w_pct", "h_pct"}
    if not _check_keys(obj, keys, extra or set(), where, issues):
        return Rect(0, 0, 0, 0)
    rect = Rect(
        _pct(obj["x_pct"], "x_pct", where, issues),
        _pct(obj["y_pct"], "y_pct", where, issues),
        _pct(obj["w_pct"], "w_pct", where, issues),
        _pct(obj["h_pct"], "h_pct", where, issues),
    )
    if rect.w <= 0 or rect.h <= 0 or rect.x1 > 100.001 or rect.y1 > 100.001:
        issues.error("schema_bad_value", f"Rectangle {rect.to_json()} is empty or runs off the page.", where)
    return rect


# ---------------------------------------------------------------------------
# Test definition (shared across classes)
# ---------------------------------------------------------------------------
@dataclass
class Question:
    id: str
    template_page: int
    kind: str
    prompt: str
    accepted_answers: list[str]
    rule: str
    rationale: str
    points: Fraction
    partial_credit: str
    answer_region: Rect
    mark_anchor: tuple[float, float]
    mark_size_mm: float

    def rubric_fields(self) -> dict[str, Any]:
        """What the grade depends on. Moving a mark changes layout, not the rubric."""
        return {
            "id": self.id,
            "kind": self.kind,
            "prompt": self.prompt,
            "accepted_answers": self.accepted_answers,
            "rule": self.rule,
            "points": format_points(self.points),
            "partial_credit": self.partial_credit,
        }

    def rubric_hash(self) -> str:
        return sha256_text(json.dumps(self.rubric_fields(), ensure_ascii=False, sort_keys=True))


@dataclass
class ScoreBox:
    template_page: int
    rect: Rect
    denominator_printed: bool
    append_denominator: bool


@dataclass
class Zone:
    template_page: int
    rect: Rect
    label: str = ""


@dataclass
class ReferenceFile:
    kind: str  # "scan" or "teacher_entered_list" (keys only)
    source_pdf: Optional[str]
    sha256: Optional[str]
    pages: list[int]


@dataclass
class TestDefinition:
    test_id: str
    test_version: str
    title: str
    template_pages: int
    max_points: Fraction
    blank: ReferenceFile
    key: ReferenceFile
    confirmed: bool
    confirmed_at: str
    teacher_statement: str
    rubric_status: str
    open_rubric_questions: list[str]
    score_box: ScoreBox
    stamp_zone: Zone
    perfect_stamp_zone: Optional[Zone]
    protected_regions: list[Zone]
    questions: list[Question]

    def rubric_hash(self) -> str:
        payload = {
            "test_id": self.test_id,
            "test_version": self.test_version,
            "max_points": format_points(self.max_points),
            "questions": [q.rubric_fields() for q in self.questions],
        }
        return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def question(self, question_id: str) -> Optional[Question]:
        return next((q for q in self.questions if q.id == question_id), None)


def _parse_reference(obj: Any, name: str, issues: Issues) -> ReferenceFile:
    where = f"references.{name}"
    if not _check_keys(obj, {"kind", "pages"}, {"source_pdf", "sha256"}, where, issues):
        return ReferenceFile("scan", None, None, [])
    kinds = {"scan"} if name == "blank" else {"scan", "teacher_entered_list"}
    kind = _choice(obj, "kind", kinds, where, issues) or "scan"
    pages = obj["pages"]
    if not isinstance(pages, list) or not all(isinstance(p, int) and not isinstance(p, bool) and p >= 1 for p in pages):
        issues.error("schema_bad_value", "'pages' must list 1-based PDF page numbers.", where)
        pages = []
    if kind == "scan" and not (obj.get("source_pdf") and pages):
        issues.error("reference_missing", f"The {name} reference needs a source_pdf and its full page range.", where)
    return ReferenceFile(kind, obj.get("source_pdf"), obj.get("sha256"), list(pages))


def _parse_zone(obj: Any, where: str, issues: Issues) -> Zone:
    if not isinstance(obj, dict):
        issues.error("schema_type", "Expected an object.", where)
        return Zone(1, Rect(0, 0, 0, 0))
    page = obj.get("template_page")
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        issues.error("schema_bad_value", "'template_page' must be a page number starting at 1.", where)
        page = 1
    rect = _rect({k: v for k, v in obj.items() if k not in ("template_page", "label")}, where, issues)
    label = obj.get("label", "")
    return Zone(page, rect, label if isinstance(label, str) else "")


def parse_test(data: Any, issues: Issues) -> Optional[TestDefinition]:
    where = "test"
    required = {
        "schema_version", "test_id", "test_version", "title", "template_pages", "max_points", "references",
        "rubric_status", "open_rubric_questions", "score_box", "stamp_zone", "protected_regions", "questions",
    }
    if not _check_keys(data, required, {"perfect_stamp_zone"}, where, issues):
        return None
    if data["schema_version"] != SCHEMA_VERSION:
        issues.error("schema_version", f"Expected schema_version {SCHEMA_VERSION}.", where)
    test_id = _text(data, "test_id", where, issues)
    if test_id and not SAFE_ID.match(test_id):
        issues.error("schema_bad_value", "test_id may contain only letters, digits, '.', '_' and '-'.", where)
    template_pages = data["template_pages"]
    if not isinstance(template_pages, int) or isinstance(template_pages, bool) or template_pages < 1:
        issues.error("schema_bad_value", "'template_pages' must be a whole number of at least 1.", where)
        template_pages = 1
    max_points = to_points(data["max_points"])
    if max_points is None or max_points <= 0:
        issues.error("schema_bad_value", "'max_points' must be a positive number.", where)
        max_points = Fraction(1)

    refs = data["references"]
    blank = key = ReferenceFile("scan", None, None, [])
    confirmed, confirmed_at, statement = False, "", ""
    if _check_keys(refs, {"blank", "key", "teacher_confirmation"}, set(), "references", issues):
        blank = _parse_reference(refs["blank"], "blank", issues)
        key = _parse_reference(refs["key"], "key", issues)
        tc = refs["teacher_confirmation"]
        if _check_keys(tc, {"confirmed", "confirmed_at", "teacher_statement"}, set(), "references.teacher_confirmation", issues):
            confirmed = tc["confirmed"] is True
            confirmed_at = tc["confirmed_at"] if isinstance(tc["confirmed_at"], str) else ""
            statement = tc["teacher_statement"] if isinstance(tc["teacher_statement"], str) else ""

    rubric_status = _choice(data, "rubric_status", {"draft", "approved"}, where, issues) or "draft"
    open_questions = data["open_rubric_questions"]
    if not isinstance(open_questions, list) or not all(isinstance(q, str) for q in open_questions):
        issues.error("schema_type", "'open_rubric_questions' must be a list of strings.", where)
        open_questions = []

    score_obj = data["score_box"]
    score_box = ScoreBox(1, Rect(0, 0, 0, 0), True, False)
    if _check_keys(score_obj, {"template_page", "x_pct", "y_pct", "w_pct", "h_pct", "denominator_printed"}, {"append_denominator"}, "score_box", issues):
        zone = _parse_zone({k: v for k, v in score_obj.items() if k not in ("denominator_printed", "append_denominator")}, "score_box", issues)
        if not isinstance(score_obj["denominator_printed"], bool):
            issues.error("schema_type", "'denominator_printed' must be true or false.", "score_box")
        append = score_obj.get("append_denominator", False) is True
        printed = score_obj["denominator_printed"] is True
        if printed and append:
            issues.error("schema_bad_value", "The worksheet already prints a denominator, so a second one must not be added.", "score_box")
        score_box = ScoreBox(zone.template_page, zone.rect, printed, append)

    stamp_zone = _parse_zone(data["stamp_zone"], "stamp_zone", issues)
    perfect_zone = _parse_zone(data["perfect_stamp_zone"], "perfect_stamp_zone", issues) if "perfect_stamp_zone" in data else None
    protected: list[Zone] = []
    if isinstance(data["protected_regions"], list):
        for i, item in enumerate(data["protected_regions"]):
            protected.append(_parse_zone(item, f"protected_regions[{i}]", issues))
    else:
        issues.error("schema_type", "'protected_regions' must be a list.", where)

    questions: list[Question] = []
    if not isinstance(data["questions"], list) or not data["questions"]:
        issues.error("schema_bad_value", "'questions' must list at least one question.", where)
    else:
        seen: set[str] = set()
        for i, item in enumerate(data["questions"]):
            question = _parse_question(item, f"questions[{i}]", template_pages, issues)
            if question is None:
                continue
            if question.id in seen:
                issues.error("duplicate_question", f"Question id '{question.id}' appears twice.", f"questions[{i}]")
            seen.add(question.id)
            questions.append(question)

    for name, zone_page in (("score_box", score_box.template_page), ("stamp_zone", stamp_zone.template_page)):
        if zone_page > template_pages:
            issues.error("schema_bad_value", f"{name} is on page {zone_page}, but the test has {template_pages} page(s).", name)
    if stamp_zone.template_page != score_box.template_page:
        issues.error("schema_bad_value", "stamp_zone must be on the same page as the score box.", "stamp_zone")
    if perfect_zone and perfect_zone.template_page != score_box.template_page:
        issues.error("schema_bad_value", "perfect_stamp_zone must be on the same page as the score box.", "perfect_stamp_zone")
    if questions and sum((q.points for q in questions), Fraction(0)) != max_points:
        total = format_points(sum((q.points for q in questions), Fraction(0)))
        issues.error("rubric_points_mismatch", f"Question points add up to {total}, but max_points is {format_points(max_points)}.", where)

    return TestDefinition(
        test_id=test_id, test_version=_text(data, "test_version", where, issues), title=_text(data, "title", where, issues),
        template_pages=template_pages, max_points=max_points, blank=blank, key=key, confirmed=confirmed,
        confirmed_at=confirmed_at, teacher_statement=statement, rubric_status=rubric_status,
        open_rubric_questions=list(open_questions), score_box=score_box, stamp_zone=stamp_zone,
        perfect_stamp_zone=perfect_zone, protected_regions=protected, questions=questions,
    )


def _parse_question(obj: Any, where: str, template_pages: int, issues: Issues) -> Optional[Question]:
    required = {"id", "template_page", "kind", "prompt", "accepted_answers", "rule", "points", "answer_region", "mark_anchor"}
    if not _check_keys(obj, required, {"rationale", "partial_credit", "mark_size_mm"}, where, issues):
        return None
    points = to_points(obj["points"])
    if points is None or points <= 0:
        issues.error("schema_bad_value", "'points' must be a positive number.", where)
        points = Fraction(1)
    page = obj["template_page"]
    if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= template_pages:
        issues.error("schema_bad_value", f"'template_page' must be from 1 to {template_pages}.", where)
        page = 1
    accepted = obj["accepted_answers"]
    if not isinstance(accepted, list) or not all(isinstance(a, str) for a in accepted):
        issues.error("schema_type", "'accepted_answers' must be a list of strings.", where)
        accepted = []
    kind = _choice(obj, "kind", QUESTION_KINDS, where, issues) or "ambiguous"
    rule = _text(obj, "rule", where, issues)
    if kind in {"personal", "open", "multiple_acceptable"} and not rule:
        issues.error("rubric_rule_missing", f"A '{kind}' question needs a written marking rule.", where)
    region = _rect(obj["answer_region"], f"{where}.answer_region", issues)
    anchor = obj["mark_anchor"]
    ax, ay = 0.0, 0.0
    if _check_keys(anchor, {"x_pct", "y_pct"}, set(), f"{where}.mark_anchor", issues):
        ax, ay = _pct(anchor["x_pct"], "x_pct", where, issues), _pct(anchor["y_pct"], "y_pct", where, issues)
    size = obj.get("mark_size_mm", 9.0)
    if not _is_number(size) or not 3 <= size <= 40:
        issues.error("schema_bad_value", "'mark_size_mm' must be between 3 and 40.", where)
        size = 9.0
    return Question(
        id=_text(obj, "id", where, issues), template_page=page, kind=kind, prompt=_text(obj, "prompt", where, issues),
        accepted_answers=list(accepted), rule=rule, rationale=str(obj.get("rationale", "")), points=points,
        partial_credit=str(obj.get("partial_credit", "")), answer_region=region, mark_anchor=(ax, ay), mark_size_mm=float(size),
    )


# ---------------------------------------------------------------------------
# Page map: every printable slot and where it came from
# ---------------------------------------------------------------------------
@dataclass
class Slot:
    slot: int
    kind: str
    student_order: int
    page_in_packet: int
    template_page: int
    physical_sheet: int
    side: str
    source_pdf: Optional[str]
    source_page: Optional[int]
    scan_rotation: int
    rotation_status: str
    offset_dx_pct: float
    offset_dy_pct: float
    page_width_pt: float
    page_height_pt: float


@dataclass
class SourcePdf:
    file: str
    sha256: str
    page_count: int
    excluded_pages: dict[int, str]


@dataclass
class PageMap:
    class_id: str
    class_label: str
    test_id: str
    test_version: str
    paper_mode: str
    sources: list[SourcePdf]
    slots: list[Slot]
    acknowledged_duplicates: list[list[int]] = field(default_factory=list)

    def slots_for_student(self, order: int) -> list[Slot]:
        return [s for s in self.slots if s.student_order == order]

    def student_orders(self) -> list[int]:
        orders: list[int] = []
        for slot in self.slots:
            if slot.student_order not in orders:
                orders.append(slot.student_order)
        return orders


def parse_page_map(data: Any, issues: Issues) -> Optional[PageMap]:
    where = "page_map"
    required = {"schema_version", "class_id", "class_label", "test_id", "test_version", "paper_mode", "sources", "slots"}
    if not _check_keys(data, required, {"acknowledged_duplicates"}, where, issues):
        return None
    if data["schema_version"] != SCHEMA_VERSION:
        issues.error("schema_version", f"Expected schema_version {SCHEMA_VERSION}.", where)
    class_id = _text(data, "class_id", where, issues)
    if class_id and not SAFE_ID.match(class_id):
        issues.error("schema_bad_value", "class_id may contain only letters, digits, '.', '_' and '-'. Put other characters in class_label.", where)
    sources: list[SourcePdf] = []
    for i, item in enumerate(data["sources"] if isinstance(data["sources"], list) else []):
        loc = f"sources[{i}]"
        if not _check_keys(item, {"file", "sha256", "page_count"}, {"excluded_pages"}, loc, issues):
            continue
        excluded: dict[int, str] = {}
        for entry in item.get("excluded_pages", []):
            if _check_keys(entry, {"page", "role"}, set(), f"{loc}.excluded_pages", issues):
                excluded[entry["page"]] = entry["role"]
        sources.append(SourcePdf(item["file"], item["sha256"], item["page_count"], excluded))
    slots: list[Slot] = []
    raw_slots = data["slots"] if isinstance(data["slots"], list) else []
    if not raw_slots:
        issues.error("schema_bad_value", "'slots' must list at least one page.", where)
    for i, item in enumerate(raw_slots):
        slot = _parse_slot(item, f"slots[{i}]", issues)
        if slot:
            slots.append(slot)
    return PageMap(
        class_id=class_id, class_label=_text(data, "class_label", where, issues), test_id=str(data["test_id"]),
        test_version=str(data["test_version"]), paper_mode=_choice(data, "paper_mode", PAPER_MODES, where, issues) or "simplex",
        sources=sources, slots=slots, acknowledged_duplicates=data.get("acknowledged_duplicates", []),
    )


def _parse_slot(obj: Any, where: str, issues: Issues) -> Optional[Slot]:
    required = {
        "slot", "kind", "student_order", "page_in_packet", "template_page", "physical_sheet", "side", "source_pdf",
        "source_page", "scan_rotation", "rotation_status", "page_width_pt", "page_height_pt",
    }
    if not _check_keys(obj, required, {"content_offset_pct"}, where, issues):
        return None
    for key in ("slot", "student_order", "page_in_packet", "template_page", "physical_sheet"):
        if not isinstance(obj[key], int) or isinstance(obj[key], bool) or obj[key] < 1:
            issues.error("schema_bad_value", f"'{key}' must be a whole number of at least 1.", where)
            return None
    kind = _choice(obj, "kind", SLOT_KINDS, where, issues)
    if kind is None:
        return None
    if kind == "scan" and (not obj["source_pdf"] or not isinstance(obj["source_page"], int)):
        issues.error("schema_bad_value", "A scan slot needs source_pdf and source_page.", where)
        return None
    if kind == "blank_filler" and (obj["source_pdf"] or obj["source_page"]):
        issues.error("schema_bad_value", "A blank_filler slot can't have a source page.", where)
        return None
    if not _is_number(obj["page_width_pt"]) or not _is_number(obj["page_height_pt"]) or obj["page_width_pt"] <= 0 or obj["page_height_pt"] <= 0:
        issues.error("schema_bad_value", "Page size must be positive.", where)
        return None
    offset = obj.get("content_offset_pct", {"dx": 0, "dy": 0})
    dx, dy = 0.0, 0.0
    if _check_keys(offset, {"dx", "dy"}, set(), f"{where}.content_offset_pct", issues):
        if not _is_number(offset["dx"]) or not _is_number(offset["dy"]) or abs(offset["dx"]) > 15 or abs(offset["dy"]) > 15:
            issues.error("schema_bad_value", "content_offset_pct values must be numbers within +/-15.", where)
        else:
            dx, dy = float(offset["dx"]), float(offset["dy"])
    return Slot(
        slot=obj["slot"], kind=kind, student_order=obj["student_order"], page_in_packet=obj["page_in_packet"],
        template_page=obj["template_page"], physical_sheet=obj["physical_sheet"],
        side=_choice(obj, "side", SIDES, where, issues) or "front", source_pdf=obj["source_pdf"], source_page=obj["source_page"],
        scan_rotation=_choice(obj, "scan_rotation", ROTATIONS, where, issues) or 0,
        rotation_status=_choice(obj, "rotation_status", ROTATION_STATUSES, where, issues) or "unconfirmed",
        offset_dx_pct=dx, offset_dy_pct=dy, page_width_pt=float(obj["page_width_pt"]), page_height_pt=float(obj["page_height_pt"]),
    )


# ---------------------------------------------------------------------------
# Grading: one record per student, one judgment per question
# ---------------------------------------------------------------------------
@dataclass
class Identity:
    status: str
    value: str

    def display(self) -> str:
        if self.status == "read":
            return self.value
        return "Unreadable" if self.status == "unreadable" else "Not provided"


@dataclass
class Answer:
    question_id: str
    observed_kind: str
    observed_answer: str
    decision: str
    awarded_points: Optional[Fraction]
    max_points: Fraction
    verification_status: str
    method: Optional[str]
    image_ref: Optional[str]
    crop_refs: list[str]
    confidence: dict[str, str]
    mark: Optional[tuple[float, float]]
    notes: str
    teacher_statement: str


@dataclass
class Student:
    student_order: int
    name: Identity
    number: Identity
    source_pages: list[dict[str, Any]]
    answers: list[Answer]
    declared_total: Optional[Fraction]
    stamp_zone: Optional[Rect]
    notes: str

    def answer(self, question_id: str) -> Optional[Answer]:
        return next((a for a in self.answers if a.question_id == question_id), None)


@dataclass
class Grading:
    class_id: str
    test_id: str
    test_version: str
    rubric_hash: str
    question_hashes: dict[str, str]
    grader_type: str
    grader_name: str
    students: list[Student]


def _parse_identity(obj: Any, where: str, issues: Issues) -> Identity:
    if not _check_keys(obj, {"status"}, {"value"}, where, issues):
        return Identity("unreadable", "")
    status = _choice(obj, "status", IDENTITY_STATUSES, where, issues) or "unreadable"
    value = obj.get("value", "") or ""
    if status == "read" and not (isinstance(value, str) and value.strip()):
        issues.error("schema_bad_value", "An identity marked 'read' needs a value. Use 'unreadable' instead of guessing.", where)
    if status != "read" and value:
        issues.error("schema_bad_value", f"An identity marked '{status}' can't carry a value; a guessed identity isn't allowed.", where)
    return Identity(status, str(value))


def parse_grading(data: Any, issues: Issues) -> Optional[Grading]:
    where = "grading"
    required = {"schema_version", "class_id", "test_id", "test_version", "rubric_hash", "question_hashes", "grader", "students"}
    if not _check_keys(data, required, set(), where, issues):
        return None
    if data["schema_version"] != SCHEMA_VERSION:
        issues.error("schema_version", f"Expected schema_version {SCHEMA_VERSION}.", where)
    grader_type, grader_name = "", ""
    if _check_keys(data["grader"], {"type", "name"}, set(), "grading.grader", issues):
        grader_type = _choice(data["grader"], "type", GRADER_TYPES, "grading.grader", issues) or ""
        grader_name = str(data["grader"]["name"])
    students: list[Student] = []
    if not isinstance(data["students"], list):
        issues.error("schema_type", "'students' must be a list.", where)
    else:
        for i, item in enumerate(data["students"]):
            student = _parse_student(item, f"students[{i}]", issues)
            if student:
                students.append(student)
    hashes = data["question_hashes"] if isinstance(data["question_hashes"], dict) else {}
    return Grading(
        class_id=str(data["class_id"]), test_id=str(data["test_id"]), test_version=str(data["test_version"]),
        rubric_hash=str(data["rubric_hash"]), question_hashes=hashes, grader_type=grader_type, grader_name=grader_name, students=students,
    )


def _parse_student(obj: Any, where: str, issues: Issues) -> Optional[Student]:
    required = {"student_order", "name", "number", "source_pages", "answers"}
    if not _check_keys(obj, required, {"declared_total", "stamp_zone", "notes"}, where, issues):
        return None
    if not isinstance(obj["student_order"], int) or isinstance(obj["student_order"], bool) or obj["student_order"] < 1:
        issues.error("schema_bad_value", "'student_order' must be a whole number of at least 1.", where)
        return None
    declared = None
    if obj.get("declared_total") is not None:
        declared = to_points(obj["declared_total"])
        if declared is None:
            issues.error("schema_bad_value", "'declared_total' must be a number or null.", where)
    answers: list[Answer] = []
    if not isinstance(obj["answers"], list):
        issues.error("schema_type", "'answers' must be a list.", where)
    else:
        for i, item in enumerate(obj["answers"]):
            answer = _parse_answer(item, f"{where}.answers[{i}]", issues)
            if answer:
                answers.append(answer)
    source_pages = obj["source_pages"] if isinstance(obj["source_pages"], list) else []
    return Student(
        student_order=obj["student_order"], name=_parse_identity(obj["name"], f"{where}.name", issues),
        number=_parse_identity(obj["number"], f"{where}.number", issues), source_pages=source_pages, answers=answers,
        declared_total=declared, stamp_zone=_rect(obj["stamp_zone"], f"{where}.stamp_zone", issues) if obj.get("stamp_zone") else None,
        notes=str(obj.get("notes", "")),
    )


def _parse_answer(obj: Any, where: str, issues: Issues) -> Optional[Answer]:
    required = {"question_id", "observed_kind", "observed_answer", "decision", "awarded_points", "max_points", "verification", "confidence"}
    if not _check_keys(obj, required, {"mark", "notes", "teacher_statement"}, where, issues):
        return None
    decision = _choice(obj, "decision", DECISIONS, where, issues)
    observed_kind = _choice(obj, "observed_kind", OBSERVED_KINDS, where, issues)
    max_points = to_points(obj["max_points"])
    if max_points is None or max_points <= 0:
        issues.error("schema_bad_value", "'max_points' must be a positive number.", where)
        max_points = Fraction(1)
    observed = obj["observed_answer"]
    if not isinstance(observed, str):
        issues.error("schema_type", "'observed_answer' must be a string.", where)
        observed = ""

    verification = obj["verification"]
    v_status, method, image_ref, crops = None, None, None, []
    if _check_keys(verification, {"status", "method", "image_ref"}, {"crop_refs"}, f"{where}.verification", issues):
        v_status = _choice(verification, "status", VERIFICATION_STATUSES, f"{where}.verification", issues)
        method = verification["method"]
        image_ref = verification["image_ref"]
        crops = verification.get("crop_refs", [])
        if not isinstance(crops, list) or not all(isinstance(c, str) for c in crops):
            issues.error("schema_type", "'crop_refs' must be a list of strings.", where)
            crops = []

    confidence = obj["confidence"]
    levels: dict[str, str] = {}
    if _check_keys(confidence, {"alignment", "reading", "interpretation"}, set(), f"{where}.confidence", issues):
        for key in ("alignment", "reading", "interpretation"):
            levels[key] = _choice(confidence, key, CONFIDENCE_LEVELS, f"{where}.confidence", issues) or "low"

    awarded_raw = obj["awarded_points"]
    awarded = None
    if decision == "pending":
        # Null, not zero: pending points must not be representable as a number.
        if awarded_raw is not None:
            issues.error("pending_has_points", "A pending answer must have awarded_points = null. Pending isn't zero.", where)
        if v_status == "visually_verified":
            issues.error("pending_marked_verified", "A pending answer can't be 'visually_verified'. Record why it is unresolved.", where)
        if observed_kind == "not_inspected" and v_status not in {"not_inspected", None}:
            issues.error("schema_bad_value", "observed_kind 'not_inspected' needs verification.status 'not_inspected'.", where)
    elif decision:
        awarded = to_points(awarded_raw)
        if awarded is None:
            issues.error("judgment_missing_points", f"A '{decision}' answer needs numeric awarded_points. A missing value never counts as zero.", where)
        elif decision == "correct" and awarded != max_points:
            issues.error("points_decision_mismatch", f"'correct' must award full points ({format_points(max_points)}), found {format_points(awarded)}.", where)
        elif decision == "incorrect" and awarded != 0:
            issues.error("points_decision_mismatch", f"'incorrect' must award 0, found {format_points(awarded)}.", where)
        elif decision == "partial" and not 0 < awarded < max_points:
            issues.error("points_decision_mismatch", f"'partial' must award more than 0 and less than {format_points(max_points)}, found {format_points(awarded)}.", where)
        if v_status != "visually_verified":
            issues.error("judgment_not_verified", f"A '{decision}' answer must be 'visually_verified'. Otherwise record it as pending.", where)
        if method not in VERIFICATION_METHODS:
            issues.error("judgment_bad_method", f"verification.method is {method!r}. Only direct visual reading or a teacher override can establish a grade; OCR and scripts can't.", where)
        if not image_ref:
            issues.error("judgment_no_image_ref", "A grade must name the page image that was looked at.", where)
        if observed_kind in {"unreadable", "not_inspected"}:
            issues.error("judgment_on_unseen_answer", f"An answer observed as '{observed_kind}' can't receive a grade. Record it as pending.", where)
        if not observed.strip():
            issues.error("judgment_no_observation", "Record what was actually seen. A blank answer is written as observed_kind 'blank' with a description.", where)
        low = [k for k, v in levels.items() if v == "low"]
        if low:
            issues.error("judgment_low_confidence", f"Low {', '.join(low)} confidence requires pending, not a grade.", where)
        if method == "teacher_override" and not str(obj.get("teacher_statement", "")).strip():
            issues.error("override_no_statement", "A teacher override must quote what the teacher said.", where)

    mark = None
    if obj.get("mark") is not None:
        if _check_keys(obj["mark"], {"x_pct", "y_pct"}, set(), f"{where}.mark", issues):
            mark = (_pct(obj["mark"]["x_pct"], "x_pct", where, issues), _pct(obj["mark"]["y_pct"], "y_pct", where, issues))
    return Answer(
        question_id=_text(obj, "question_id", where, issues), observed_kind=observed_kind or "not_inspected", observed_answer=observed,
        decision=decision or "pending", awarded_points=awarded, max_points=max_points, verification_status=v_status or "not_inspected",
        method=method, image_ref=image_ref, crop_refs=list(crops), confidence=levels, mark=mark, notes=str(obj.get("notes", "")),
        teacher_statement=str(obj.get("teacher_statement", "")),
    )


# ---------------------------------------------------------------------------
# Arithmetic and award rules. The only place a total is ever computed.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Outcome:
    student_order: int
    resolved: bool
    total: Optional[Fraction]
    max_points: Fraction
    percent: Optional[Fraction]
    award: str  # "perfect", "praise" or "none"
    unresolved: tuple[str, ...]


def compute_outcome(student: Student, test: TestDefinition) -> Outcome:
    """Add up visually recorded judgments. Missing or pending means no total and no award."""
    unresolved: list[str] = []
    total = Fraction(0)
    for question in test.questions:
        answer = student.answer(question.id)
        if answer is None or answer.decision == "pending" or answer.awarded_points is None:
            unresolved.append(question.id)
        else:
            total += answer.awarded_points
    if unresolved:
        return Outcome(student.student_order, False, None, test.max_points, None, "none", tuple(unresolved))
    percent = total * 100 / test.max_points
    award = "perfect" if total == test.max_points else ("praise" if percent >= 90 else "none")
    return Outcome(student.student_order, True, total, test.max_points, percent, award, ())
