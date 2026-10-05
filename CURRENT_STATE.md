# Current State

## Status

PaperGrader v2 build 1 is implemented as a static vanilla JavaScript ES-module app with no build step or test suite. The repository is configured to deploy from the `main` root to GitHub Pages at https://nolancasama.github.io/paper-grader/. Build 1 was pushed to `main` on 2026-10-06.

## What Exists

Five-step workflow: scan an answer key plus student pages → define typed answer areas and a separate name area → review one question across the class → inspect/export results → print correction overlays onto the original student sheets.

- Answer-key-first mode defaults on; the key is excluded from student counts, results, and printing.
- Answer areas support type, points, optional expected answer, selection, moving, resizing, deletion, and sidebar navigation.
- Grading includes question progress and flagged counts, key and name crops, compact cards, filters, bulk remaining-○, and keyboard navigation.
- Results include editable names, totals, percentages, per-question marks, class average, per-question correct rate, and UTF-8-with-BOM CSV export.
- Japanese and English UI, defaulted from browser language and persisted locally.
- A frozen grader registry and auto-grade result rules are present, but no grader is registered in this build; the auto-grade button is therefore hidden.
- Sessions persist under `papergrader-session-v2`, keyed by scan fingerprint. Page images are not stored. Printer settings persist across scans.
- Existing calibrated print geometry remains intact: paper size, X/Y offset, 180° rotation, reverse order, and alignment test.
- Reliability safeguards remain: network-first service worker, natural file sort, beforeunload prompt, ungraded-print confirmation, aspect-ratio warning, and pointer-cancel handling.

## Known Issues

- The whole grade grid rerenders on every grade; this may be slow for 35–40 students.
- Every page is held as a full-size canvas (roughly 10 MB each), creating memory risk on iPads and Chromebooks.
- The score is always printed top-right and may overlap the paper's name or score area.
- Actual auto-graders are not included in build 1.
- Real-copier alignment has not yet been tested.

## Next Steps

1. Run a real copier alignment test with a photocopy (see README).
2. Implement and register answer-type graders.
3. Reduce rerendering and page-canvas memory use.
4. Make printed score position configurable.
