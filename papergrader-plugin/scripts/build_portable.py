#!/usr/bin/env python3
"""Build a no-install Windows folder: Python, the libraries and the plugin together.

    python scripts/build_portable.py --out C:\\somewhere [--python-version 3.13.9]

For 64-bit Windows PCs where you can't install software. It doesn't include Codex
or the ChatGPT app. It also doesn't override school IT policy: a managed PC can
still refuse to run python.exe from a user folder.

The output is a local build. It isn't committed: PyMuPDF is AGPL-3.0 and this
repository doesn't redistribute it.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "PaperGrader-Portable"
EXCLUDE = {".venv", "__pycache__", ".pytest_cache", "tests", "examples", "dist"}

MARKETPLACE = """{
  "name": "paper-grader-local",
  "interface": {"displayName": "PaperGrader (private)"},
  "plugins": [
    {
      "name": "papergrader",
      "source": {"source": "local", "path": "./papergrader-plugin"},
      "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
      "category": "Productivity"
    }
  ]
}
"""

LAUNCHER = r"""@echo off
rem Opens a window where "python" means the Python in this folder.
set "PG_HOME=%~dp0"
set "PATH=%PG_HOME%python;%PATH%"
title PaperGrader
python "%PG_HOME%papergrader-plugin\skills\grade-paper-tests\scripts\pg.py" doctor
echo.
echo If can_process_pdfs is true, PDF processing works on this PC.
echo Start Codex from THIS window, so it finds this Python.
echo.
cmd /k
"""

GUIDE = """PaperGrader, no-install version (64-bit Windows)

1. Unzip this whole folder somewhere you can write, such as Documents.
   Don't run it from inside the zip.

2. Double-click PaperGrader.bat. A window opens and tests the setup.
   - can_process_pdfs: true means it works.
   - If Windows says the program is blocked, this PC's policy forbids it.
     Ask school IT. Please don't try to get around it.

3. You still need Codex or the ChatGPT desktop app on this PC. This folder
   doesn't include them. Once per PC, in that same window, run:

       codex plugin marketplace add "%PG_HOME%."
       codex plugin add papergrader@paper-grader-local

4. Always start Codex from the PaperGrader.bat window. Started any other way,
   it won't find this Python.

5. In a new session, ask:
   "Run PaperGrader's doctor, then the vision check, and show me the raw output."

Student data: keep job folders in a private location, not a shared drive or a
shared PC profile, and check your school's rules. Delete them when you're done.

Full guide: papergrader-plugin/README.md
"""


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def copy_plugin(destination: Path) -> None:
    def ignore(_: str, names: list[str]) -> list[str]:
        return [n for n in names if n in EXCLUDE or n.endswith(".pyc")]

    shutil.copytree(ROOT, destination, ignore=ignore)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--python-version", default="3.13.9")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    folder = out / NAME
    if folder.exists():
        print(f"{folder} already exists. Choose another --out, or remove it yourself.")
        return 1
    folder.mkdir(parents=True)

    version = args.python_version
    archive = out / f"python-{version}-embed-amd64.zip"
    if not archive.exists():
        url = f"https://www.python.org/ftp/python/{version}/{archive.name}"
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, archive)
    python_dir = folder / "python"
    with zipfile.ZipFile(archive) as source:
        source.extractall(python_dir)

    # Embedded Python ignores PYTHONPATH and the current folder, and reads only its
    # ._pth file. So the libraries and the plugin have to be listed there, or
    # `python -m papergrader` fails. Paths are relative to this file, so the folder can move.
    short = "".join(version.split(".")[:2])
    pth = python_dir / f"python{short}._pth"
    pth.write_text(f"python{short}.zip\n.\nLib\\site-packages\n..\\papergrader-plugin\nimport site\n", encoding="utf-8")

    site_packages = python_dir / "Lib" / "site-packages"
    # --no-deps, with an explicit list: PyMuPDF's optional layers bring in onnxruntime
    # and other document-AI packages this tool never uses and must not rely on.
    run(
        sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--target", str(site_packages),
        "--platform", "win_amd64", "--python-version", ".".join(version.split(".")[:2]), "--only-binary=:all:", "--no-deps",
        "pymupdf", "openpyxl", "et_xmlfile",
    )

    copy_plugin(folder / "papergrader-plugin")
    marketplace = folder / ".agents" / "plugins"
    marketplace.mkdir(parents=True)
    (marketplace / "marketplace.json").write_text(MARKETPLACE, encoding="utf-8")
    (folder / "PaperGrader.bat").write_text(LAUNCHER.replace("\n", "\r\n"), encoding="ascii", newline="")
    (folder / "START_HERE.txt").write_text(GUIDE.replace("\n", "\r\n"), encoding="utf-8", newline="")

    zip_path = out / f"{NAME}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as target:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                target.write(path, Path(NAME) / path.relative_to(folder))
    print(f"wrote {zip_path} ({zip_path.stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
