"""Phase 2: correction overlays. Positions are checked by measuring the rendered page."""
import math

import pymupdf
import pytest

from conftest import below_student, edit_json, error_codes, has_ink, ink_center, make_job, ninety_student, pending_student, plans_of, ungraded_student
from papergrader import decorations, demo, printer_config
from papergrader.common import MM, Issues, PaperGraderError, load_json
from papergrader.correction_overlay import PageFrame
from papergrader.pipeline import build_class
from papergrader.validator import validate_correction_pdf


def corrections_path(ctx):
    return ctx.job.output_dir(ctx.class_id) / f"{ctx.class_id}_corrections_NORMAL_ORDER.pdf"


def preview_path(ctx):
    return ctx.job.output_dir(ctx.class_id) / f"{ctx.class_id}_correction_PREVIEW_DO_NOT_PRINT.pdf"


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_page_frame_agrees_with_the_renderer_at_every_rotation(rotation):
    """Draw a dot, render through the same rotation matrix, and see where it lands upright."""
    frame = PageFrame(300.0, 500.0, rotation)
    u, v = frame.upright_width * 0.2, frame.upright_height * 0.3
    x, y = frame.to_display(u, v)
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=500)
    page.draw_circle((x, y), 6, color=None, fill=(1, 0, 0))
    pix = page.get_pixmap(matrix=pymupdf.Matrix(1, 1).prerotate(rotation), alpha=False)
    assert (pix.width, pix.height) == (round(frame.upright_width), round(frame.upright_height))
    i = (round(v) * pix.width + round(u)) * pix.n
    assert pix.samples[i] > 200 and pix.samples[i + 1] < 60, f"dot missing at the expected upright position for rotation {rotation}"


@pytest.mark.parametrize("angle,expected", [(0, "left"), (90, "top"), (180, "right"), (270, "bottom")])
def test_art_rotation_turns_clockwise_as_documented(tmp_path, monkeypatch, angle, expected):
    """A block on the art's left end must move to the top after a 90 degree clockwise turn."""
    art = pymupdf.open()
    art_page = art.new_page(width=200, height=100)
    art_page.draw_rect(pymupdf.Rect(0, 0, 40, 100), color=None, fill=(1, 0, 0))
    art_page.draw_rect(pymupdf.Rect(40, 0, 200, 100), color=None, fill=(0, 0, 1))
    monkeypatch.setitem(decorations._art_cache, "test-art", art)
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=400)
    decorations.place_art(page, "test-art", (200, 200), 200, 100, angle)
    cx, cy = ink_center(page)
    assert {"left": cx < 190, "right": cx > 210, "top": cy < 190, "bottom": cy > 210}[expected], (cx, cy)


def test_score_lands_inside_the_score_box_and_adds_no_denominator(tmp_path):
    ctx = make_job(tmp_path, [below_student()])
    assert build_class(ctx.job, ctx.class_id)["status"] != "BLOCKED"
    plan = plans_of(ctx.job, ctx.class_id)[0]
    assert plan["score"]["text"] == "70"  # no "/100": the worksheet already prints it
    box = plan["score"]["box"]
    assert box == pytest.approx([70 * 595.276 / 100, 5.5 * 841.89 / 100, 81 * 595.276 / 100, 10.5 * 841.89 / 100], abs=0.5)
    with pymupdf.open(corrections_path(ctx)) as doc:
        page = doc[0]
        inside = page.get_pixmap(clip=pymupdf.Rect(box), alpha=True, dpi=72)
        assert any(bytes(inside.samples)[3::4])
        # Directly right of the box (where a duplicated "/100" would go) stays clean.
        right = page.get_pixmap(clip=pymupdf.Rect(box[2] + 1, box[1], box[2] + 80, box[3]), alpha=True, dpi=72)
        assert not any(bytes(right.samples)[3::4])


def test_a_denominator_is_printed_only_where_the_worksheet_lacks_one(tmp_path):
    changes = {"score_box": {"template_page": 1, "x_pct": 70, "y_pct": 5.5, "w_pct": 18, "h_pct": 5, "denominator_printed": False, "append_denominator": True}}
    ctx = make_job(tmp_path, [below_student()], **changes)
    assert build_class(ctx.job, ctx.class_id)["status"] != "BLOCKED"
    assert plans_of(ctx.job, ctx.class_id)[0]["score"]["text"] == "70/100"


def test_correct_partial_and_incorrect_each_draw_their_own_symbol(tmp_path):
    student = demo.SyntheticStudent("X", "1", demo._all_correct_written(), demo._judged({"1.1": ("partial", 5), "1.2": ("incorrect", 0)}))
    ctx = make_job(tmp_path, [student])
    assert build_class(ctx.job, ctx.class_id)["status"] != "BLOCKED"
    symbols = {m["question_id"]: m["symbol"] for m in plans_of(ctx.job, ctx.class_id)[0]["marks"]}
    assert (symbols["1.1"], symbols["1.2"], symbols["1.3"]) == ("partial", "incorrect", "correct")


def test_a_pending_answer_gets_no_mark_and_the_score_box_stays_blank(tmp_path):
    ctx = make_job(tmp_path, [pending_student()])
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != "BLOCKED", report["errors"]
    plan = plans_of(ctx.job, ctx.class_id)[0]
    assert "1.3" not in {m["question_id"] for m in plan["marks"]} and len(plan["marks"]) == 9
    assert plan["score"] is None and plan["stamp"] is None and plan["embroidery"] is None
    with pymupdf.open(corrections_path(ctx)) as doc:
        score_area = pymupdf.Rect(70 * 5.95, 5.5 * 8.42, 88 * 5.95, 10.5 * 8.42)
        assert not any(bytes(doc[0].get_pixmap(clip=score_area, alpha=True, dpi=72).samples)[3::4])


def test_a_completely_ungraded_page_is_still_present_and_fully_blank(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [ninety_student(), ungraded_student(), below_student()])
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != "BLOCKED", report["errors"]
    with pymupdf.open(corrections_path(ctx)) as doc:
        assert doc.page_count == 3
        assert not has_ink(doc[1], dpi=72)
        assert has_ink(doc[0]) and has_ink(doc[2]), "neighbours keep their own marks"


def test_page_size_and_order_match_the_stack(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [ninety_student(), below_student(), perfect_student])
    build_class(ctx.job, ctx.class_id)
    with pymupdf.open(corrections_path(ctx)) as doc:
        assert doc.page_count == 3
        for page in doc:
            assert (round(page.rect.width), round(page.rect.height)) == (595, 842) and page.rotation == 0
    # Normal order: PDF page N carries student N's own score, in scan order.
    assert [p["score"]["text"] for p in plans_of(ctx.job, ctx.class_id)] == ["90", "70", "100"]
    assert [p["student_order"] for p in plans_of(ctx.job, ctx.class_id)] == [1, 2, 3]


def test_print_order_mapping_lists_every_page_in_normal_order(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [ninety_student(), perfect_student])
    build_class(ctx.job, ctx.class_id)
    text = (ctx.job.output_dir(ctx.class_id) / "c1_print_order_mapping.csv").read_text(encoding="utf-8-sig")
    assert "Normal-order PDF page 1 -> original test order 1, page 1" in text
    assert "Normal-order PDF page 2 -> original test order 2, page 1" in text


def test_a_profile_cannot_ask_for_reversed_output():
    profile = printer_config.bundled_profile()
    profile["pdf_order"] = "reverse"
    assert any("normal" in problem for problem in printer_config.validate_profile(profile))


def test_the_bundled_printer_profile_matches_the_locked_setup():
    profile = printer_config.bundled_profile()
    assert printer_config.validate_profile(profile) == []
    assert profile["printer"] == "RISO ORPHIS GL7430" and profile["pdf_order"] == "normal" and profile["paper_mode"] == "simplex"
    assert "pull-out" in profile["tray"] and "face down" in profile["paper_face"] and "100%" in profile["scale"]
    assert "逆順印刷" in profile["reverse_order_setting"] and profile["calibration"]["physically_verified"] is False


# ---------------------------------------------------------------------------
# Rotated scans
# ---------------------------------------------------------------------------
def expected_display_point(x_pct, y_pct, rotation, width=595.276, height=841.89):
    frame = PageFrame(width, height, rotation)
    return frame.to_display(*frame.pct(x_pct, y_pct))


@pytest.mark.parametrize("raster,stored", [(180, 0), (0, 180), (180, 180)])
def test_upside_down_scans_get_marks_where_the_answer_really_is(tmp_path, raster, stored):
    """Only question 1.1 gets a mark, so its position can be measured directly."""
    student = demo.SyntheticStudent("Upside Down", "1", {"1.1": "3"}, {"1.1": ("correct", 10)}, raster_rotation=raster, stored_rotation=stored)
    ctx = make_job(tmp_path, [student])
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != "BLOCKED", report["errors"]
    rotation = (360 - (raster + stored) % 360) % 360
    x, y = expected_display_point(36, 15.8, rotation)
    with pymupdf.open(corrections_path(ctx)) as doc:
        assert doc[0].rotation == 0, "overlay pages carry no rotation flag; they match the sheet as fed"
        cx, cy = ink_center(doc[0])
    assert (cx, cy) == pytest.approx((x, y), abs=4.0)
    if rotation == 180:
        assert cy > 842 * 0.6, "the mark belongs at the bottom of an upside-down sheet"


def test_a_sideways_scan_keeps_its_page_shape_and_places_marks_correctly(tmp_path):
    student = demo.SyntheticStudent("Sideways", "1", {"1.1": "3"}, {"1.1": ("correct", 10)}, raster_rotation=90)
    ctx = make_job(tmp_path, [student])
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != "BLOCKED", report["errors"]
    with pymupdf.open(corrections_path(ctx)) as doc:
        assert (round(doc[0].rect.width), round(doc[0].rect.height)) == (842, 595)
        cx, cy = ink_center(doc[0])
    x, y = PageFrame(841.89, 595.276, 270).to_display(*PageFrame(841.89, 595.276, 270).pct(36, 15.8))
    assert (cx, cy) == pytest.approx((x, y), abs=4.0)


@pytest.mark.parametrize("raster,stored", [(180, 0), (0, 180)])
def test_the_preview_shows_the_scan_in_the_same_orientation_as_the_marks(tmp_path, raster, stored):
    """The trap: show_pdf_page ignores /Rotate, which would flip the scan under the marks."""
    student = demo.SyntheticStudent("Preview", "1", {"1.1": "3"}, {"1.1": ("correct", 10)}, raster_rotation=raster, stored_rotation=stored)
    ctx = make_job(tmp_path, [student])
    build_class(ctx.job, ctx.class_id)
    source = ctx.job.source_path("demo_c1_students.pdf")
    with pymupdf.open(source) as scan, pymupdf.open(preview_path(ctx)) as preview:
        scan_pix = scan[0].get_pixmap(dpi=36, colorspace=pymupdf.csGRAY, alpha=False)
        preview_pix = preview[0].get_pixmap(dpi=36, colorspace=pymupdf.csGRAY, alpha=False)
        assert (scan_pix.width, scan_pix.height) == (preview_pix.width, preview_pix.height)
        difference = sum(abs(a - b) for a, b in zip(scan_pix.samples, preview_pix.samples)) / len(scan_pix.samples)
    assert difference < 6, f"the preview doesn't match the scan as displayed (mean difference {difference:.1f})"


def test_a_stamp_on_an_upside_down_sheet_is_itself_upside_down(tmp_path):
    student = demo.SyntheticStudent("Flip", "1", demo._all_correct_written(), demo._judged(), raster_rotation=180)
    ctx = make_job(tmp_path, [student])
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != "BLOCKED", report["errors"]
    plan = plans_of(ctx.job, ctx.class_id)[0]
    frame = PageFrame(plan["page_width_pt"], plan["page_height_pt"], 180)
    x, y = frame.to_display(plan["stamp"]["cx"], plan["stamp"]["cy"])
    assert y > plan["page_height_pt"] / 2, "the upright top zone is at the bottom of this sheet"
    with pymupdf.open(corrections_path(ctx)) as doc:
        probe = pymupdf.Rect(x - 20, y - 20, x + 20, y + 20)
        assert any(bytes(doc[0].get_pixmap(clip=probe, alpha=True, dpi=72).samples)[3::4])


# ---------------------------------------------------------------------------
# Printer calibration
# ---------------------------------------------------------------------------
def test_printer_offsets_move_the_printable_pdf_but_not_the_preview(tmp_path):
    student = demo.SyntheticStudent("Offset", "1", {"1.1": "3"}, {"1.1": ("correct", 10)})
    ctx = make_job(tmp_path, [student])
    build_class(ctx.job, ctx.class_id)
    with pymupdf.open(corrections_path(ctx)) as doc:
        x0, y0 = ink_center(doc[0])
    printer_config.set_offsets(ctx.job.profile_path, 3.0, -2.0)
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != "BLOCKED", report["errors"]
    with pymupdf.open(corrections_path(ctx)) as doc:
        x1, y1 = ink_center(doc[0])
    assert x1 - x0 == pytest.approx(3.0 * MM, abs=1.2) and y1 - y0 == pytest.approx(-2.0 * MM, abs=1.2)
    with pymupdf.open(preview_path(ctx)) as doc:
        px, py = ink_center(doc[0])
    assert (px, py) == pytest.approx((x0, y0), abs=1.5), "the preview shows intended placement, without printer compensation"


def test_an_offset_that_pushes_art_off_the_page_blocks_the_build(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    printer_config.set_offsets(ctx.job.profile_path, -20.0, 0.0)
    assert "offset_pushes_art_off_page" in error_codes(build_class(ctx.job, ctx.class_id))


def test_setting_an_offset_clears_any_earlier_physical_confirmation(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    printer_config.confirm_calibration(ctx.job.profile_path, "The test print lined up.")
    assert ctx.job.load_profile()["calibration"]["physically_verified"] is True
    printer_config.set_offsets(ctx.job.profile_path, 1.0, 1.0)
    assert ctx.job.load_profile()["calibration"]["physically_verified"] is False


def test_physical_confirmation_requires_the_teachers_own_words(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    with pytest.raises(PaperGraderError):
        printer_config.confirm_calibration(ctx.job.profile_path, "   ")


def test_the_calibration_pdf_has_numbered_sheets_and_warns_it_is_for_photocopies(tmp_path):
    path = printer_config.build_calibration_pdf(tmp_path / "cal.pdf", "A4", 3)
    with pymupdf.open(path) as doc:
        assert doc.page_count == 3
        assert (round(doc[0].rect.width), round(doc[0].rect.height)) == (595, 842)
        text = doc[0].get_text()
        assert "PHOTOCOPIES ONLY" in text and "RISO ORPHIS GL7430" in text and "逆順印刷" in text
        assert "sheet 3 of 3" in doc[2].get_text()


def test_the_calibration_crosshair_lands_exactly_where_it_is_labelled(tmp_path):
    path = printer_config.build_calibration_pdf(tmp_path / "cal.pdf", "A4", 1)
    with pymupdf.open(path) as doc:
        # Stop short of 26 mm, where the cross's own red label begins.
        clip = pymupdf.Rect(14 * MM, 10 * MM, 26 * MM, 26 * MM)
        pix = doc[0].get_pixmap(clip=clip, dpi=144, alpha=False)
        xs, ys = [], []
        for y in range(pix.height):
            for x in range(pix.width):
                i = (y * pix.width + x) * pix.n
                if pix.samples[i] > 170 and pix.samples[i + 1] < 90 and pix.samples[i + 2] < 90:
                    xs.append(x)
                    ys.append(y)
        assert (min(xs) + max(xs)) / 2 / 2 + 14 * MM == pytest.approx(20 * MM, abs=1.0)
        assert (min(ys) + max(ys)) / 2 / 2 + 10 * MM == pytest.approx(20 * MM, abs=1.0)


def test_a_calibration_sheet_can_carry_the_real_tests_positions(tmp_path):
    targets = {1: [("score", 75.0, 8.0), ("1.1", 36.0, 15.8)]}
    path = printer_config.build_calibration_pdf(tmp_path / "cal.pdf", "A4", 2, targets=targets)
    with pymupdf.open(path) as doc:
        assert "score" in doc[0].get_text() and "1.1" in doc[0].get_text()


# ---------------------------------------------------------------------------
# Validator: a page that contains anything unplanned fails
# ---------------------------------------------------------------------------
def test_stray_vector_ink_is_caught_even_though_it_is_not_text(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [ninety_student()])
    build_class(ctx.job, ctx.class_id)
    path = corrections_path(ctx)
    with pymupdf.open(path) as doc:
        doc[0].draw_rect(pymupdf.Rect(40, 600, 80, 640), color=(0, 0, 0), width=1)
        tampered = tmp_path / "tampered.pdf"
        doc.save(tampered)
    issues = Issues()
    validate_correction_pdf(tampered, plans_of(ctx.job, ctx.class_id), (0, 0), issues)
    assert "ink_outside_planned_areas" in issues.codes()


def test_a_mark_placed_outside_its_answer_region_blocks_the_build(tmp_path):
    ctx = make_job(tmp_path, [ninety_student()])
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"][0]["answers"][0].update(mark={"x_pct": 90, "y_pct": 90}))
    assert "mark_outside_answer_region" in error_codes(build_class(ctx.job, ctx.class_id))


def test_a_per_student_content_offset_moves_marks_with_the_shifted_print(tmp_path):
    student = demo.SyntheticStudent("Shift", "1", {"1.1": "3"}, {"1.1": ("correct", 10)})
    ctx = make_job(tmp_path, [student])
    build_class(ctx.job, ctx.class_id)
    with pymupdf.open(corrections_path(ctx)) as doc:
        x0, _ = ink_center(doc[0])
    edit_json(ctx.job.page_map_path(ctx.class_id), lambda d: d["slots"][0].update(content_offset_pct={"dx": 2, "dy": 0}))
    build_class(ctx.job, ctx.class_id)
    with pymupdf.open(corrections_path(ctx)) as doc:
        x1, _ = ink_center(doc[0])
    assert x1 - x0 == pytest.approx(0.02 * 595.276, abs=1.2)
