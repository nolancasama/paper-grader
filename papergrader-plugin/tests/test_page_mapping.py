"""Phase 2: page mapping. A lost or shifted page prints marks on the wrong child's paper."""
from pathlib import Path

import pymupdf
import pytest

from conftest import below_student, edit_json, error_codes, make_job, ninety_student
from papergrader import demo
from papergrader.common import PaperGraderError, load_json, save_json, sha256_file
from papergrader.job import Job
from papergrader.pdf_processor import inventory_pdf, page_fingerprint, render_view
from papergrader.pipeline import build_class
from papergrader.validator import validate_inputs


def three(tmp_path, perfect_student, **kwargs):
    return make_job(tmp_path, [perfect_student, ninety_student(), below_student()], **kwargs)


def test_a_clean_class_passes(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    bundle = validate_inputs(ctx.job, ctx.class_id)
    assert bundle.issues.ok, bundle.issues.to_json()


def test_a_missing_student_page_blocks_the_build(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    edit_json(ctx.job.page_map_path(ctx.class_id), lambda d: (d["slots"].pop(1), [s.update(slot=i + 1) for i, s in enumerate(d["slots"])]))
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] == "BLOCKED" and "student_page_unmapped" in error_codes(report)


def test_a_duplicated_student_page_blocks_the_build(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)

    def duplicate(data):
        data["slots"][1]["source_page"] = data["slots"][0]["source_page"]

    edit_json(ctx.job.page_map_path(ctx.class_id), duplicate)
    assert "student_page_duplicated" in error_codes(build_class(ctx.job, ctx.class_id))


def test_a_source_page_that_does_not_exist_blocks_the_build(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    edit_json(ctx.job.page_map_path(ctx.class_id), lambda d: d["slots"][2].update(source_page=99))
    assert "source_page_invalid" in error_codes(build_class(ctx.job, ctx.class_id))


def test_swapped_pages_break_the_scan_order_check(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)

    def swap(data):
        data["slots"][0]["source_page"], data["slots"][1]["source_page"] = data["slots"][1]["source_page"], data["slots"][0]["source_page"]

    edit_json(ctx.job.page_map_path(ctx.class_id), swap)
    assert "scan_order_violation" in error_codes(build_class(ctx.job, ctx.class_id))


def test_slots_cannot_be_reordered_which_would_reverse_the_print_job(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    edit_json(ctx.job.page_map_path(ctx.class_id), lambda d: d["slots"].reverse())
    assert "slot_sequence_broken" in error_codes(build_class(ctx.job, ctx.class_id))


def test_a_grading_record_pointing_at_the_wrong_scan_page_is_caught(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"][0]["source_pages"][0].update(source_page=2))
    assert "source_page_mismatch" in error_codes(build_class(ctx.job, ctx.class_id))


def test_an_answer_citing_another_students_image_is_caught(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"][0]["answers"][0]["verification"].update(image_ref="slot-0002"))
    assert "image_ref_wrong_student" in error_codes(build_class(ctx.job, ctx.class_id))


def test_an_answer_citing_an_image_never_rendered_is_caught(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"][0]["answers"][0]["verification"].update(image_ref="slot-0001-view-999"))
    assert "image_ref_unknown" in error_codes(build_class(ctx.job, ctx.class_id))


def test_unconfirmed_rotation_blocks_the_build(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    edit_json(ctx.job.page_map_path(ctx.class_id), lambda d: d["slots"][1].update(rotation_status="unconfirmed"))
    assert "rotation_unconfirmed" in error_codes(build_class(ctx.job, ctx.class_id))


def test_a_proposed_map_needs_someone_to_confirm_every_rotation(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    data = ctx.job.propose_map(ctx.class_id, "Again", ["demo_c1_students.pdf"], replace=True)
    assert {s["rotation_status"] for s in data["slots"]} == {"unconfirmed"}


def test_a_double_fed_sheet_is_flagged(tmp_path, perfect_student):
    # The same paper scanned twice gives identical pages.
    ctx = make_job(tmp_path, [perfect_student, perfect_student])
    report = build_class(ctx.job, ctx.class_id)
    assert "duplicate_page_content" in error_codes(report)
    edit_json(ctx.job.page_map_path(ctx.class_id), lambda d: d.update(acknowledged_duplicates=[[1, 2]]))
    assert "duplicate_page_content" not in error_codes(build_class(ctx.job, ctx.class_id))


def test_a_source_file_changed_after_mapping_is_caught(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    path = ctx.job.source_path("demo_c1_students.pdf")
    path.write_bytes(path.read_bytes() + b"\n%changed")
    assert "source_hash_mismatch" in error_codes(build_class(ctx.job, ctx.class_id))


# ---------------------------------------------------------------------------
# Reference confirmation
# ---------------------------------------------------------------------------
def test_grading_is_blocked_until_the_teacher_confirms_the_references(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    edit_json(ctx.job.test_path, lambda d: d["references"]["teacher_confirmation"].update(confirmed=False))
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] == "BLOCKED" and "references_unconfirmed" in error_codes(report)


def test_a_draft_rubric_blocks_the_build(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    edit_json(ctx.job.test_path, lambda d: d.update(rubric_status="draft"))
    assert "rubric_not_approved" in error_codes(build_class(ctx.job, ctx.class_id))


def test_a_replaced_answer_key_file_is_caught(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    path = ctx.job.source_path("demo_key.pdf")
    path.write_bytes(path.read_bytes() + b"\n%changed")
    assert "reference_hash_mismatch" in error_codes(build_class(ctx.job, ctx.class_id))


def build_combined(tmp_path: Path, order: list[str], students) -> Path:
    """One PDF holding the blank, the key and students, with pages in the given order."""
    blank = pymupdf.open(demo.make_blank_pdf(tmp_path / "b.pdf"))
    key = pymupdf.open(demo.make_key_pdf(tmp_path / "k.pdf"))
    scans = pymupdf.open(demo.make_student_pdf(tmp_path / "s.pdf", students))
    out = pymupdf.open()
    sources = {"blank": (blank, 0), "key": (key, 0)}
    scan_index = 0
    for role in order:
        if role == "student":
            out.insert_pdf(scans, from_page=scan_index, to_page=scan_index)
            scan_index += 1
        else:
            out.insert_pdf(sources[role][0])
    path = tmp_path / "combined.pdf"
    out.save(path)
    for doc in (blank, key, scans, out):
        doc.close()
    return path


@pytest.mark.parametrize("order", [["blank", "key", "student", "student"], ["key", "blank", "student", "student"], ["student", "blank", "student", "key"]])
def test_a_combined_pdf_works_with_references_in_any_position(tmp_path, order):
    students = [ninety_student(), below_student()]
    root = tmp_path / "w"
    root.mkdir()
    combined = build_combined(root, order, students)
    job = Job.create(tmp_path / "job")
    job.add_source(combined)
    positions = {role: [i + 1 for i, r in enumerate(order) if r == role] for role in ("blank", "key")}
    test = demo.base_test_json(combined, combined, 1, positions["blank"], positions["key"])
    save_json(job.test_path, test)
    excluded = {"combined.pdf": {positions["blank"][0]: "blank", positions["key"][0]: "key"}}
    data = job.propose_map("mix", "Mix", ["combined.pdf"], excluded)
    student_pages = [s["source_page"] for s in data["slots"]]
    assert student_pages == [i + 1 for i, r in enumerate(order) if r == "student"]
    assert [s["student_order"] for s in data["slots"]] == [1, 2]
    job.set_rotation("mix", 0, None)
    job.scaffold_grading("mix", "teacher_manual", "fixture")
    assert validate_inputs(job, "mix").issues.ok


def test_a_reference_page_cannot_also_be_a_student_page(tmp_path):
    root = tmp_path / "w"
    root.mkdir()
    combined = build_combined(root, ["blank", "key", "student"], [ninety_student()])
    job = Job.create(tmp_path / "job")
    job.add_source(combined)
    save_json(job.test_path, demo.base_test_json(combined, combined, 1, [1], [2]))
    # Nothing excluded here, so the key lands among the students: it must be refused.
    job.propose_map("mix", "Mix", ["combined.pdf"])
    job.set_rotation("mix", 0, None)
    job.scaffold_grading("mix", "teacher_manual", "fixture")
    assert "reference_page_in_student_slots" in validate_inputs(job, "mix").issues.codes()


# ---------------------------------------------------------------------------
# Multi-page tests
# ---------------------------------------------------------------------------
def test_two_blank_sheets_are_not_mistaken_for_a_duplicate(tmp_path):
    """Blank pages legitimately look alike, unlike a filled-in page appearing twice."""
    doc = pymupdf.open()
    doc.new_page(width=595, height=842)
    doc.new_page(width=595, height=842)
    path = tmp_path / "blank_backs.pdf"
    doc.save(path)
    doc.close()
    assert page_fingerprint(path, 1) is None and page_fingerprint(path, 2) is None


def test_a_multi_page_test_groups_packets_and_prints_one_score(tmp_path, perfect_student):
    # The second student's page 2 differs, as two children's real papers would.
    second = demo.SyntheticStudent("Ninety Pupil", "2", {**demo._all_correct_written(), "3.1": "vehicle"}, demo._judged({"3.1": ("incorrect", 0)}))
    ctx = make_job(tmp_path, [perfect_student, second], template_pages=2)
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] == "AWAITING_VISUAL_AUDIT", report["errors"]
    assert report["counts"]["printable_pages"] == 4 and report["counts"]["students"] == 2
    plans = load_json(ctx.job.output_dir(ctx.class_id) / "c1_overlay_plan.json")["plans"]
    assert [p["student_order"] for p in plans] == [1, 1, 2, 2]
    assert [bool(p["score"]) for p in plans] == [True, False, True, False]
    assert plans[1]["marks"], "the second page still gets its own marks"
    # The border and stamp belong to the score page, not to every sheet.
    assert plans[0]["embroidery"] and plans[0]["stamp"] and not plans[1]["embroidery"] and not plans[1]["stamp"]


def test_a_multi_page_packet_with_a_lost_page_blocks_the_build(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student, ninety_student()], template_pages=2)

    def lose_last(data):
        data["slots"].pop()
        data["sources"][0]["excluded_pages"] = [{"page": 4, "role": "unknown"}]

    edit_json(ctx.job.page_map_path(ctx.class_id), lose_last)
    assert "packet_incomplete" in error_codes(build_class(ctx.job, ctx.class_id))


# ---------------------------------------------------------------------------
# Duplex
# ---------------------------------------------------------------------------
def test_simplex_is_the_default(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    data = load_json(ctx.job.page_map_path(ctx.class_id))
    assert data["paper_mode"] == "simplex" and all(s["side"] == "front" for s in data["slots"])
    assert len({s["physical_sheet"] for s in data["slots"]}) == 3


def test_duplex_maps_fronts_and_backs_and_warns_it_is_unverified(tmp_path, perfect_student):
    job = Job.create(tmp_path / "job")
    work = tmp_path / "w"
    work.mkdir()
    test = demo.setup_test(job, work, 2)
    demo.setup_class(job, work, "d", "Duplex", [perfect_student], test, paper_mode="duplex")
    data = load_json(job.page_map_path("d"))
    assert [(s["physical_sheet"], s["side"]) for s in data["slots"]] == [(1, "front"), (1, "back")]
    assert "duplex_unverified" in validate_inputs(job, "d").issues.codes()


def test_a_duplex_sheet_with_a_missing_back_is_refused(tmp_path, perfect_student):
    job = Job.create(tmp_path / "job")
    work = tmp_path / "w"
    work.mkdir()
    test = demo.setup_test(job, work, 2)
    demo.setup_class(job, work, "d", "Duplex", [perfect_student], test, paper_mode="duplex")
    edit_json(job.page_map_path("d"), lambda d: d["slots"][1].update(side="front"))
    assert "duplex_side_missing" in validate_inputs(job, "d").issues.codes()


# ---------------------------------------------------------------------------
# Rendering and the job folder
# ---------------------------------------------------------------------------
def test_inventory_reports_stored_rotation_and_no_text_layer(tmp_path):
    student = demo.SyntheticStudent("A", "1", demo._all_correct_written(), {}, stored_rotation=180)
    path = demo.make_student_pdf(tmp_path / "s.pdf", [student])
    info = inventory_pdf(path)
    assert info["pages"][0]["stored_rotation"] == 180 and info["pages"][0]["has_text_layer"] is False


def test_rendered_views_come_out_upright_with_a_stored_rotation_flag(tmp_path):
    """Regression guard: rendering must respect /Rotate; show_pdf_page alone does not."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=400)
    page.draw_rect(pymupdf.Rect(0, 0, 60, 60), color=None, fill=(1, 0, 0))
    page.set_rotation(180)  # displays upside down, with the block at the bottom right
    path = tmp_path / "r.pdf"
    doc.save(path)
    doc.close()
    out = tmp_path / "view.png"
    render_view(path, 1, 180, out, dpi=72)
    pix = pymupdf.Pixmap(str(out))
    index = (10 * pix.width + 10) * pix.n
    assert pix.samples[index] > 200 and pix.samples[index + 1] < 60, "rotating by 180 must bring the block back to the top left"


def test_a_crop_with_a_grid_is_written_to_a_temporary_view_only(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    before = sha256_file(ctx.job.source_path("demo_c1_students.pdf"))
    entry = ctx.job.render_slot(ctx.class_id, 1, dpi=100, rect_pct=(20, 10, 40, 20), zoom=2.0, grid=True)
    assert Path(entry["path"]).is_file() and entry["ref"] == "slot-0001-view-001"
    assert entry["width_px"] > entry["height_px"] > 0
    assert sha256_file(ctx.job.source_path("demo_c1_students.pdf")) == before
    assert ctx.job.load_renders(ctx.class_id)[entry["ref"]]["student_order"] == 1


def test_a_job_folder_inside_a_git_checkout_is_refused(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    with pytest.raises(PaperGraderError, match="inside a git checkout"):
        Job.create(tmp_path / "repo" / "jobs" / "class")


def test_a_source_name_cannot_escape_the_job_folder(tmp_path, perfect_student):
    ctx = three(tmp_path, perfect_student)
    with pytest.raises(PaperGraderError):
        ctx.job.source_path("../../secret.pdf")
    with pytest.raises(PaperGraderError):
        ctx.job.class_dir("../evil")
