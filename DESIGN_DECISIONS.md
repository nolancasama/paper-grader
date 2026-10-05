# Design Decisions

This file records meaningful product, UX, visual, architectural, or behavioral decisions for this project.

For each significant decision, record:

- Date
- What was decided or changed
- Why
- Previous approach, if relevant
- Rejected alternatives, if useful

Only record decisions that may be useful to understand later.

Do NOT record:
- trivial UI adjustments
- routine bug fixes
- formatting changes
- mechanical refactors with no design consequence
- every individual code modification

Git is the source of truth for detailed code-change history.

A useful rule:

> If a future developer or AI could reasonably ask, "Why is it designed this way?", record the answer here.

## 2026-10-05 — Reliability pass after first GitHub Pages deploy

- **Service worker is network-first** for same-origin requests, falling back to
  cache offline; cache name bumped per release. Why: cache-first with a fixed
  cache name meant teachers would never receive updates. Rejected: removing the
  service worker (loses offline use in classrooms with bad Wi-Fi).
- **Grading session persists to localStorage, scans do not.** Questions, grades,
  names and print settings are saved, keyed by a fingerprint of the loaded
  files (names, sizes, page count). Re-loading the same scan restores the
  session. Why: a refresh must not lose a class's grading; page images are far
  too large for localStorage and re-selecting the scan is cheap. Rejected:
  storing page images in IndexedDB (larger change, revisit with memory work).
- **Leaving the page with unsaved-looking work prompts** (beforeunload) whenever
  questions exist.
- **Files are sorted by natural filename order** before loading, since page
  order = student order and the file picker guarantees no order.
- **Deleting a question removes only that question's grades.**
- **Printing warns, never blocks**: a confirm before printing corrections when
  any student has ungraded questions, and a visible warning when any page's
  aspect ratio differs from the chosen paper by more than 2% (marks would be
  stretched). Teacher can proceed either way.
