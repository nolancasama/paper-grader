"""Phase 5: the whole workflow, the safety guards around it, and the plugin package."""
import ast
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pymupdf
import pytest

from conftest import PLUGIN_ROOT, below_student, edit_json, error_codes, make_job, ninety_student, pending_student, plans_of
from papergrader import demo, printer_config, vision_check
from papergrader.common import Issues, PaperGraderError, load_json, save_json, sha256_file
from papergrader.job import Job
from papergrader.pipeline import AWAITING_AUDIT, BLOCKED, READY_ORIGINALS, READY_PROOF, attest_audit, build_class, current_status
from papergrader.validator import FORBIDDEN_MODULES, check_no_grading_from_images, validate_inputs

REPO_ROOT = PLUGIN_ROOT.parent


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------
def test_the_demo_builds_two_classes_and_every_check_ran(built_demo):
    for class_id in (built_demo.class_a, built_demo.class_b):
        report = built_demo.reports[class_id]
        assert report["status"] == AWAITING_AUDIT, report["errors"]
        assert report["errors"] == []
        assert set(report["checks"].values()) == {"passed"}, report["checks"]
        assert report["synthetic_data"] is True


def test_the_demo_counts_each_scenario(built_demo):
    counts = built_demo.reports[built_demo.class_a]["counts"]
    assert counts == {"printable_pages": 7, "students": 7, "confirmed": 5, "pending": 2, "praise_awards": 2, "perfect_awards": 2}


def test_classes_stay_separate_and_numbering_restarts(built_demo):
    a = load_json(built_demo.job.page_map_path(built_demo.class_a))
    b = load_json(built_demo.job.page_map_path(built_demo.class_b))
    assert a["slots"][0]["student_order"] == 1 and b["slots"][0]["student_order"] == 1
    assert a["sources"][0]["file"] != b["sources"][0]["file"]
    assert built_demo.job.output_dir(built_demo.class_a) != built_demo.job.output_dir(built_demo.class_b)
    with pymupdf.open(built_demo.job.output_dir(built_demo.class_b) / "demo-class-b_student_score_roster.pdf") as doc:
        text = doc[0].get_text()
    assert "Fumi Test" in text and "Aiko Sample" not in text


def test_a_second_class_reuses_the_confirmed_test_without_new_references(built_demo):
    assert len(list((built_demo.job.root / "sources").glob("demo_key*"))) == 1
    grades_a = load_json(built_demo.job.grading_path(built_demo.class_a))
    grades_b = load_json(built_demo.job.grading_path(built_demo.class_b))
    assert grades_a["rubric_hash"] == grades_b["rubric_hash"]


def test_a_handwritten_number_counts_as_correct_only_because_a_judgment_says_so(tmp_path):
    """The case behind the earlier failure: a handwritten '3' that OCR read as blank.

    The scan is a pure image with no text layer. The grade comes from a supplied
    judgment, and it is applied without anything reading the digit.
    """
    student = demo.SyntheticStudent("Hand Written", "1", {"1.1": "3"}, {"1.1": ("correct", 10)})
    ctx = make_job(tmp_path, [student])
    source = ctx.job.source_path("demo_c1_students.pdf")
    with pymupdf.open(source) as doc:
        assert doc[0].get_text().strip() == "", "no text layer exists for anything to extract"
        assert doc[0].get_images(), "the scan is an image"
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != BLOCKED, report["errors"]
    plan = plans_of(ctx.job, ctx.class_id)[0]
    assert plan["marks"][0]["question_id"] == "1.1" and plan["marks"][0]["symbol"] == "correct"
    details = (ctx.job.output_dir(ctx.class_id) / "c1_answer_details.csv").read_text(encoding="utf-8-sig")
    assert "1.1,written,3,correct" in details


def test_the_build_never_rewrites_a_grade(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student, ninety_student(), pending_student()])
    before = sha256_file(ctx.job.grading_path(ctx.class_id))
    build_class(ctx.job, ctx.class_id)
    assert sha256_file(ctx.job.grading_path(ctx.class_id)) == before


def test_changing_a_judgment_changes_only_what_follows_from_it(tmp_path):
    """Regenerating after a teacher correction: new score, new award, everything consistent."""
    student = pending_student()
    ctx = make_job(tmp_path, [student])
    build_class(ctx.job, ctx.class_id)
    assert plans_of(ctx.job, ctx.class_id)[0]["score"] is None

    def resolve(data):
        answer = next(a for a in data["students"][0]["answers"] if a["question_id"] == "1.3")
        answer.update(
            observed_kind="written", observed_answer="8", decision="incorrect", awarded_points=0, teacher_statement="That is an 8, so it's wrong.",
            verification={"status": "visually_verified", "method": "teacher_override", "image_ref": "slot-0001"},
            confidence={"alignment": "high", "reading": "high", "interpretation": "high"},
        )

    edit_json(ctx.job.grading_path(ctx.class_id), resolve)
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != BLOCKED, report["errors"]
    plan = plans_of(ctx.job, ctx.class_id)[0]
    assert plan["score"]["text"] == "90" and plan["stamp"]["kind"] == "praise"


def test_a_declared_total_must_match_the_arithmetic(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"][0].update(declared_total=95))
    assert "score_arithmetic_mismatch" in error_codes(build_class(ctx.job, ctx.class_id))


def test_a_pending_student_cannot_declare_a_total(tmp_path):
    ctx = make_job(tmp_path, [pending_student()])
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"][0].update(declared_total=90))
    assert "pending_has_total" in error_codes(build_class(ctx.job, ctx.class_id))


def test_a_missing_question_blocks_rather_than_counting_as_zero(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"][0]["answers"].pop())
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] == BLOCKED and "judgment_missing" in error_codes(report)
    assert report["checks"]["scores_from_visual_judgments"] == "failed"
    assert report["outputs"] == {}, "no PDFs from an incomplete record"


def test_a_student_with_no_grading_record_blocks_the_build(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student, ninety_student()])
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"].pop())
    assert "student_grading_missing" in error_codes(build_class(ctx.job, ctx.class_id))


def test_checks_that_never_ran_say_so_rather_than_claiming_success(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    edit_json(ctx.job.test_path, lambda d: d["references"]["teacher_confirmation"].update(confirmed=False))
    report = build_class(ctx.job, ctx.class_id)
    assert report["checks"]["praise_stamps_present"] == "not_run"
    assert report["checks"]["page_count_matches_stack"] == "not_run"


def test_a_class_wide_blank_cluster_raises_a_warning_for_a_human(tmp_path):
    """The signature of the OCR failure: many blanks on an easy item."""
    students = [demo.SyntheticStudent(f"S {i}", str(i), {**demo._all_correct_written(), "1.5": str(i)}, demo._judged({"1.5": ("incorrect", 0)})) for i in range(1, 6)]
    ctx = make_job(tmp_path, students)

    def mark_blank(data):
        for student in data["students"]:
            answer = next(a for a in student["answers"] if a["question_id"] == "1.5")
            answer.update(observed_kind="blank", observed_answer="The box looks empty")

    edit_json(ctx.job.grading_path(ctx.class_id), mark_blank)
    bundle = validate_inputs(ctx.job, ctx.class_id)
    assert "class_wide_blank_cluster" in bundle.issues.codes() and bundle.issues.ok, "it asks for another look; it never changes a grade"


def test_the_same_answer_graded_two_ways_raises_a_warning(tmp_path):
    a = demo.SyntheticStudent("A", "1", {**demo._all_correct_written(), "1.1": "3"}, demo._judged())
    b = demo.SyntheticStudent("B", "2", {**demo._all_correct_written(), "1.1": "3"}, demo._judged({"1.1": ("incorrect", 0)}))
    ctx = make_job(tmp_path, [a, b])
    edit_json(ctx.job.page_map_path(ctx.class_id), lambda d: d.update(acknowledged_duplicates=[[1, 2]]))
    assert "inconsistent_decision" in validate_inputs(ctx.job, ctx.class_id).issues.codes()


# ---------------------------------------------------------------------------
# Rubric revisions
# ---------------------------------------------------------------------------
def test_a_rubric_change_blocks_until_affected_answers_are_regraded(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student, ninety_student()])
    edit_json(ctx.job.test_path, lambda d: d["questions"][0].update(accepted_answers=["3", "three"]))
    assert "rubric_changed_since_grading" in error_codes(build_class(ctx.job, ctx.class_id))
    assert ctx.job.rebase_grading(ctx.class_id) == ["1.1"]
    data = load_json(ctx.job.grading_path(ctx.class_id))
    for student in data["students"]:
        answers = {a["question_id"]: a for a in student["answers"]}
        assert answers["1.1"]["decision"] == "pending" and answers["1.1"]["awarded_points"] is None
        assert answers["1.2"]["decision"] == "correct", "unaffected answers keep their judgment"
    report = build_class(ctx.job, ctx.class_id)
    assert report["status"] != BLOCKED, report["errors"]
    assert report["counts"]["pending"] == 2


def test_moving_a_mark_is_not_a_rubric_change(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    edit_json(ctx.job.test_path, lambda d: d["questions"][0]["mark_anchor"].update(x_pct=35))
    assert "rubric_changed_since_grading" not in error_codes(build_class(ctx.job, ctx.class_id))


# ---------------------------------------------------------------------------
# The print status ladder
# ---------------------------------------------------------------------------
def test_status_climbs_one_earned_step_at_a_time(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    assert build_class(ctx.job, ctx.class_id)["status"] == AWAITING_AUDIT
    assert current_status(ctx.job, ctx.class_id)["status"] == AWAITING_AUDIT
    report = attest_audit(ctx.job, ctx.class_id, [1], "Viewed the overlay and preview for slot 1.")
    assert report["status"] == READY_PROOF and "PHOTOCOPIES" in report["status_meaning"]
    assert report["physical_calibration_verified"] is False
    printer_config.confirm_calibration(ctx.job.profile_path, "My photocopy test lined up.")
    assert current_status(ctx.job, ctx.class_id)["status"] == READY_ORIGINALS


def test_an_audit_must_cover_every_decorated_page(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [ninety_student(), perfect_student])
    build_class(ctx.job, ctx.class_id)
    with pytest.raises(PaperGraderError, match="Not yet covered"):
        attest_audit(ctx.job, ctx.class_id, [1], "Only looked at one.")
    assert current_status(ctx.job, ctx.class_id)["status"] == AWAITING_AUDIT


def test_a_blocked_build_cannot_be_audited(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    build_class(ctx.job, ctx.class_id, _skip_embroidery=True)
    with pytest.raises(PaperGraderError, match="blocked"):
        attest_audit(ctx.job, ctx.class_id, [1], "Looks fine.")


def test_editing_a_finished_pdf_revokes_its_status(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    build_class(ctx.job, ctx.class_id)
    attest_audit(ctx.job, ctx.class_id, [1], "Viewed.")
    path = ctx.job.output_dir(ctx.class_id) / "c1_corrections_NORMAL_ORDER.pdf"
    path.write_bytes(path.read_bytes() + b"\n%edited")
    status = current_status(ctx.job, ctx.class_id)
    assert status["status"] == BLOCKED and "changed" in status["status_meaning"]


def test_changing_grades_after_the_build_revokes_its_status(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    build_class(ctx.job, ctx.class_id)
    attest_audit(ctx.job, ctx.class_id, [1], "Viewed.")
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"][0].update(notes="changed"))
    assert current_status(ctx.job, ctx.class_id)["status"] == BLOCKED


def test_a_rebuild_removes_stale_print_ready_files(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    build_class(ctx.job, ctx.class_id)
    final = ctx.job.output_dir(ctx.class_id) / "c1_corrections_NORMAL_ORDER.pdf"
    assert final.exists()
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["students"][0]["answers"].pop())
    assert build_class(ctx.job, ctx.class_id)["status"] == BLOCKED
    assert not final.exists(), "the old file must not survive to be printed by mistake"


def test_output_clearing_refuses_a_folder_it_did_not_create(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    folder = ctx.job.output_dir(ctx.class_id)
    folder.mkdir(parents=True)
    (folder / "teacher_notes.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(PaperGraderError, match="won't be deleted"):
        build_class(ctx.job, ctx.class_id)
    assert (folder / "teacher_notes.txt").exists()


# ---------------------------------------------------------------------------
# Vision preflight
# ---------------------------------------------------------------------------
def test_visual_grades_are_refused_until_the_session_proves_it_can_see(tmp_path, perfect_student):
    ctx = make_job(tmp_path, [perfect_student])
    edit_json(ctx.job.grading_path(ctx.class_id), lambda d: d["grader"].update(type="chatgpt_visual", name="ChatGPT"))
    assert "vision_preflight_missing" in error_codes(build_class(ctx.job, ctx.class_id))
    vision_check.issue_challenge(ctx.job.vision_path, ctx.job.root / "v.png", code="4821")
    assert vision_check.answer_challenge(ctx.job.vision_path, "1111") is False
    assert "vision_preflight_missing" in error_codes(build_class(ctx.job, ctx.class_id))
    assert vision_check.answer_challenge(ctx.job.vision_path, "4821") is True
    assert "vision_preflight_missing" not in error_codes(build_class(ctx.job, ctx.class_id))


def test_the_vision_challenge_has_no_readable_answer_on_disk(tmp_path):
    state, image = tmp_path / "state.json", tmp_path / "c.png"
    vision_check.issue_challenge(state, image, code="7395")
    assert "7395" not in state.read_text(encoding="utf-8") and image.is_file()
    doc = pymupdf.open(image)
    assert doc[0].get_text().strip() == "", "the number is pixels, not text"


def test_vision_attempts_run_out(tmp_path):
    state, image = tmp_path / "state.json", tmp_path / "c.png"
    vision_check.issue_challenge(state, image, code="1000")
    for _ in range(3):
        assert vision_check.answer_challenge(state, "0") is False
    with pytest.raises(PaperGraderError, match="Out of attempts"):
        vision_check.answer_challenge(state, "1000")


# ---------------------------------------------------------------------------
# Reusing a saved test
# ---------------------------------------------------------------------------
def test_a_saved_test_can_grade_a_class_in_a_new_job(tmp_path, perfect_student):
    ctx = make_job(tmp_path / "first", [perfect_student]) if (tmp_path / "first").mkdir() is None else None
    package = ctx.job.export_test(tmp_path / "saved_test.zip")
    second = Job.create(tmp_path / "second")
    test = second.import_test(package)
    assert test.rubric_hash() == Issues() and False if False else test.confirmed is True
    work = tmp_path / "w"
    work.mkdir()
    demo.setup_class(second, work, "next", "Next", [ninety_student()], load_json(second.test_path))
    report = build_class(second, "next")
    assert report["status"] != BLOCKED, report["errors"]


def test_a_tampered_saved_test_is_refused(tmp_path, perfect_student):
    (tmp_path / "first").mkdir()
    ctx = make_job(tmp_path / "first", [perfect_student])
    package = ctx.job.export_test(tmp_path / "saved.zip")
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(tampered, "w") as out:
        for item in source.namelist():
            data = source.read(item)
            out.writestr(item, data + b"%x" if item.endswith("demo_key.pdf") else data)
    second = Job.create(tmp_path / "second")
    with pytest.raises(PaperGraderError, match="doesn't match"):
        second.import_test(tampered)


def test_a_package_with_a_path_traversal_entry_is_refused(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as out:
        out.writestr("test.json", "{}")
        out.writestr("../../evil.py", "x")
    job = Job.create(tmp_path / "job")
    with pytest.raises(PaperGraderError, match="Unexpected file"):
        job.import_test(bad)


# ---------------------------------------------------------------------------
# Guards: no OCR, no network, no student data in the repo
# ---------------------------------------------------------------------------
def test_the_package_imports_no_ocr_vision_or_network_libraries():
    issues = Issues()
    check_no_grading_from_images(issues)
    assert issues.ok, issues.to_json()
    for source in (PLUGIN_ROOT / "papergrader").glob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert not {a.name.split(".")[0] for a in node.names} & FORBIDDEN_MODULES, source.name
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN_MODULES, source.name


def test_the_import_guard_itself_catches_a_violation(tmp_path, monkeypatch):
    """A guard that can't fail proves nothing, so show it failing."""
    bad_pkg = tmp_path / "pkg"
    bad_pkg.mkdir()
    (bad_pkg / "sneaky.py").write_text("import pytesseract\n", encoding="utf-8")
    (bad_pkg / "validator.py").write_text("", encoding="utf-8")
    import papergrader.validator as v

    monkeypatch.setattr(v, "__file__", str(bad_pkg / "validator.py"))
    issues = Issues()
    v.check_no_grading_from_images(issues)
    assert "forbidden_import" in issues.codes()


def test_grading_records_never_touch_an_image_library():
    tree = ast.parse((PLUGIN_ROOT / "papergrader" / "grading_models.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    assert not names & {"pymupdf", "fitz", "PIL"}


def _tracked_files() -> list[str]:
    try:
        output = subprocess.run(["git", "ls-files", "--others", "--cached", "--exclude-standard", "papergrader-plugin"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    return output.splitlines()


def test_no_private_job_data_can_be_committed():
    """The repository is public. Only named synthetic demo output may hold PDFs or grades."""
    allowed_prefix = "papergrader-plugin/examples/demo_output/"
    for name in _tracked_files():
        if name.startswith(allowed_prefix):
            continue
        assert not name.endswith((".pdf", ".xlsx", ".csv", ".zip")), f"{name} could hold student data"
        assert Path(name).name not in {"grading.json", "page_map.json"}, name


def test_the_committed_examples_are_labelled_synthetic():
    folder = PLUGIN_ROOT / "examples" / "demo_output"
    if not folder.exists():
        pytest.skip("no committed examples")
    for report in folder.rglob("*_validation_report.json"):
        assert load_json(report)["synthetic_data"] is True, report


# ---------------------------------------------------------------------------
# The plugin package
# ---------------------------------------------------------------------------
def test_the_plugin_manifest_is_valid_and_private():
    manifest = load_json(PLUGIN_ROOT / "plugin.json")
    assert manifest["name"] == "papergrader" and manifest["version"]
    assert manifest["extensions"]["com.openai"]["interface"]["displayName"] == "PaperGrader"
    overlay = load_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    assert overlay["name"] == manifest["name"] and overlay["version"] == manifest["version"] and overlay["skills"] == "./skills/"
    text = (PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8")
    assert "mcpServers" not in text and "hooks" not in text and not (PLUGIN_ROOT / "mcp.json").exists(), "no servers or hooks in version 1"


def test_the_marketplace_entry_points_at_the_plugin():
    marketplace = load_json(REPO_ROOT / ".agents" / "plugins" / "marketplace.json")
    entry = marketplace["plugins"][0]
    assert entry["name"] == "papergrader" and (REPO_ROOT / entry["source"]["path"] / "plugin.json").is_file()
    assert entry["policy"]["installation"] == "AVAILABLE"


def test_the_skill_has_required_frontmatter_and_mandatory_rules():
    text = (PLUGIN_ROOT / "skills" / "grade-paper-tests" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: grade-paper-tests\ndescription: ")
    for phrase in ("doctor", "vision-check", "explicit", "pending", "attest-audit", "photocop"):
        assert phrase in text, phrase


def test_the_bundled_instructions_match_the_authoritative_file_exactly():
    root = REPO_ROOT / "CHATGPT_GRADING_INSTRUCTIONS.md"
    copy = PLUGIN_ROOT / "skills" / "grade-paper-tests" / "references" / "CHATGPT_GRADING_INSTRUCTIONS.md"
    assert root.read_bytes() == copy.read_bytes(), "run scripts/build_bundle.py to refresh the copy"


def test_every_cli_command_named_in_the_skill_exists():
    import re

    from papergrader.cli import build_parser

    parser = build_parser()
    commands = next(a.choices for a in parser._actions if hasattr(a, "choices") and a.choices)
    root = PLUGIN_ROOT / "skills" / "grade-paper-tests"
    for path in [root / "SKILL.md", root / "references" / "workflow.md"]:
        for name in re.findall(r"\bpg (?:\S+ )?([a-z]+(?:-[a-z]+)*)\b", path.read_text(encoding="utf-8")):
            if name in {"py", "json"}:
                continue
            assert name in commands, f"{path.name} mentions unknown command {name}"


def test_the_launcher_runs_from_any_working_directory(tmp_path):
    launcher = PLUGIN_ROOT / "skills" / "grade-paper-tests" / "scripts" / "pg.py"
    done = subprocess.run([sys.executable, str(launcher), "doctor"], cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["can_process_pdfs"] is True


def test_doctor_stops_cleanly_when_pdf_support_is_missing(tmp_path):
    """Simulate a runtime without PyMuPDF. It must say so, not crash or pretend."""
    code = (
        "import sys; sys.modules['pymupdf'] = None; "
        f"sys.path.insert(0, {str(PLUGIN_ROOT)!r}); "
        "from papergrader.cli import main; sys.exit(main(['doctor']))"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 2
    result = json.loads(done.stdout)
    assert result["can_process_pdfs"] is False and "Don't pretend" in result["verdict"]


def test_the_cli_reports_errors_as_json_without_a_traceback(tmp_path):
    done = subprocess.run([sys.executable, "-m", "papergrader", "status", "--job", str(tmp_path), "--class", "x"], cwd=PLUGIN_ROOT, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 1 and "Traceback" not in done.stderr
    assert "isn't a PaperGrader job" in json.loads(done.stdout)["error"]


def test_the_runtime_bundle_works_from_a_clean_folder(tmp_path):
    subprocess.run([sys.executable, str(PLUGIN_ROOT / "scripts" / "build_bundle.py"), "--out", str(tmp_path / "dist")], check=True, capture_output=True, text=True, encoding="utf-8")
    bundle = tmp_path / "dist" / "papergrader-runtime.zip"
    plugin_zip = tmp_path / "dist" / "papergrader-plugin.zip"
    assert bundle.is_file() and plugin_zip.is_file()
    with zipfile.ZipFile(plugin_zip) as archive:
        names = archive.namelist()
        assert "plugin.json" in names and "skills/grade-paper-tests/SKILL.md" in names
        assert not [n for n in names if ".venv" in n or "__pycache__" in n or n.startswith("tests/") or n.startswith("examples/")]
    unpack = tmp_path / "unpacked"
    with zipfile.ZipFile(bundle) as archive:
        archive.extractall(unpack)
    done = subprocess.run([sys.executable, "-m", "papergrader", "doctor"], cwd=unpack, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["checks"]["artwork"]["ok"] is True
