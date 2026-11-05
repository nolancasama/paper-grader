"""Phase 3: stamps and embroidery are proven present by rendering, and absence is a failure."""
import math
import re
from pathlib import Path

import pymupdf
import pytest

from conftest import below_student, error_codes, make_job, ninety_student, pending_student, plans_of, ungraded_student
from papergrader import decorations
from papergrader.common import ASSETS_DIR, MM, Issues, PaperGraderError
from papergrader.correction_overlay import planned_rects
from papergrader.decorations import InkMap, analyze_region
from papergrader.pipeline import BLOCKED, build_class
from papergrader.validator import validate_correction_pdf, validate_preview_pdf


def corrections_path(ctx):
    return ctx.job.output_dir(ctx.class_id) / f"{ctx.class_id}_corrections_NORMAL_ORDER.pdf"


def preview_path(ctx):
    return ctx.job.output_dir(ctx.class_id) / f"{ctx.class_id}_correction_PREVIEW_DO_NOT_PRINT.pdf"


def measure(page, box, zoom=2.0):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
    return analyze_region(bytes(pix.samples), pix.width, pix.height, zoom, box)


@pytest.fixture
def perfect_ctx(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    ctx.report = build_class(ctx.job, ctx.class_id)
    assert ctx.report["status"] != BLOCKED, ctx.report["errors"]
    return ctx


# ---------------------------------------------------------------------------
# The mandatory test from the plan
# ---------------------------------------------------------------------------
def test_mandatory_a_verified_100_shows_embroidery_and_a_perfect_stamp_in_both_pdfs(perfect_ctx, tmp_path):
    """Render both PDFs to images, and measure the art on the resulting pixels."""
    plan = plans_of(perfect_ctx.job, perfect_ctx.class_id)[0]
    rects = planned_rects(plan)
    assert plan["stamp"]["kind"] == "perfect" and "perfect_" in plan["stamp"]["asset"]
    assert plan["embroidery"]["kept"] >= plan["embroidery"]["planned"] * 0.7

    with pymupdf.open(corrections_path(perfect_ctx)) as doc:
        page = doc[0]
        assert not page.get_images(), "marks-only: no scan or raster in the printable PDF"
        assert not page.get_text().strip(), "marks-only: no text objects at all"
        stamp = measure(page, rects["stamp"][0])
        assert stamp.coverage > 0.25 and stamp.families >= 4, stamp
        # Thread colours reach all four sides of the page.
        tiles = plan["embroidery"]["tiles"]
        assert {t["edge"] for t in tiles} >= {"top", "right", "bottom", "left"}
        everything = (min(b[0] for b in rects["embroidery"]), min(b[1] for b in rects["embroidery"]), max(b[2] for b in rects["embroidery"]), max(b[3] for b in rects["embroidery"]))
        assert measure(page, everything).families >= 5
        for box in rects["embroidery"]:
            assert measure(page, box).coverage > 0.012, "each motif is really there"

    with pymupdf.open(preview_path(perfect_ctx)) as doc:
        pix = pymupdf.Pixmap(doc[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False), 1)
        samples = bytes(pix.samples)
        assert analyze_region(samples, pix.width, pix.height, 2.0, rects["stamp"][0]).families >= 4
        for box in rects["embroidery"]:
            assert analyze_region(samples, pix.width, pix.height, 2.0, box).families >= 1


def test_missing_embroidery_fails_validation(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    report = build_class(ctx.job, ctx.class_id, _skip_embroidery=True)
    assert report["status"] == BLOCKED and "embroidery_missing" in error_codes(report)
    assert report["checks"]["perfect_has_stamp_and_embroidery"] == "failed"
    assert "PRINT" in (ctx.job.output_dir(ctx.class_id) / "PRINT_STATUS.txt").read_text(encoding="utf-8")
    assert not (ctx.job.output_dir(ctx.class_id) / "c1_corrections_NORMAL_ORDER.pdf").exists(), "a failed file must not keep the print-ready name"
    assert (ctx.job.output_dir(ctx.class_id) / "NOT_PRINT_READY" / "NOT_PRINT_READY_c1_corrections_NORMAL_ORDER.pdf").exists()


def test_a_missing_stamp_fails_validation(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    report = build_class(ctx.job, ctx.class_id, _skip_stamp=True)
    assert report["status"] == BLOCKED and "stamp_missing" in error_codes(report)


def test_a_missing_praise_stamp_fails_validation(tmp_path):
    ctx = make_job(tmp_path, [ninety_student()])
    report = build_class(ctx.job, ctx.class_id, _skip_stamp=True)
    assert report["status"] == BLOCKED and "stamp_missing" in error_codes(report)


def _replace_page(ctx, tmp_path, draw) -> Path:
    """A correction PDF whose art was swapped for something cheaper."""
    plan = plans_of(ctx.job, ctx.class_id)[0]
    doc = pymupdf.open()
    page = doc.new_page(width=plan["page_width_pt"], height=plan["page_height_pt"])
    draw(page, plan)
    path = tmp_path / "substitute.pdf"
    doc.save(path)
    doc.close()
    return path


def test_a_plain_red_rectangle_cannot_pass_for_embroidery(perfect_ctx, tmp_path):
    def draw(page, plan):
        rects = planned_rects(plan)
        for box in rects["embroidery"]:
            page.draw_rect(pymupdf.Rect(box), color=(0.84, 0.04, 0.1), width=2)

    path = _replace_page(perfect_ctx, tmp_path, draw)
    issues = Issues()
    validate_correction_pdf(path, plans_of(perfect_ctx.job, perfect_ctx.class_id), (0, 0), issues)
    assert "embroidery_not_multicolor" in issues.codes()


def test_a_text_only_stamp_cannot_pass_for_illustrated_art(perfect_ctx, tmp_path):
    def draw(page, plan):
        box = pymupdf.Rect(planned_rects(plan)["stamp"][0])
        page.draw_rect(box, color=None, fill=(0.84, 0.04, 0.1))

    path = _replace_page(perfect_ctx, tmp_path, draw)
    issues = Issues()
    validate_correction_pdf(path, plans_of(perfect_ctx.job, perfect_ctx.class_id), (0, 0), issues)
    assert "stamp_not_illustrated" in issues.codes()


@pytest.mark.parametrize("label", ["REVIEW", "PENDING", "pending review", "?", "要確認"])
def test_forbidden_status_text_on_a_correction_page_fails(perfect_ctx, tmp_path, label):
    with pymupdf.open(corrections_path(perfect_ctx)) as doc:
        page = doc[0]
        writer = pymupdf.TextWriter(page.rect)
        writer.append((100, 500), label, font=pymupdf.Font("cjk"), fontsize=20)
        writer.write_text(page)
        path = tmp_path / "labelled.pdf"
        doc.save(path)
    issues = Issues()
    validate_correction_pdf(path, plans_of(perfect_ctx.job, perfect_ctx.class_id), (0, 0), issues)
    assert "forbidden_status_text" in issues.codes()


def test_a_forbidden_label_on_the_preview_fails_too(perfect_ctx, tmp_path):
    with pymupdf.open(preview_path(perfect_ctx)) as doc:
        doc[0].insert_text((100, 500), "REVIEW", fontsize=20)
        path = tmp_path / "labelled_preview.pdf"
        doc.save(path)
    issues = Issues()
    validate_preview_pdf(path, plans_of(perfect_ctx.job, perfect_ctx.class_id), issues)
    assert "forbidden_status_text" in issues.codes()


def test_a_scanned_background_in_the_printable_pdf_fails(perfect_ctx, tmp_path):
    with pymupdf.open(corrections_path(perfect_ctx)) as doc:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
        pix.clear_with(200)
        doc[0].insert_image(pymupdf.Rect(0, 0, 595, 842), pixmap=pix, overlay=False)
        path = tmp_path / "with_background.pdf"
        doc.save(path)
    issues = Issues()
    validate_correction_pdf(path, plans_of(perfect_ctx.job, perfect_ctx.class_id), (0, 0), issues)
    assert "correction_contains_image" in issues.codes()


def test_a_page_dropped_from_the_correction_pdf_fails(perfect_ctx, tmp_path):
    plans = plans_of(perfect_ctx.job, perfect_ctx.class_id)
    issues = Issues()
    validate_correction_pdf(corrections_path(perfect_ctx), plans + [plans[0]], (0, 0), issues)
    assert "page_count_mismatch" in issues.codes()


def test_a_missing_art_file_blocks_instead_of_printing_without_art(tmp_path, perfect_student, monkeypatch):
    ctx = make_job(tmp_path, [perfect_student])
    monkeypatch.setattr(decorations, "ASSETS_DIR", tmp_path / "no_such_assets")
    monkeypatch.setattr(decorations, "_art_cache", {})
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] == BLOCKED and "art_asset_missing" in error_codes(report)


# ---------------------------------------------------------------------------
# Who earns what
# ---------------------------------------------------------------------------
def test_ninety_gets_a_praise_stamp_but_no_embroidery(tmp_path):
    ctx = make_job(tmp_path, [ninety_student()])
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != BLOCKED, report["errors"]
    plan = plans_of(ctx.job, ctx.class_id)[0]
    assert plan["stamp"]["kind"] == "praise" and plan["embroidery"] is None
    with pymupdf.open(corrections_path(ctx)) as doc:
        assert measure(doc[0], planned_rects(plan)["stamp"][0]).families >= 3


def test_below_ninety_gets_only_red(tmp_path):
    ctx = make_job(tmp_path, [below_student()])
    assert build_class(ctx.job, ctx.class_id)["status"] != BLOCKED
    plan = plans_of(ctx.job, ctx.class_id)[0]
    assert plan["stamp"] is None and plan["embroidery"] is None
    with pymupdf.open(corrections_path(ctx)) as doc:
        report = measure(doc[0], (0, 0, doc[0].rect.width, doc[0].rect.height))
    assert report.red_share > 0.98 and report.families <= 2, "red marks only"


@pytest.mark.parametrize("make", [pending_student, ungraded_student])
def test_unresolved_students_get_no_art_even_if_most_answers_are_right(tmp_path, make):
    ctx = make_job(tmp_path, [make()])
    assert build_class(ctx.job, ctx.class_id)["status"] != BLOCKED
    plan = plans_of(ctx.job, ctx.class_id)[0]
    assert plan["stamp"] is None and plan["embroidery"] is None and plan["score"] is None


def test_the_perfect_stamp_is_larger_than_any_praise_stamp():
    assert decorations.PERFECT_WIDTH_MM * 0.97 * 0.8 > decorations.PRAISE_WIDTH_MM * 1.03


# ---------------------------------------------------------------------------
# Hand-stamped variation
# ---------------------------------------------------------------------------
def test_stamp_variation_stays_within_the_specified_ranges_and_goes_both_ways():
    values = [decorations.stamp_variation(f"test|v|class|{order}") for order in range(1, 200)]
    assert all(2.0 <= abs(v["dx_mm"]) <= 6.0 for v in values)
    assert all(1.0 <= abs(v["dy_mm"]) <= 4.0 for v in values)
    assert all(2.0 <= abs(v["angle_deg"]) <= 7.0 for v in values)
    assert {v["angle_deg"] > 0 for v in values} == {True, False}
    assert {v["dx_mm"] > 0 for v in values} == {True, False}


def test_each_student_gets_a_different_position_but_the_same_one_every_time():
    assert decorations.stamp_variation("a|1") == decorations.stamp_variation("a|1")
    assert decorations.stamp_variation("a|1") != decorations.stamp_variation("a|2")


def test_a_rebuild_produces_identical_pixels(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student, ninety_student()])
    build_class(ctx.job, ctx.class_id)
    with pymupdf.open(corrections_path(ctx)) as doc:
        first = [bytes(p.get_pixmap(dpi=72, alpha=True).samples) for p in doc]
    build_class(ctx.job, ctx.class_id)
    with pymupdf.open(corrections_path(ctx)) as doc:
        second = [bytes(p.get_pixmap(dpi=72, alpha=True).samples) for p in doc]
    assert first == second


def test_a_batch_uses_more_than_one_character_and_placement():
    assets = {decorations.choose_stamp_asset("praise", f"t|v|c|{i}") for i in range(30)}
    assert len({re.search(r"_(girl|boy|cat|rabbit|dragon)\.svg", a).group(1) for a in assets}) >= 4
    assert len({re.search(r"praise_(\w+?)_(girl|boy|cat|rabbit|dragon)", a).group(1) for a in assets}) >= 3


# ---------------------------------------------------------------------------
# Decorations must never cover content
# ---------------------------------------------------------------------------
ZONE = (200.0, 100.0, 500.0, 400.0)


def test_a_stamp_stays_inside_its_zone_after_rotation_and_jitter():
    for order in range(30):
        stamp = decorations.plan_stamp("perfect", f"seed-{order}", ZONE, [], InkMap.empty())
        assert stamp is not None
        x0, y0, x1, y1 = stamp["box"]
        assert x0 >= ZONE[0] and y0 >= ZONE[1] and x1 <= ZONE[2] and y1 <= ZONE[3]


def test_a_stamp_shrinks_its_variation_rather_than_overlap_a_blocker():
    free = decorations.plan_stamp("praise", "seed-1", ZONE, [], InkMap.empty())
    x0, y0, x1, y1 = free["box"]
    # Nudge a blocker into the corner the jittered stamp occupies.
    near_x = x0 if free["cx"] < (ZONE[0] + ZONE[2]) / 2 else x1 - 2
    blocker = (near_x, y0, near_x + 2, y0 + 2)
    moved = decorations.plan_stamp("praise", "seed-1", ZONE, [blocker], InkMap.empty())
    assert moved is not None and moved["variation_factor"] < 1.0
    assert not decorations._overlaps(tuple(moved["box"]), blocker)


def test_a_stamp_that_cannot_fit_is_reported_not_dropped(tmp_path, perfect_student):
    tiny = {"template_page": 1, "x_pct": 50, "y_pct": 12, "w_pct": 8, "h_pct": 5}
    ctx = make_job(tmp_path, [perfect_student], stamp_zone=tiny)
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] == BLOCKED and "stamp_no_safe_position" in error_codes(report)


def test_a_stamp_avoids_handwriting_found_on_the_scan(tmp_path):
    """A doodle in the stamp zone: the art must not land on it."""
    width, height = 200, 200
    gray = bytearray(b"\xff" * (width * height))
    for y in range(60, 140):
        for x in range(60, 140):
            gray[y * width + x] = 0  # solid ink in the middle
    ink = InkMap(width, height, bytes(gray), 200.0, 200.0)
    assert decorations.plan_stamp("praise", "s", (0, 0, 200, 200), [], ink) is None
    clear = decorations.plan_stamp("praise", "s", (0, 0, 200, 200), [], InkMap.empty())
    assert clear is not None


def test_embroidery_drops_motifs_that_would_touch_a_protected_region():
    page_w, page_h = 595.0, 842.0
    full = decorations.plan_embroidery(page_w, page_h, [], InkMap.empty(), 6.0, "s")
    assert full["sufficient"] and full["kept"] == full["planned"]
    title = (100.0, 15.0, 400.0, 40.0)  # printed right across the top band
    interrupted = decorations.plan_embroidery(page_w, page_h, [title], InkMap.empty(), 6.0, "s")
    assert interrupted["kept"] < interrupted["planned"]
    for tile in interrupted["tiles"]:
        assert not decorations._overlaps(tuple(tile["box"]), title)


def test_embroidery_stays_inside_the_printers_safe_margin():
    margin = 6.0
    plan = decorations.plan_embroidery(595.0, 842.0, [], InkMap.empty(), margin, "s")
    edge = margin * MM
    for tile in plan["tiles"]:
        x0, y0, x1, y1 = tile["box"]
        assert x0 >= edge - 0.01 and y0 >= edge - 0.01 and x1 <= 595.0 - edge + 0.01 and y1 <= 842.0 - edge + 0.01


def test_a_page_with_no_room_for_the_border_fails_closed(tmp_path, perfect_student):
    everywhere = [{"template_page": 1, "x_pct": 0, "y_pct": 0, "w_pct": 100, "h_pct": 11, "label": "x"}, {"template_page": 1, "x_pct": 0, "y_pct": 89, "w_pct": 100, "h_pct": 11, "label": "x"}, {"template_page": 1, "x_pct": 0, "y_pct": 0, "w_pct": 8, "h_pct": 100, "label": "x"}, {"template_page": 1, "x_pct": 92, "y_pct": 0, "w_pct": 8, "h_pct": 100, "label": "x"}]
    ctx = make_job(tmp_path, [perfect_student], protected_regions=everywhere)
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] == BLOCKED and "embroidery_no_safe_area" in error_codes(report)


def test_a_narrower_border_is_tried_before_giving_up():
    # A blocker across the top of the regular band, leaving room only for a narrower one.
    band_end = (6 + 7 * 0.7 + 0.2) * MM
    blocker = (0.0, band_end, 595.0, band_end + 60)
    wide = decorations.plan_embroidery(595.0, 842.0, [blocker], InkMap.empty(), 6.0, "s")
    assert wide["scale"] < 1.0 and wide["sufficient"]


# ---------------------------------------------------------------------------
# The art itself
# ---------------------------------------------------------------------------
def test_every_required_art_file_exists():
    assert [str(p) for p in decorations.required_assets() if not p.is_file()] == []


def test_stamp_art_is_original_vector_with_no_fonts_or_embedded_images():
    for path in decorations.required_assets():
        svg = path.read_text(encoding="utf-8")
        assert "<image" not in svg and "<text" not in svg and "font-family" not in svg and "href" not in svg, path.name


@pytest.mark.parametrize("asset", ["stamps/perfect_girl.svg", "stamps/perfect_boy.svg", "stamps/perfect_cat.svg", "stamps/perfect_rabbit.svg", "stamps/perfect_dragon.svg", "stamps/praise_great_job_girl.svg", "stamps/praise_excellent_cat.svg", "stamps/praise_amazing_dragon.svg", "stamps/praise_genius_boy.svg"])
def test_each_stamp_renders_in_full_colour(asset):
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=250)
    decorations.place_art(page, asset, (150, 125), 260, 200, 0)
    report = measure(page, (0, 0, 300, 250))
    assert report.coverage > 0.3 and report.families >= 4, (asset, report)


def test_embroidery_has_fine_stitches_not_flat_shapes():
    svg = (ASSETS_DIR / "embroidery" / "edge_0.svg").read_text(encoding="utf-8")
    assert svg.count("<path") > 300, "needlework is built from hundreds of individual stitches"
    used = {c.lower() for c in re.findall(r'stroke="(#[0-9a-fA-F]{6})"', svg)}
    assert len(used) >= 12, "many thread shades"
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=80)
    decorations.place_art(page, "embroidery/edge_0.svg", (100, 40), 180, 70, 0)
    assert measure(page, (0, 0, 200, 80)).families >= 5
