"""Prove the current session can actually see images, before any grading starts.

Grading must come from looking. Some runtimes accept an image without giving the
model any way to see it, and the failure would otherwise be invisible. This
draws a random number as pen strokes (no text layer to extract) and stores only
a salted hash, so the number can be answered only by viewing the image.

It proves capability, not diligence. It can't prove that every answer was
examined; the grading record and the teacher's spot check carry that part.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pymupdf

from .common import PaperGraderError, load_json, save_json
from .correction_overlay import digit_paths, draw_strokes

_ATTEMPTS = 3


def _digest(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


def issue_challenge(state_path: Path, image_path: Path, code: Optional[str] = None) -> Path:
    """Write the challenge image. ``code`` exists only so synthetic fixtures are reproducible."""
    code = code or f"{secrets.randbelow(9000) + 1000}"
    salt = secrets.token_hex(16)
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=120)
    shape = page.new_shape()
    draw_strokes(shape, digit_paths(code, 40, 28, 64), 4.0, (0.1, 0.1, 0.1), lambda x, y: (x, y))
    shape.commit()
    image_path.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(dpi=144, alpha=False).save(image_path)
    doc.close()
    save_json(state_path, {"passed": False, "salt": salt, "digest": _digest(code, salt), "attempts_left": _ATTEMPTS, "image": str(image_path), "passed_at": None})
    return image_path


def answer_challenge(state_path: Path, answer: str) -> bool:
    if not state_path.is_file():
        raise PaperGraderError("No vision check is open. Run vision-check first.")
    state = load_json(state_path)
    if state.get("passed"):
        return True
    if state["attempts_left"] <= 0:
        raise PaperGraderError("Out of attempts. Run vision-check for a new image, or stop: this session may be unable to see images.")
    if _digest(answer.strip(), state["salt"]) == state["digest"]:
        state["passed"] = True
        state["passed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_json(state_path, state)
        return True
    state["attempts_left"] -= 1
    save_json(state_path, state)
    return False


def has_passed(state_path: Path) -> bool:
    return state_path.is_file() and load_json(state_path).get("passed") is True
