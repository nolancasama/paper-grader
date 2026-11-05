"""Shared fixtures. All data is synthetic, and every grade is typed in as fixture truth.

These tests exercise PDF mechanics, arithmetic and validation. Nothing here shows
that Python can read handwriting, because it doesn't try to.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from papergrader import demo  # noqa: E402
from papergrader.common import load_json, save_json  # noqa: E402
from papergrader.job import Job  # noqa: E402
from papergrader.pipeline import build_class  # noqa: E402


def make_job(tmp_path: Path, students, template_pages: int = 1, class_id: str = "c1", label: str = "Class One", **test_changes) -> SimpleNamespace:
    """A private job with one class of synthetic students, ready to build."""
    job = Job.create(tmp_path / "job")
    work = tmp_path / "inputs"
    work.mkdir(exist_ok=True)
    test = demo.setup_test(job, work, template_pages)
    if test_changes:
        test.update(test_changes)
        save_json(job.test_path, test)
    demo.setup_class(job, work, class_id, label, students, test)
    return SimpleNamespace(job=job, class_id=class_id, test=test, work=work)


@pytest.fixture
def perfect_student():
    return demo.SyntheticStudent("Aiko Sample", "1", demo._all_correct_written(), demo._judged())


def ninety_student() -> demo.SyntheticStudent:
    return demo.SyntheticStudent("Ninety Pupil", "2", {**demo._all_correct_written(), "1.5": "5"}, demo._judged({"1.5": ("incorrect", 0)}))


def below_student() -> demo.SyntheticStudent:
    return demo.SyntheticStudent(
        "Seventy Pupil", "3", {**demo._all_correct_written(), "1.2": "1", "2.1": "a dog", "3.1": "vehicle"},
        demo._judged({"1.2": ("incorrect", 0), "2.1": ("incorrect", 0), "3.1": ("incorrect", 0)}),
    )


def pending_student() -> demo.SyntheticStudent:
    return demo.SyntheticStudent(
        "Pending Pupil", "4", {**demo._all_correct_written(), "1.3": "8"}, demo._judged({"1.3": ("pending", None)}),
        pending_reason={"1.3": "Can't tell 1 from 7, even enlarged."},
    )


def ungraded_student() -> demo.SyntheticStudent:
    return demo.SyntheticStudent(None, None, {"1.1": "4"}, {}, uninspected=True)


@pytest.fixture(scope="session")
def built_demo(tmp_path_factory) -> SimpleNamespace:
    """A finished two-class demo. Read-only: tests that change things build their own."""
    root = tmp_path_factory.mktemp("demo") / "job"
    reports = demo.run_demo(root)
    return SimpleNamespace(job=Job(root), reports=reports, class_a="demo-class-a", class_b="demo-class-b")


def edit_json(path: Path, change) -> None:
    data = load_json(path)
    change(data)
    save_json(path, data)


def plans_of(job: Job, class_id: str) -> list[dict]:
    return load_json(job.output_dir(class_id) / f"{class_id}_overlay_plan.json")["plans"]


def error_codes(report: dict) -> set[str]:
    return {e["code"] for e in report["errors"]}


def ink_center(page: pymupdf.Page, dpi: int = 72, min_red: bool = False) -> tuple[float, float] | None:
    """Centre of the red ink on a rendered page, in points."""
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    xs, ys = [], []
    data = pix.samples
    for y in range(pix.height):
        for x in range(pix.width):
            i = (y * pix.width + x) * pix.n
            if data[i] > 170 and data[i + 1] < 90 and data[i + 2] < 90:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs) + max(xs)) / 2 / zoom, (min(ys) + max(ys)) / 2 / zoom


def has_ink(page: pymupdf.Page, dpi: int = 36) -> bool:
    return any(bytes(page.get_pixmap(dpi=dpi, alpha=True).samples)[3::4])


__all__ = ["make_job", "build_class", "copy", "edit_json", "plans_of", "error_codes", "ink_center", "has_ink"]
