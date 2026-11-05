"""A grading job's private working folder and its record files.

Layout (never inside a git checkout, so student data can't be committed):

    job/
      job.json  test.json  printer_profile.json  vision_preflight.json
      sources/                    uploaded PDFs, unchanged
      reference_renders/          views of blank and key pages
      classes/<class_id>/
        page_map.json  grading.json  renders.json
        renders/                  page images and crops that were looked at
        output/                   generated files, safe to delete and rebuild
"""
from __future__ import annotations

import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import SCHEMA_VERSION, __version__
from .common import SAFE_ID, Issues, PaperGraderError, inside_git_worktree, load_json, save_json, sha256_file
from .grading_models import Grading, PageMap, TestDefinition, parse_grading, parse_page_map, parse_test
from .pdf_processor import propose_page_map, render_view
from .printer_config import DEFAULT_PROFILE, bundled_profile, validate_profile


class Job:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        if not (self.root / "job.json").is_file():
            raise PaperGraderError(f"{self.root} isn't a PaperGrader job. Run init-job first.")

    @classmethod
    def create(cls, root: Path, allow_inside_git: bool = False, profile_id: str = DEFAULT_PROFILE) -> "Job":
        root = Path(root).resolve()
        if inside_git_worktree(root) and not allow_inside_git:
            raise PaperGraderError(
                f"{root} is inside a git checkout. Student scans and grades must stay out of repositories, so choose a folder elsewhere."
            )
        root.mkdir(parents=True, exist_ok=True)
        if (root / "job.json").exists():
            raise PaperGraderError(f"{root} is already a job. Use it as it is, or choose a new folder.")
        (root / "sources").mkdir(exist_ok=True)
        (root / "classes").mkdir(exist_ok=True)
        save_json(root / "job.json", {"schema_version": SCHEMA_VERSION, "papergrader_version": __version__, "created_at": _now()})
        save_json(root / "printer_profile.json", bundled_profile(profile_id))
        return cls(root)

    # -- paths ---------------------------------------------------------------
    @property
    def test_path(self) -> Path:
        return self.root / "test.json"

    @property
    def profile_path(self) -> Path:
        return self.root / "printer_profile.json"

    @property
    def vision_path(self) -> Path:
        return self.root / "vision_preflight.json"

    def source_path(self, name: str) -> Path:
        if not name or Path(name).name != name:
            raise PaperGraderError(f"Source name {name!r} must be a plain file name.")
        return self.root / "sources" / name

    def class_dir(self, class_id: str) -> Path:
        if not SAFE_ID.match(class_id or ""):
            raise PaperGraderError(f"Class id {class_id!r} may contain only letters, digits, '.', '_' and '-'. Put other characters in the class label.")
        return self.root / "classes" / class_id

    def page_map_path(self, class_id: str) -> Path:
        return self.class_dir(class_id) / "page_map.json"

    def grading_path(self, class_id: str) -> Path:
        return self.class_dir(class_id) / "grading.json"

    def renders_path(self, class_id: str) -> Path:
        return self.class_dir(class_id) / "renders.json"

    def output_dir(self, class_id: str) -> Path:
        return self.class_dir(class_id) / "output"

    # -- sources -------------------------------------------------------------
    def add_source(self, path: Path) -> dict[str, str]:
        path = Path(path)
        if not path.is_file():
            raise PaperGraderError(f"File not found: {path}")
        target = self.source_path(path.name)
        if target.exists() and sha256_file(target) != sha256_file(path):
            raise PaperGraderError(f"sources/ already has a different file named {path.name}. Rename the new one.")
        if not target.exists():
            shutil.copy2(path, target)
        return {"file": path.name, "sha256": sha256_file(target)}

    # -- loading -------------------------------------------------------------
    def load_test(self, issues: Issues) -> Optional[TestDefinition]:
        if not self.test_path.is_file():
            issues.error("test_missing", "No test.json. Build the interpreted answer key before grading.", "test")
            return None
        return parse_test(load_json(self.test_path), issues)

    def load_page_map(self, class_id: str, issues: Issues) -> Optional[PageMap]:
        path = self.page_map_path(class_id)
        if not path.is_file():
            issues.error("page_map_missing", f"No page map for class {class_id}. Run propose-map.", "page_map")
            return None
        return parse_page_map(load_json(path), issues)

    def load_grading(self, class_id: str, issues: Issues) -> Optional[Grading]:
        path = self.grading_path(class_id)
        if not path.is_file():
            issues.error("grading_missing", f"No grading record for class {class_id}. Run scaffold-grading.", "grading")
            return None
        return parse_grading(load_json(path), issues)

    def load_renders(self, class_id: str) -> dict[str, dict[str, Any]]:
        path = self.renders_path(class_id)
        return load_json(path)["refs"] if path.is_file() else {}

    def load_profile(self) -> dict[str, Any]:
        return load_json(self.profile_path)

    # -- class setup -----------------------------------------------------------
    def propose_map(
        self, class_id: str, class_label: str, source_names: list[str], excluded: Optional[dict[str, dict[int, str]]] = None,
        paper_mode: str = "simplex", replace: bool = False,
    ) -> dict:
        issues = Issues()
        test = self.load_test(issues)
        if test is None:
            raise PaperGraderError("test.json must exist and parse before mapping pages: " + "; ".join(i.message for i in issues.errors))
        target = self.page_map_path(class_id)
        if target.exists() and not replace:
            raise PaperGraderError(f"{target} already exists and may hold confirmed rotations. Pass --replace to discard it.")
        paths = [self.source_path(name) for name in source_names]
        for path in paths:
            if not path.is_file():
                raise PaperGraderError(f"{path.name} isn't in sources/. Run add-source first.")
        data = propose_page_map(paths, class_id, class_label, test.test_id, test.test_version, test.template_pages, excluded, paper_mode)
        save_json(target, data)
        return data

    def set_rotation(self, class_id: str, rotation: int, slots: Optional[list[int]]) -> int:
        """Record a rotation someone saw. ``slots=None`` means every still-unconfirmed page."""
        if rotation not in (0, 90, 180, 270):
            raise PaperGraderError("Rotation must be 0, 90, 180 or 270.")
        path = self.page_map_path(class_id)
        data = load_json(path)
        changed = 0
        for slot in data["slots"]:
            selected = slot["slot"] in slots if slots is not None else slot["rotation_status"] == "unconfirmed"
            if selected and slot["kind"] == "scan":
                slot["scan_rotation"] = rotation
                slot["rotation_status"] = "visually_confirmed"
                changed += 1
        if slots is not None and changed != len(set(slots)):
            raise PaperGraderError(f"Some of the slots {slots} don't exist or aren't scanned pages; nothing was saved.")
        save_json(path, data)
        return changed

    # -- rendering, with a log of what was looked at ---------------------------
    def render_slot(
        self, class_id: str, slot_number: int, dpi: int = 200, rect_pct: Optional[tuple[float, float, float, float]] = None,
        zoom: float = 1.0, grid: bool = False,
    ) -> dict[str, Any]:
        data = load_json(self.page_map_path(class_id))
        slot = next((s for s in data["slots"] if s["slot"] == slot_number), None)
        if slot is None:
            raise PaperGraderError(f"Class {class_id} has no slot {slot_number}.")
        if slot["kind"] != "scan":
            raise PaperGraderError(f"Slot {slot_number} is a blank filler with no scan.")
        log = self.load_renders(class_id)
        base = f"slot-{slot_number:04d}"
        if rect_pct is None and not grid and zoom == 1.0:
            ref = base
        else:
            count = sum(1 for key in log if key.startswith(base + "-view-")) + 1
            ref = f"{base}-view-{count:03d}"
        out = self.class_dir(class_id) / "renders" / f"{ref}.png"
        info = render_view(self.source_path(slot["source_pdf"]), slot["source_page"], slot["scan_rotation"], out, dpi, rect_pct, zoom, grid)
        entry = {
            **info, "ref": ref, "path": str(out), "sha256": sha256_file(out), "slot": slot_number, "student_order": slot["student_order"],
            "source_pdf": slot["source_pdf"], "source_page": slot["source_page"], "scan_rotation": slot["scan_rotation"], "rendered_at": _now(),
        }
        log[ref] = entry
        save_json(self.renders_path(class_id), {"schema_version": SCHEMA_VERSION, "refs": log})
        return entry

    def render_source_page(self, name: str, page: int, rotation: int = 0, dpi: int = 200, rect_pct=None, zoom: float = 1.0, grid: bool = False) -> dict[str, Any]:
        """A view of any source page: for classifying blank and key pages, or reading the rubric."""
        path = self.source_path(name)
        suffix = "-grid" if grid else ""
        crop = "-crop" if rect_pct else ""
        out = self.root / "reference_renders" / f"{path.stem}-p{page:03d}-r{rotation}{crop}{suffix}.png"
        return {**render_view(path, page, rotation, out, dpi, rect_pct, zoom, grid), "path": str(out)}

    # -- grading records -------------------------------------------------------
    def scaffold_grading(self, class_id: str, grader_type: str = "chatgpt_visual", grader_name: str = "ChatGPT") -> dict:
        """Start every answer as explicitly pending. The safe state exists before any looking does."""
        issues = Issues()
        test = self.load_test(issues)
        page_map = self.load_page_map(class_id, issues)
        if test is None or page_map is None:
            raise PaperGraderError("; ".join(i.message for i in issues.errors))
        target = self.grading_path(class_id)
        if target.exists():
            raise PaperGraderError(f"{target} already exists. Refusing to overwrite recorded grades.")
        students = []
        for order in page_map.student_orders():
            students.append({
                "student_order": order,
                "name": {"status": "unreadable"},
                "number": {"status": "unreadable"},
                "source_pages": source_pages_for(page_map, order),
                "answers": [_pending_answer(q.id, q.points) for q in test.questions],
            })
        data = {
            "schema_version": SCHEMA_VERSION, "class_id": class_id, "test_id": test.test_id, "test_version": test.test_version,
            "rubric_hash": test.rubric_hash(), "question_hashes": {q.id: q.rubric_hash() for q in test.questions},
            "grader": {"type": grader_type, "name": grader_name}, "students": students,
        }
        save_json(target, data)
        return data

    def rebase_grading(self, class_id: str) -> list[str]:
        """After a rubric change: reset only affected answers to pending, so they get regraded."""
        issues = Issues()
        test = self.load_test(issues)
        if test is None:
            raise PaperGraderError("; ".join(i.message for i in issues.errors))
        path = self.grading_path(class_id)
        data = load_json(path)
        old = data["question_hashes"]
        current = {q.id: q.rubric_hash() for q in test.questions}
        changed = sorted(q for q in current if old.get(q) != current[q])
        points = {q.id: q.points for q in test.questions}
        for student in data["students"]:
            kept = [a for a in student["answers"] if a["question_id"] in current and a["question_id"] not in changed]
            for question_id in changed:
                kept.append(_pending_answer(question_id, points[question_id], "The rubric changed. Look at this answer again."))
            order = {q.id: i for i, q in enumerate(test.questions)}
            student["answers"] = sorted(kept, key=lambda a: order[a["question_id"]])
            student.pop("declared_total", None)
        data["rubric_hash"] = test.rubric_hash()
        data["question_hashes"] = current
        save_json(path, data)
        return changed

    # -- saved test packages, for reusing a confirmed test in a later session --
    def export_test(self, out_path: Path) -> Path:
        issues = Issues()
        test = self.load_test(issues)
        if test is None or issues.errors:
            raise PaperGraderError("Only a valid test can be exported: " + "; ".join(i.message for i in issues.errors))
        names = {r.source_pdf for r in (test.blank, test.key) if r.source_pdf}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.test_path, "test.json")
            for name in sorted(names):
                archive.write(self.source_path(name), f"sources/{name}")
        return out_path

    def import_test(self, package: Path) -> TestDefinition:
        with zipfile.ZipFile(package) as archive:
            for member in archive.namelist():
                parts = Path(member).parts
                if member != "test.json" and not (len(parts) == 2 and parts[0] == "sources" and Path(member).name == parts[1]):
                    raise PaperGraderError(f"Unexpected file in test package: {member}")
            if self.test_path.exists():
                raise PaperGraderError("This job already has a test.json. Import into a new job.")
            archive.extractall(self.root)
        issues = Issues()
        test = self.load_test(issues)
        if test is None or issues.errors:
            raise PaperGraderError("The imported test is invalid: " + "; ".join(i.message for i in issues.errors))
        for reference in (test.blank, test.key):
            if reference.source_pdf and sha256_file(self.source_path(reference.source_pdf)) != reference.sha256:
                raise PaperGraderError(f"{reference.source_pdf} doesn't match the hash recorded when the teacher confirmed it.")
        return test


def source_pages_for(page_map: PageMap, order: int) -> list[dict[str, Any]]:
    return [
        {"slot": s.slot, "source_pdf": s.source_pdf, "source_page": s.source_page, "page_in_packet": s.page_in_packet}
        for s in page_map.slots_for_student(order) if s.kind == "scan"
    ]


def _pending_answer(question_id: str, points: Any, notes: str = "") -> dict[str, Any]:
    from .grading_models import format_points

    return {
        "question_id": question_id, "observed_kind": "not_inspected", "observed_answer": "", "decision": "pending",
        "awarded_points": None, "max_points": format_points(points),
        "verification": {"status": "not_inspected", "method": None, "image_ref": None},
        "confidence": {"alignment": "low", "reading": "low", "interpretation": "low"}, "notes": notes,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_profile(profile: dict[str, Any], issues: Issues) -> None:
    for problem in validate_profile(profile):
        issues.error("printer_profile_invalid", problem, "printer_profile")
