"""Command line for PaperGrader. Every command prints one JSON object.

    python -m papergrader doctor
    python -m papergrader --help

Exit codes: 0 success, 1 a problem to fix or a blocked build, 2 the runtime can't
work at all. The result on stdout is the only proof a command ran. Anyone relaying
this tool's work must quote it rather than assume an outcome.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

from . import __version__
from .common import ASSETS_DIR, PLUGIN_ROOT, PaperGraderError


def _emit(data: dict[str, Any]) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:  # consoles on older Windows code pages can't print Japanese
        print(json.dumps(data, ensure_ascii=True, indent=2))


def _doctor(_: argparse.Namespace) -> int:
    """Report what this runtime can really do, by doing it."""
    result: dict[str, Any] = {
        "command": "doctor",
        "papergrader_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "plugin_root": str(PLUGIN_ROOT),
        "checks": {},
    }
    checks = result["checks"]
    try:
        import pymupdf

        checks["pymupdf"] = {"ok": True, "version": pymupdf.__version__}
    except ImportError as exc:
        checks["pymupdf"] = {"ok": False, "error": str(exc), "fix": "pip install -r requirements.txt"}
        result["can_process_pdfs"] = False
        result["verdict"] = "This runtime can't process PDFs. Stop, and tell the teacher. Don't pretend the files were created."
        _emit(result)
        return 2
    try:
        import openpyxl

        checks["openpyxl"] = {"ok": True, "version": openpyxl.__version__}
    except ImportError:
        checks["openpyxl"] = {"ok": False, "note": "XLSX output unavailable; CSV still works."}

    from . import decorations

    missing = [str(p) for p in decorations.required_assets() if not p.is_file()]
    checks["artwork"] = {"ok": not missing, "assets_dir": str(ASSETS_DIR), "missing": missing}

    try:
        with tempfile.TemporaryDirectory() as temp:
            doc = pymupdf.open()
            page = doc.new_page(width=200, height=200)
            decorations.place_art(page, "stamps/perfect_cat.svg", (100, 100), 150, 115, 5)
            path = Path(temp) / "self_test.pdf"
            doc.save(path)
            doc.close()
            with pymupdf.open(path) as check:
                pix = check[0].get_pixmap(dpi=36, alpha=True)
                inked = any(bytes(pix.samples)[3::4])
            checks["render_self_test"] = {"ok": inked}
    except Exception as exc:  # any failure here means generated PDFs can't be trusted
        checks["render_self_test"] = {"ok": False, "error": str(exc)}

    from .common import Issues
    from .validator import check_no_grading_from_images

    guard = Issues()
    check_no_grading_from_images(guard)
    checks["no_ocr_or_network_imports"] = {"ok": guard.ok}
    essential = ("artwork", "render_self_test", "no_ocr_or_network_imports")
    good = all(checks[name]["ok"] for name in essential)
    result["can_process_pdfs"] = good
    result["verdict"] = (
        "PDF processing works here. Run vision-check next to find out whether this session can see images."
        if good else "An essential check failed. Stop and report it; generated files couldn't be trusted."
    )
    _emit(result)
    return 0 if good else 2


def _job(args: argparse.Namespace):
    from .job import Job

    return Job(Path(args.job))


def _parse_rect(text: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    if not text:
        return None
    try:
        x, y, w, h = (float(part) for part in text.split(","))
    except ValueError as exc:
        raise PaperGraderError("--rect must be four percentages: x,y,width,height") from exc
    return x, y, w, h


def _parse_int_list(text: Optional[str]) -> Optional[list[int]]:
    if text is None:
        return None
    values: list[int] = []
    try:
        for part in text.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                values.extend(range(int(start), int(end) + 1))
            elif part:
                values.append(int(part))
    except ValueError as exc:
        raise PaperGraderError(f"Couldn't read the number list {text!r}. Use a form like 1,2,5-9.") from exc
    return values


def _init_job(args: argparse.Namespace) -> int:
    from .job import Job

    job = Job.create(Path(args.job), allow_inside_git=args.allow_inside_git)
    _emit({"command": "init-job", "job": str(job.root), "printer_profile": str(job.profile_path)})
    return 0


def _add_source(args: argparse.Namespace) -> int:
    job = _job(args)
    from .pdf_processor import inventory_pdf

    added = []
    for name in args.files:
        info = job.add_source(Path(name))
        added.append({**info, "inventory": inventory_pdf(job.source_path(info["file"]))})
    _emit({"command": "add-source", "added": added})
    return 0


def _inspect(args: argparse.Namespace) -> int:
    from .pdf_processor import inventory_pdf

    _emit({"command": "inspect", "inventory": inventory_pdf(Path(args.pdf))})
    return 0


def _view_source(args: argparse.Namespace) -> int:
    job = _job(args)
    entries = [
        job.render_source_page(args.source, page, args.rotation, args.dpi, _parse_rect(args.rect), args.zoom, args.grid)
        for page in (_parse_int_list(args.pages) or [])
    ]
    _emit({"command": "view-source", "views": entries, "reminder": "Open and look at each image. A file path isn't an observation."})
    return 0


def _set_test(args: argparse.Namespace) -> int:
    from .common import Issues, load_json, save_json
    from .grading_models import format_points, parse_test

    job = _job(args)
    data = load_json(Path(args.file))
    issues = Issues()
    test = parse_test(data, issues)
    if not test or not issues.ok:
        _emit({"command": "set-test", "saved": False, **issues.to_json()})
        return 1
    if job.test_path.exists() and not args.replace:
        raise PaperGraderError("This job already has a test. Pass --replace for a rubric revision, then run rebase-grading for each class.")
    save_json(job.test_path, data)
    _emit({"command": "set-test", "saved": True, "rubric_hash": test.rubric_hash(), "questions": len(test.questions), "max_points": format_points(test.max_points), "rubric_status": test.rubric_status, "teacher_confirmed": test.confirmed, **issues.to_json()})
    return 0


def _propose_map(args: argparse.Namespace) -> int:
    job = _job(args)
    excluded: dict[str, dict[int, str]] = {}
    for spec in args.exclude or []:
        try:
            file_name, role, pages = spec.split(":", 2)
        except ValueError as exc:
            raise PaperGraderError("--exclude takes FILE:ROLE:PAGES, for example combined.pdf:blank:1") from exc
        for page in _parse_int_list(pages) or []:
            excluded.setdefault(file_name, {})[page] = role
    data = job.propose_map(args.class_id, args.label or args.class_id, args.sources, excluded, args.paper_mode, args.replace)
    students = data["slots"][-1]["student_order"] if data["slots"] else 0
    _emit({
        "command": "propose-map", "slots": len(data["slots"]), "students_if_packets_are_complete": students, "page_map": str(job.page_map_path(args.class_id)),
        "reminder": "This is only a proposal, assuming every packet is complete. Look at the pages, correct the map if needed, and confirm rotation with set-rotation.",
    })
    return 0


def _set_rotation(args: argparse.Namespace) -> int:
    job = _job(args)
    slots = None if args.rest else _parse_int_list(args.slots)
    if slots is None and not args.rest:
        raise PaperGraderError("Name the pages you looked at with --slots, or use --rest for every page still unconfirmed.")
    _emit({"command": "set-rotation", "updated": job.set_rotation(args.class_id, args.rotation, slots)})
    return 0


def _render(args: argparse.Namespace) -> int:
    job = _job(args)
    from .common import load_json

    if args.slots:
        slots = _parse_int_list(args.slots) or []
    else:
        slots = [s["slot"] for s in load_json(job.page_map_path(args.class_id))["slots"] if s["kind"] == "scan"]
    entries = [job.render_slot(args.class_id, slot, args.dpi, _parse_rect(args.rect), args.zoom, args.grid) for slot in slots]
    _emit({
        "command": "render", "views": [{"ref": e["ref"], "path": e["path"], "slot": e["slot"], "student_order": e["student_order"]} for e in entries],
        "reminder": "Open and look at each image. Cite the ref in verification.image_ref only for an image that was actually viewed.",
    })
    return 0


def _scaffold(args: argparse.Namespace) -> int:
    job = _job(args)
    data = job.scaffold_grading(args.class_id, args.grader_type, args.grader_name)
    _emit({"command": "scaffold-grading", "students": len(data["students"]), "grading": str(job.grading_path(args.class_id)), "note": "Every answer starts as pending. Nothing counts until it is looked at and recorded."})
    return 0


def _rebase(args: argparse.Namespace) -> int:
    _emit({"command": "rebase-grading", "questions_reset_to_pending": _job(args).rebase_grading(args.class_id)})
    return 0


def _check(args: argparse.Namespace) -> int:
    from .grading_models import format_points
    from .validator import validate_inputs

    bundle = validate_inputs(_job(args), args.class_id)
    students = [
        {"student_order": o.student_order, "confirmed_total": format_points(o.total) if o.resolved else None, "award": o.award, "unresolved": list(o.unresolved)}
        for o in sorted(bundle.outcomes.values(), key=lambda o: o.student_order)
    ]
    _emit({"command": "check", "ok": bundle.issues.ok, "students": students, **bundle.issues.to_json()})
    return 0 if bundle.issues.ok else 1


def _build(args: argparse.Namespace) -> int:
    from .pipeline import build_class

    job = _job(args)
    report = build_class(job, args.class_id)
    _emit({
        "command": "build", "status": report["status"], "status_meaning": report["status_meaning"], "output_dir": str(job.output_dir(args.class_id)),
        "checks": report["checks"], "counts": report["counts"], "outputs": sorted(report["outputs"]), "visual_audit_required_slots": report["visual_audit"]["required_slots"],
        "errors": report["errors"], "warnings": report["warnings"],
    })
    return 0 if report["status"] != "BLOCKED" else 1


def _status(args: argparse.Namespace) -> int:
    from .pipeline import current_status

    report = current_status(_job(args), args.class_id)
    _emit({"command": "status", "status": report["status"], "status_meaning": report["status_meaning"], "physical_calibration_verified": report["physical_calibration_verified"], "visual_audit": report["visual_audit"], "errors": report["errors"], "warnings": report["warnings"]})
    return 0 if report["status"] != "BLOCKED" else 1


def _attest(args: argparse.Namespace) -> int:
    from .pipeline import attest_audit

    report = attest_audit(_job(args), args.class_id, _parse_int_list(args.slots) or [], args.statement)
    _emit({"command": "attest-audit", "status": report["status"], "status_meaning": report["status_meaning"], "visual_audit": report["visual_audit"]})
    return 0


def _vision_issue(args: argparse.Namespace) -> int:
    from .vision_check import issue_challenge

    job = _job(args)
    image = issue_challenge(job.vision_path, job.root / "vision_check.png")
    _emit({"command": "vision-check", "image": str(image), "instruction": "View this image with your image viewing tool, then run vision-answer with the number it shows. If you can't view images, stop and tell the teacher: visual grading isn't possible in this session."})
    return 0


def _vision_answer(args: argparse.Namespace) -> int:
    from .vision_check import answer_challenge

    passed = answer_challenge(_job(args).vision_path, args.answer)
    _emit({"command": "vision-answer", "passed": passed})
    return 0 if passed else 1


def _calibration(args: argparse.Namespace) -> int:
    from .common import Issues
    from .printer_config import build_calibration_pdf, bundled_profile

    profile = bundled_profile()
    targets = None
    template_pages = 1
    if args.job:
        job = _job(args)
        profile = job.load_profile()
        issues = Issues()
        test = job.load_test(issues)
        if test:
            template_pages = test.template_pages
            targets = {}
            box = test.score_box
            targets.setdefault(box.template_page, []).append(("score", box.rect.x + box.rect.w / 2, box.rect.y + box.rect.h / 2))
            for question in test.questions:
                targets.setdefault(question.template_page, []).append((question.id, question.mark_anchor[0], question.mark_anchor[1]))
    path = build_calibration_pdf(Path(args.out), args.paper, args.pages, profile, targets=targets, template_pages=template_pages)
    _emit({"command": "calibration-pdf", "file": str(path), "offset_mm": profile["offset_mm"], "physically_verified": profile["calibration"]["physically_verified"], "reminder": "Print on photocopies only. This file proves nothing until the teacher has measured a real print."})
    return 0


def _set_offsets(args: argparse.Namespace) -> int:
    from .printer_config import set_offsets

    profile = set_offsets(_job(args).profile_path, args.x, args.y)
    _emit({"command": "set-offsets", "offset_mm": profile["offset_mm"], "physically_verified": False, "next": "Rebuild each class, then repeat the photocopy test."})
    return 0


def _confirm_calibration(args: argparse.Namespace) -> int:
    from .printer_config import confirm_calibration

    profile = confirm_calibration(_job(args).profile_path, args.teacher_statement)
    _emit({"command": "confirm-calibration", "calibration": profile["calibration"]})
    return 0


def _export_test(args: argparse.Namespace) -> int:
    path = _job(args).export_test(Path(args.out))
    _emit({"command": "export-test", "file": str(path), "privacy": "This holds the test and its answer key. Keep it private."})
    return 0


def _import_test(args: argparse.Namespace) -> int:
    test = _job(args).import_test(Path(args.package))
    _emit({"command": "import-test", "test_id": test.test_id, "test_version": test.test_version, "rubric_hash": test.rubric_hash(), "teacher_confirmed": test.confirmed})
    return 0


def _demo(args: argparse.Namespace) -> int:
    from .demo import run_demo

    reports = run_demo(Path(args.out))
    _emit({
        "command": "demo", "job": str(Path(args.out).resolve()), "warning": "Synthetic data with typed-in grades. This shows the PDF pipeline, not grading accuracy.",
        "classes": {cid: {"status": r["status"], "counts": r["counts"], "checks": r["checks"], "errors": r["errors"]} for cid, r in reports.items()},
    })
    return 0 if all(r["status"] != "BLOCKED" for r in reports.values()) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="papergrader", description="PDF mechanics for visually graded paper tests. It never decides whether an answer is right.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    def command(name: str, handler, help_text: str, job: bool = True, class_id: bool = False) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.set_defaults(handler=handler)
        if job:
            p.add_argument("--job", required=True, help="the job folder")
        if class_id:
            p.add_argument("--class", dest="class_id", required=True, help="class id: letters, digits, '.', '_' and '-' only")
        return p

    command("doctor", _doctor, "Report what this runtime can really do.", job=False)
    p = command("init-job", _init_job, "Create a private job folder. Refuses a folder inside a git checkout.")
    p.add_argument("--allow-inside-git", action="store_true", help=argparse.SUPPRESS)
    p = command("add-source", _add_source, "Copy PDFs into the job and list their pages.")
    p.add_argument("files", nargs="+")
    p = command("inspect", _inspect, "List a PDF's pages without changing anything.", job=False)
    p.add_argument("pdf")
    p = command("view-source", _view_source, "Render source pages, to identify the blank and key or read the rubric.")
    p.add_argument("source")
    p.add_argument("--pages", required=True, help="for example 1,2,5-9")
    p.add_argument("--rotation", type=int, default=0, choices=(0, 90, 180, 270))
    p.add_argument("--dpi", type=int, default=200)
    p.add_argument("--rect", help="crop as x,y,w,h percentages")
    p.add_argument("--zoom", type=float, default=1.0)
    p.add_argument("--grid", action="store_true", help="overlay a percent grid for reading coordinates")
    p = command("set-test", _set_test, "Validate and save the interpreted answer key and rubric.")
    p.add_argument("file")
    p.add_argument("--replace", action="store_true", help="revise an existing test; run rebase-grading afterwards")
    p = command("propose-map", _propose_map, "Propose packets from student scans, in scan order.", class_id=True)
    p.add_argument("sources", nargs="+", help="file names already added with add-source, in scan order")
    p.add_argument("--label", help="the class name for reports; any characters")
    p.add_argument("--exclude", action="append", metavar="FILE:ROLE:PAGES", help="reference pages inside a student PDF, e.g. combined.pdf:blank:1")
    p.add_argument("--paper-mode", choices=("simplex", "duplex"), default="simplex")
    p.add_argument("--replace", action="store_true")
    p = command("set-rotation", _set_rotation, "Record the orientation seen on pages: clockwise degrees needed to make them upright.", class_id=True)
    p.add_argument("--rotation", type=int, required=True, choices=(0, 90, 180, 270))
    p.add_argument("--slots", help="for example 3,7-9")
    p.add_argument("--rest", action="store_true", help="every page still unconfirmed")
    p = command("render", _render, "Render student pages or crops for looking at. Each gets a citable ref.", class_id=True)
    p.add_argument("--slots", help="default: all pages")
    p.add_argument("--dpi", type=int, default=200)
    p.add_argument("--rect", help="crop as x,y,w,h percentages")
    p.add_argument("--zoom", type=float, default=1.0)
    p.add_argument("--grid", action="store_true")
    p = command("scaffold-grading", _scaffold, "Create the grading record, with every answer pending.", class_id=True)
    p.add_argument("--grader-type", choices=("chatgpt_visual", "teacher_manual"), default="chatgpt_visual")
    p.add_argument("--grader-name", default="ChatGPT")
    command("rebase-grading", _rebase, "After a rubric change, reset only the affected answers to pending.", class_id=True)
    command("check", _check, "Validate records without building anything.", class_id=True)
    command("build", _build, "Generate and validate every output for a class.", class_id=True)
    command("status", _status, "Re-check finished files and report whether they may be printed.", class_id=True)
    p = command("attest-audit", _attest, "Record which finished pages were looked at, and what was seen.", class_id=True)
    p.add_argument("--slots", required=True)
    p.add_argument("--statement", required=True)
    command("vision-check", _vision_issue, "Create an image that can only be answered by seeing it.")
    p = command("vision-answer", _vision_answer, "Answer the vision check.")
    p.add_argument("answer")
    p = command("calibration-pdf", _calibration, "Generate the photocopy calibration test.", job=False)
    p.add_argument("--job", help="optional: add this test's score box and mark positions")
    p.add_argument("--out", required=True)
    p.add_argument("--paper", default="A4")
    p.add_argument("--pages", type=int, default=5)
    p = command("set-offsets", _set_offsets, "Set printer offsets in mm. This clears any physical confirmation.")
    p.add_argument("--x", type=float, required=True)
    p.add_argument("--y", type=float, required=True)
    p = command("confirm-calibration", _confirm_calibration, "Record the teacher's report of a successful physical test.")
    p.add_argument("--teacher-statement", required=True)
    p = command("export-test", _export_test, "Save the confirmed test and references to one private file for later sessions.")
    p.add_argument("--out", required=True)
    p = command("import-test", _import_test, "Load a saved test into a new job, verifying its hashes.")
    p.add_argument("package")
    p = command("demo", _demo, "Build two synthetic classes end to end.", job=False)
    p.add_argument("--out", required=True, help="a new folder outside any git checkout")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except PaperGraderError as exc:
        _emit({"command": args.command, "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
