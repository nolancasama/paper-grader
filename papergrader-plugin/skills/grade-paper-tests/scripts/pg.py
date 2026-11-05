#!/usr/bin/env python3
"""Run PaperGrader from wherever the plugin was installed.

    python pg.py doctor

Looks for the package two ways: the plugin layout (three folders up from here),
and an unpacked runtime bundle in the working directory.
"""
import sys
from pathlib import Path

for candidate in (Path(__file__).resolve().parents[3], Path.cwd()):
    if (candidate / "papergrader" / "__init__.py").is_file():
        sys.path.insert(0, str(candidate))
        break
else:
    print('{"command": "launcher", "can_process_pdfs": false, "verdict": "The papergrader package is not reachable from this skill. This surface did not install the whole plugin. Stop and tell the teacher; do not pretend to have run anything."}')
    sys.exit(2)

from papergrader.cli import main  # noqa: E402

sys.exit(main())
