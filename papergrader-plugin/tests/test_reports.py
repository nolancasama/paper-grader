"""Phase 4: teacher-facing reports and exports."""
import csv

import openpyxl
import pymupdf
import pytest

from conftest import below_student, edit_json, make_job, ninety_student, pending_student, ungraded_student
from papergrader import demo
from papergrader.common import Issues
from papergrader.grading_models import compute_outcome
from papergrader.pipeline import build_class, output_names
from papergrader.validator import validate_inputs, validate_reports


@pytest.fixture
def ctx(tmp_path, perfect_student):
    japanese = demo.SyntheticStudent("山田 花子", "12", {**demo._all_correct_written(), "1.5": "5"}, demo._judged({"1.5": ("incorrect", 0)}))
    context = make_job(tmp_path, [perfect_student, japanese, below_student(), pending_student(), ungraded_student()], label="2年1組")
    context.report = build_class(context.job, context.class_id)
    assert context.report["status"] != "BLOCKED", context.report["errors"]
    context.out = context.job.output_dir(context.class_id)
    return context


def pdf_text(path):
    with pymupdf.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)


def test_every_required_output_exists_with_a_class_specific_name(ctx):
    for name in output_names("c1").values():
        assert (ctx.out / name).is_file(), name
        assert name.startswith("c1_")
    assert (ctx.out / "c1_corrections_NORMAL_ORDER.pdf").is_file()
    assert (ctx.out / "c1_validation_report.json").is_file()


def test_the_roster_lists_every_student_in_scan_order(ctx):
    text = pdf_text(ctx.out / "c1_student_score_roster.pdf")
    assert "2年1組 — Student Scores" in text
    assert text.index("Aiko Sample") < text.index("山田 花子") < text.index("Seventy Pupil") < text.index("Pending Pupil")
    assert "100/100" in text and "90/100" in text and "70/100" in text
    assert text.count("Pending review") == 2
    assert "Unreadable" in text and "Not provided" not in text.split("Pending Pupil")[0]


def test_a_pending_student_shows_no_number_on_the_roster(ctx):
    with pymupdf.open(ctx.out / "c1_student_score_roster.pdf") as doc:
        words = doc[0].get_text()
    # The only totals on the page belong to the three confirmed students.
    assert sorted(token for token in words.split() if "/100" in token) == ["100/100", "70/100", "90/100"]


def test_the_roster_is_not_part_of_the_correction_page_count(ctx):
    with pymupdf.open(ctx.out / "c1_corrections_NORMAL_ORDER.pdf") as doc:
        assert doc.page_count == 5
        assert all(not page.get_text().strip() for page in doc)


def test_a_large_class_gets_more_roster_pages_not_tiny_text(tmp_path):
    from papergrader import reports
    from papergrader.grading_models import Identity, Outcome, PageMap, Student
    from fractions import Fraction

    students = [Student(i, Identity("read", f"Student {i}"), Identity("read", str(i)), [], [], None, None, "") for i in range(1, 91)]
    outcomes = {s.student_order: Outcome(s.student_order, True, Fraction(80), Fraction(100), Fraction(80), "none", ()) for s in students}

    class Stub:
        title = "T"
        test_version = "v"

    class Grading:
        pass

    grading = Grading()
    grading.students = students
    page_map = PageMap("c", "Big", "t", "v", "simplex", [], [])
    path = reports.build_roster(tmp_path / "r.pdf", Stub, page_map, grading, outcomes)
    with pymupdf.open(path) as doc:
        assert doc.page_count >= 2
        spans = [s["size"] for b in doc[0].get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]]
        assert min(spans) >= 7, "footers aside, table text stays readable"
        text = "\n".join(p.get_text() for p in doc)
    assert all(f"Student {i}\n" in text or f"Student {i}" in text for i in (1, 45, 90))
    assert text.count("Order") == doc_pages_with_header(path)


def doc_pages_with_header(path):
    with pymupdf.open(path) as doc:
        return doc.page_count


def test_results_csv_keeps_pending_distinct_from_zero(ctx):
    with open(ctx.out / "c1_student_results.csv", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [r["test_order"] for r in rows] == ["1", "2", "3", "4", "5"]
    assert rows[0]["total"] == "100" and rows[1]["total"] == "90" and rows[2]["total"] == "70"
    assert rows[3]["total"] == "Pending review" and rows[3]["Q1.3"] == "pending" and rows[3]["unresolved_questions"] == "1.3"
    assert rows[3]["percent"] == ""
    assert rows[4]["unresolved_questions"].split()[0] == "1.1"
    assert rows[2]["Q1.2"] == "0", "a real zero stays a zero"
    assert rows[1]["name"] == "山田 花子"


def test_the_answer_details_record_each_observation_and_its_image(ctx):
    with open(ctx.out / "c1_answer_details.csv", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 5 * 10
    first = rows[0]
    assert (first["question"], first["observed_answer"], first["decision"], first["symbol"], first["image_ref"]) == ("1.1", "3", "correct", "○", "slot-0001")
    assert first["method"] == "direct_visual"


def test_the_xlsx_matches_the_csv(ctx):
    book = openpyxl.load_workbook(ctx.out / "c1_student_results.xlsx")
    assert book.sheetnames == ["Students", "Answers", "Print order"]
    sheet = book["Students"]
    header = [c.value for c in sheet[1]]
    total = header.index("total")
    assert [sheet.cell(r, total + 1).value for r in range(2, 7)] == [100, 90, 70, "Pending review", "Pending review"]
    assert sheet.cell(3, header.index("name") + 1).value == "山田 花子"


def test_a_handwritten_formula_cannot_execute_in_a_spreadsheet(tmp_path):
    from papergrader import reports

    assert reports._safe_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert reports._safe_cell("+81") == "'+81"
    assert reports._safe_cell("Tanaka") == "Tanaka"
    assert reports._numeric("nan") == "nan" and reports._numeric("Pending review") == "Pending review" and reports._numeric("90") == 90


def test_the_summary_carries_a_review_list_and_warnings(ctx):
    text = pdf_text(ctx.out / "c1_grading_summary.pdf")
    assert "Teacher review list" in text and "Can't tell 1 from 7" in text
    assert "Pending review: 2" in text and "SYNTHETIC" in text


def test_the_answer_key_shows_the_personal_response_rule_not_just_the_teachers_example(ctx):
    text = pdf_text(ctx.out / "c1_answer_key_list.pdf")
    assert "Interpreted Answer Key" in text and "Personal" in text
    assert "September/9 is" in text and "only the teacher's example" in text
    for question_id in ("1.1", "2.2", "3.1", "4"):
        assert question_id in text


def test_the_reports_can_be_opened_and_are_valid(ctx):
    for name in ("c1_student_score_roster.pdf", "c1_grading_summary.pdf", "c1_answer_key_list.pdf", "c1_correction_PREVIEW_DO_NOT_PRINT.pdf"):
        with pymupdf.open(ctx.out / name) as doc:
            assert doc.page_count >= 1 and doc[0].get_pixmap(dpi=30).width > 0


def test_a_corrupt_roster_fails_validation(ctx):
    bundle = validate_inputs(ctx.job, ctx.class_id)
    (ctx.out / "c1_student_score_roster.pdf").write_bytes(b"not a pdf")
    issues = Issues()
    validate_reports({"roster": ctx.out / "c1_student_score_roster.pdf"}, bundle.page_map, bundle.grading, bundle.test, bundle.outcomes, issues) if False else None
    paths = {"summary": ctx.out / "c1_grading_summary.pdf", "broken": ctx.out / "c1_student_score_roster.pdf"}
    validate_reports(paths, bundle.page_map, bundle.grading, bundle.test, bundle.outcomes, issues)
    assert "pdf_unreadable" in issues.codes()


def test_a_missing_output_fails_validation(ctx):
    bundle = validate_inputs(ctx.job, ctx.class_id)
    issues = Issues()
    validate_reports({"roster": ctx.out / "gone.pdf"}, bundle.page_map, bundle.grading, bundle.test, bundle.outcomes, issues)
    assert "output_missing" in issues.codes()


def test_a_roster_that_shows_a_pending_student_as_scored_fails(ctx, tmp_path):
    bundle = validate_inputs(ctx.job, ctx.class_id)
    fake = tmp_path / "roster.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "100/100 90/100 70/100 0/100 0/100")
    doc.save(fake)
    issues = Issues()
    validate_reports({"roster": fake}, bundle.page_map, bundle.grading, bundle.test, bundle.outcomes, issues)
    assert "roster_pending_mismatch" in issues.codes()


def test_a_csv_total_that_disagrees_with_the_arithmetic_fails(ctx, tmp_path):
    bundle = validate_inputs(ctx.job, ctx.class_id)
    text = (ctx.out / "c1_student_results.csv").read_text(encoding="utf-8-sig").replace("Seventy Pupil,3,10,0,10,10,10,0,10,0,10,10,70", "Seventy Pupil,3,10,0,10,10,10,0,10,0,10,10,75")
    fake = tmp_path / "r.csv"
    fake.write_text(text, encoding="utf-8-sig")
    issues = Issues()
    validate_reports({"results_csv": fake}, bundle.page_map, bundle.grading, bundle.test, bundle.outcomes, issues)
    assert "results_total_mismatch" in issues.codes()
