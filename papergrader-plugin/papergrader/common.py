"""Small shared helpers: issues, JSON files, hashing and plugin paths."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PLUGIN_ROOT / "assets"
PRINTERS_DIR = PLUGIN_ROOT / "printers"

MM = 72.0 / 25.4  # PDF points per millimetre
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class PaperGraderError(Exception):
    """A problem the operator must fix; the CLI reports it without a traceback."""


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" blocks printing; "warning" needs a human to read it
    code: str
    message: str
    where: str = ""

    def to_json(self) -> dict[str, str]:
        return {"severity": self.severity, "code": self.code, "message": self.message, "where": self.where}


class Issues:
    """An ordered collection of validation findings."""

    def __init__(self) -> None:
        self.items: list[Issue] = []

    def error(self, code: str, message: str, where: str = "") -> None:
        self.items.append(Issue("error", code, message, where))

    def warning(self, code: str, message: str, where: str = "") -> None:
        self.items.append(Issue("warning", code, message, where))

    def extend(self, other: "Issues") -> None:
        self.items.extend(other.items)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.items if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.items if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> set[str]:
        return {i.code for i in self.items}

    def to_json(self) -> dict[str, list[dict[str, str]]]:
        return {"errors": [i.to_json() for i in self.errors], "warnings": [i.to_json() for i in self.warnings]}


def load_json(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise PaperGraderError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PaperGraderError(f"{path} is not valid JSON: {exc}") from exc


def save_json(path: Path, data: Any) -> None:
    """Write JSON atomically so a crash can't leave a half-written grading file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def inside_git_worktree(path: Path) -> bool:
    """True when ``path`` lies inside a git checkout. Used to keep student data out of repos."""
    current = path.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return True
    return False
