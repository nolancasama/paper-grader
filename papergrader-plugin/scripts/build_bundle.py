#!/usr/bin/env python3
"""Build the two distributable zips, and refresh the bundled instructions.

    python scripts/build_bundle.py [--out dist]

papergrader-plugin.zip    the plugin, for a workspace upload
papergrader-runtime.zip   the code and art only, to attach to a chat whose
                          sandbox can run Python but didn't install the plugin
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
EXCLUDE_DIRS = {".venv", "__pycache__", ".pytest_cache", "tests", "examples", "dist"}
RUNTIME_ITEMS = ("papergrader", "assets", "printers", "requirements.txt")
INSTRUCTIONS = "CHATGPT_GRADING_INSTRUCTIONS.md"


def _files(base: Path):
    for path in sorted(base.rglob("*")):
        if path.is_file() and not (set(path.relative_to(ROOT).parts) & EXCLUDE_DIRS) and path.suffix != ".pyc":
            yield path


def _write(out: Path, paths) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "dist"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # The repository root copy stays authoritative. The skill carries an exact copy.
    source = REPO / INSTRUCTIONS
    copy = ROOT / "skills" / "grade-paper-tests" / "references" / INSTRUCTIONS
    if source.is_file() and (not copy.is_file() or copy.read_bytes() != source.read_bytes()):
        shutil.copyfile(source, copy)

    _write(out / "papergrader-plugin.zip", _files(ROOT))
    runtime = []
    for item in RUNTIME_ITEMS:
        path = ROOT / item
        runtime.extend(_files(path) if path.is_dir() else [path])
    _write(out / "papergrader-runtime.zip", runtime)
    print(f"wrote {out / 'papergrader-plugin.zip'}")
    print(f"wrote {out / 'papergrader-runtime.zip'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
