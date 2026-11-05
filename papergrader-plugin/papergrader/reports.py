"""Teacher-facing reports. "Pending review" may appear here, and only here.

None of these pages ever enter a correction PDF: they are separate files, so
they can't shift a print job.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Optional

import pymupdf

from .common import MM
from .grading_models import Grading, Outcome, PageMap, Student, TestDefinition, format_points

PAGE_W, PAGE_H = 210 * MM, 297 * MM
MARGIN = 14 * MM
PENDING = "Pending review"
SYMBOLS = {"correct": "○", "partial": "△", "incorrect": "×", "pending": ""}

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
except ImportError:  # the spreadsheet is optional; CSV always works
    Workbook = None  # type: ignore[assignment,misc]


class _Writer:
    """Minimal table layout, falling back to a CJK font so Japanese names print correctly."""

    def __init__(self, title: str) -> None:
        self.doc = pymupdf.open()
        self.doc.set_metadata({"title": title, "producer": "PaperGrader", "creator": "PaperGrader"})
        self.regular = pymupdf.Font("helv")
        self.bold = pymupdf.Font("hebo")
        self.cjk = pymupdf.Font("cjk")
        self.page: Optional[pymupdf.Page] = None
        self.y = 0.0
        self.title = title
        self.new_page()

    def new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = MARGIN

    def _runs(self, text: str, bold: bool) -> list[tuple[str, pymupdf.Font]]:
        base = self.bold if bold else self.regular
        runs: list[tuple[str, pymupdf.Font]] = []
        for char in text:
            font = base if base.has_glyph(ord(char)) else self.cjk
            if runs and runs[-1][1] is font:
                runs[-1] = (runs[-1][0] + char, font)
            else:
                runs.append((char, font))
        return runs

    def width(self, text: str, size: float, bold: bool = False) -> float:
        return sum(font.text_length(run, size) for run, font in self._runs(text, bold))

    def wrap(self, text: str, size: float, max_width: float, bold: bool = False) -> list[str]:
        lines: list[str] = []
        for paragraph in text.split("\n"):
            current = ""
            for token in _tokens(paragraph):
                if self.width(current + token, size, bold) <= max_width:
                    current += token
                    continue
                if current:
                    lines.append(current.rstrip())
                current = token.lstrip()
                while self.width(current, size, bold) > max_width and len(current) > 1:
                    cut = len(current) - 1
                    while cut > 1 and self.width(current[:cut], size, bold) > max_width:
                        cut -= 1
                    lines.append(current[:cut])
                    current = current[cut:]
            lines.append(current.rstrip())
        return lines or [""]

    def text(self, x: float, baseline: float, text: str, size: float, bold: bool = False, color: tuple[float, float, float] = (0.1, 0.1, 0.12)) -> None:
        writer = pymupdf.TextWriter(self.page.rect, color=color)
        cursor = x
        for run, font in self._runs(text, bold):
            writer.append((cursor, baseline), run, font=font, fontsize=size)
            cursor += font.text_length(run, size)
        writer.write_text(self.page)

    def heading(self, text: str, size: float = 16) -> None:
        for line in self.wrap(text, size, PAGE_W - 2 * MARGIN, bold=True):
            self.y += size * 1.25
            self.text(MARGIN, self.y, line, size, bold=True)
        self.y += size * 0.45

    def paragraph(self, text: str, size: float = 9.5, color: tuple[float, float, float] = (0.25, 0.25, 0.3)) -> None:
        for line in self.wrap(text, size, PAGE_W - 2 * MARGIN):
            if self.y + size * 1.4 > PAGE_H - MARGIN:
                self.new_page()
            self.y += size * 1.35
            self.text(MARGIN, self.y, line, size, color=color)
        self.y += size * 0.5

    def table(self, headers: list[str], rows: list[list[str]], widths: list[float], size: float = 10.0, emphasize: Optional[int] = None) -> None:
        """A table that repeats its header on each page. Widths are fractions of the page."""
        total = PAGE_W - 2 * MARGIN
        columns = [w * total for w in widths]
        pad = 3.0

        def draw_header() -> None:
            height = size * 1.8
            self.page.draw_rect(pymupdf.Rect(MARGIN, self.y, MARGIN + total, self.y + height), color=None, fill=(0.91, 0.92, 0.95))
            x = MARGIN
            for header, column in zip(headers, columns):
                self.text(x + pad, self.y + height - size * 0.55, header, size, bold=True)
                x += column
            self.y += height

        draw_header()
        for index, row in enumerate(rows):
            wrapped = [self.wrap(cell, size, column - 2 * pad, bold=emphasize == i) for i, (cell, column) in enumerate(zip(row, columns))]
            height = max(len(cell) for cell in wrapped) * size * 1.3 + size * 0.7
            if self.y + height > PAGE_H - MARGIN:
                self.new_page()
                draw_header()
            if index % 2:
                self.page.draw_rect(pymupdf.Rect(MARGIN, self.y, MARGIN + total, self.y + height), color=None, fill=(0.97, 0.97, 0.985))
            x = MARGIN
            for i, (cell, column) in enumerate(zip(wrapped, columns)):
                line_y = self.y + size * 1.2
                for line in cell:
                    color = (0.72, 0.28, 0.0) if line == PENDING else (0.1, 0.1, 0.12)
                    self.text(x + pad, line_y, line, size, bold=emphasize == i, color=color)
                    line_y += size * 1.3
                x += column
            self.page.draw_line((MARGIN, self.y + height), (MARGIN + total, self.y + height), color=(0.82, 0.83, 0.86), width=0.4)
            self.y += height
        self.y += size

    def finish(self, path: Path) -> Path:
        count = self.doc.page_count
        for index, page in enumerate(self.doc):
            self.page = page
            label = f"{self.title}   |   Page {index + 1} of {count}"
            self.text(MARGIN, PAGE_H - MARGIN * 0.55, label, 7.5, color=(0.45, 0.45, 0.5))
        self.doc.subset_fonts()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(path, garbage=4, deflate=True)
        self.doc.close()
        return path


def _tokens(text: str) -> Iterable[str]:
    """Split on spaces for Latin text, and between characters for CJK text."""
    token = ""
    for char in text:
        if char == " ":
            yield token + char
            token = ""
        elif ord(char) > 0x2E7F:
            if token:
                yield token
                token = ""
            yield char
        else:
            token += char
    if token:
        yield token


def _score_cell(outcome: Outcome) -> str:
    return f"{format_points(outcome.total)}/{format_points(outcome.max_points)}" if outcome.resolved else PENDING


def _page_range(page_map: PageMap, order: int) -> str:
    parts: dict[str, list[int]] = {}
    for slot in page_map.slots_for_student(order):
        if slot.kind == "scan":
            parts.setdefault(slot.source_pdf or "", []).append(slot.source_page or 0)
    out = []
    for name, pages in parts.items():
        span = f"{pages[0]}" if len(pages) == 1 else f"{pages[0]}-{pages[-1]}"
        out.append(f"{name} p.{span}")
    return "; ".join(out)


def build_roster(path: Path, test: TestDefinition, page_map: PageMap, grading: Grading, outcomes: dict[int, Outcome]) -> Path:
    title = f"{page_map.class_label} — Student Scores"
    writer = _Writer(title)
    writer.heading(title)
    writer.paragraph(f"{test.title} (version {test.test_version}). Listed in original scan order.")
    rows = []
    for student in sorted(grading.students, key=lambda s: s.student_order):
        outcome = outcomes[student.student_order]
        rows.append([str(student.student_order), student.name.display(), student.number.display(), page_map.class_label, _score_cell(outcome)])
    count = len(rows)
    size = 12.0 if count <= 30 else (10.0 if count <= 42 else 9.0)
    writer.table(["Order", "Name", "No.", "Class", "Score"], rows, [0.09, 0.39, 0.12, 0.18, 0.22], size=size, emphasize=4)
    return writer.finish(path)


def build_summary(path: Path, test: TestDefinition, page_map: PageMap, grading: Grading, outcomes: dict[int, Outcome], warnings: list[str]) -> Path:
    title = f"{page_map.class_label} — Grading Summary"
    writer = _Writer(title)
    writer.heading(title)
    resolved = [o for o in outcomes.values() if o.resolved]
    pending = [o for o in outcomes.values() if not o.resolved]
    line = f"{test.title} (version {test.test_version}). Students: {len(outcomes)}. Confirmed: {len(resolved)}. Pending review: {len(pending)}."
    if resolved:
        average = sum((o.total for o in resolved), start=type(resolved[0].total)(0)) / len(resolved)
        line += f" Average of confirmed scores: {float(average):.1f}/{format_points(test.max_points)}."
    writer.paragraph(line)
    if grading.grader_type == "synthetic_fixture":
        writer.paragraph("SYNTHETIC DEMONSTRATION DATA: these are not real student grades.", color=(0.72, 0.28, 0.0))
    rows = []
    for student in sorted(grading.students, key=lambda s: s.student_order):
        outcome = outcomes[student.student_order]
        rows.append([
            str(student.student_order), student.name.display(), student.number.display(), _score_cell(outcome),
            _page_range(page_map, student.student_order), ", ".join(outcome.unresolved),
        ])
    writer.table(["Order", "Name", "No.", "Score", "Scan pages", "Needs review"], rows, [0.08, 0.26, 0.09, 0.15, 0.24, 0.18], size=9.5, emphasize=3)
    review = _review_rows(grading, outcomes)
    if review:
        writer.heading("Teacher review list", 12)
        writer.paragraph("These answers have no mark on the printed correction page. The student's score box stays blank until every one is resolved.")
        writer.table(["Order", "Question", "What was seen", "Why it is unresolved"], review, [0.08, 0.12, 0.35, 0.45], size=9)
    if warnings:
        writer.heading("Quality-control warnings", 12)
        for warning in warnings:
            writer.paragraph(f"• {warning}", size=9)
    return writer.finish(path)


def _review_rows(grading: Grading, outcomes: dict[int, Outcome]) -> list[list[str]]:
    rows = []
    for student in sorted(grading.students, key=lambda s: s.student_order):
        for question_id in outcomes[student.student_order].unresolved:
            answer = student.answer(question_id)
            if answer is None:
                rows.append([str(student.student_order), question_id, "(no judgment recorded)", "Missing"])
            else:
                reason = answer.notes or answer.verification_status.replace("_", " ")
                rows.append([str(student.student_order), question_id, answer.observed_answer or f"({answer.observed_kind.replace('_', ' ')})", reason])
    return rows


def build_answer_key(path: Path, test: TestDefinition, class_label: Optional[str] = None) -> Path:
    title = f"{test.title} — Interpreted Answer Key"
    writer = _Writer(title)
    writer.heading(title)
    label = f" Used for {class_label}." if class_label else ""
    writer.paragraph(f"Test version {test.test_version}. Maximum {format_points(test.max_points)} points. This is the rule set actually applied, not a transcription of the completed key.{label}")
    kinds = {
        "fixed": "Fixed", "multiple_acceptable": "Several accepted", "personal": "Personal response", "matching": "Matching",
        "open": "Open response", "ambiguous": "Ambiguous: ask teacher",
    }
    rows = []
    for question in test.questions:
        accepted = "; ".join(question.accepted_answers) or "(see rule)"
        rule = question.rule
        if question.rationale:
            rule += f" Why: {question.rationale}"
        if question.partial_credit:
            rule += f" Partial credit: {question.partial_credit}"
        rows.append([question.id, str(question.template_page), kinds[question.kind], accepted, rule.strip(), format_points(question.points)])
    writer.table(["Q", "Page", "Type", "Accepted", "Rule", "Pts"], rows, [0.08, 0.07, 0.15, 0.24, 0.39, 0.07], size=9)
    if test.open_rubric_questions:
        writer.heading("Open rubric questions", 12)
        for item in test.open_rubric_questions:
            writer.paragraph(f"• {item}")
    return writer.finish(path)


def _safe_cell(value: str) -> str:
    """Stop spreadsheet apps from running a handwritten '=' or '+' as a formula."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def results_rows(test: TestDefinition, page_map: PageMap, grading: Grading, outcomes: dict[int, Outcome]) -> tuple[list[str], list[list[str]]]:
    question_ids = [q.id for q in test.questions]
    headers = ["test_order", "class", "source_pages", "name", "number"] + [f"Q{q}" for q in question_ids] + ["total", "max", "percent", "status", "unresolved_questions"]
    rows = []
    for student in sorted(grading.students, key=lambda s: s.student_order):
        outcome = outcomes[student.student_order]
        scores = []
        for question_id in question_ids:
            answer = student.answer(question_id)
            scores.append(format_points(answer.awarded_points) if answer and answer.awarded_points is not None else "pending")
        rows.append(
            [str(student.student_order), page_map.class_label, _page_range(page_map, student.student_order), _safe_cell(student.name.display()), _safe_cell(student.number.display())]
            + scores
            + [
                format_points(outcome.total) if outcome.resolved else PENDING,
                format_points(outcome.max_points),
                f"{float(outcome.percent):.1f}" if outcome.resolved else "",
                "confirmed" if outcome.resolved else "pending review",
                " ".join(outcome.unresolved),
            ]
        )
    return headers, rows


def answer_detail_rows(test: TestDefinition, grading: Grading) -> tuple[list[str], list[list[str]]]:
    headers = ["test_order", "question", "observed_kind", "observed_answer", "decision", "symbol", "awarded", "max", "verification", "method", "image_ref", "alignment_conf", "reading_conf", "interpretation_conf", "notes"]
    rows = []
    for student in sorted(grading.students, key=lambda s: s.student_order):
        for question in test.questions:
            answer = student.answer(question.id)
            if answer is None:
                rows.append([str(student.student_order), question.id, "", "", "missing", "", "", format_points(question.points), "", "", "", "", "", "", ""])
                continue
            rows.append([
                str(student.student_order), question.id, answer.observed_kind, _safe_cell(answer.observed_answer), answer.decision, SYMBOLS[answer.decision],
                format_points(answer.awarded_points) if answer.awarded_points is not None else "",
                format_points(answer.max_points), answer.verification_status, answer.method or "", answer.image_ref or "",
                answer.confidence.get("alignment", ""), answer.confidence.get("reading", ""), answer.confidence.get("interpretation", ""), _safe_cell(answer.notes),
            ])
    return headers, rows


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel opens Japanese names correctly
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return path


def write_xlsx(path: Path, sheets: list[tuple[str, list[str], list[list[str]]]]) -> Optional[Path]:
    if Workbook is None:
        return None
    book = Workbook()
    book.remove(book.active)
    fill = PatternFill("solid", fgColor="E8EAF0")
    for name, headers, rows in sheets:
        sheet = book.create_sheet(name)
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = fill
            cell.alignment = Alignment(vertical="center")
        for row in rows:
            sheet.append([_numeric(value) for value in row])
        sheet.freeze_panes = "A2"
        for index, header in enumerate(headers, start=1):
            longest = max([len(str(header))] + [len(str(row[index - 1])) for row in rows[:200]])
            sheet.column_dimensions[sheet.cell(1, index).column_letter].width = min(40, longest + 2)
    book.save(path)
    return path


def _numeric(value: str) -> Any:
    """Keep numbers numeric so spreadsheet formulas work; everything else stays text."""
    try:
        number = float(value)
    except ValueError:
        return value
    if value.strip().lower() in {"nan", "inf", "-inf", "infinity", "-infinity"}:
        return value
    return int(number) if number.is_integer() and "." not in value else number


def print_mapping_rows(page_map: PageMap, grading: Grading) -> tuple[list[str], list[list[str]]]:
    names = {s.student_order: s.name.display() for s in grading.students}
    headers = ["pdf_page", "test_order", "name", "page_in_packet", "source_pdf", "source_page", "physical_sheet", "side", "scan_rotation", "mapping"]
    rows = []
    for slot in page_map.slots:
        rows.append([
            str(slot.slot), str(slot.student_order), _safe_cell(names.get(slot.student_order, "")), str(slot.page_in_packet), slot.source_pdf or "(blank filler)",
            str(slot.source_page or ""), str(slot.physical_sheet), slot.side, str(slot.scan_rotation),
            f"Normal-order PDF page {slot.slot} -> original test order {slot.student_order}, page {slot.page_in_packet}",
        ])
    return headers, rows
