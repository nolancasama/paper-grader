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

## 2026-10-05 — v2 redesign direction (user decisions)

- **Workflow is review-first, built around an answer key** scanned as page 1.
  Why: the teacher expected the app to grade automatically; manual judging of
  every answer was the main cost. Full spec in `DESIGN.md`.
- **Grading split by answer type**: circled choices graded locally by ink
  comparison against the key (free, private); written words, numbers and
  matching lines graded by AI with low-confidence answers flagged for review.
  Rejected: pixel comparison for handwriting (different handwriting never
  matches) and for matching lines (line paths vary).
- **Auto-graders plug in via a frozen Grader interface** (`graders.js`) in
  separate files, so the core app can ship before any grader exists.
- **Japanese + English UI toggle**, default by browser language.
- **Laptop-first** (mouse + keyboard); tablet must not break.
- **Visual direction "Calm teacher's desk"**: warm paper tones, red-pen accent
  for marks, following the Japanese ○/×-in-red convention. Rejected: clean
  dense tool look, bold playful look.

## 2026-10-05 — v2 build 1 implementation boundaries

- **The first page is assigned the answer-key role, not treated as a special
  student.** It is excluded consistently from student counts, results, and
  print output. Why: a single page-role rule prevents workflow and print
  indexing from disagreeing.
- **v2 sessions use the new `papergrader-session-v2` namespace without v1
  migration.** Why: the question, name-area, and grade-record shapes changed;
  silently adapting an old session could attach grades to the wrong regions.
- **The core app depends only on the frozen registry in `graders.js`.** No
  answer-type grader is imported or registered in build 1, and auto-grade UI is
  hidden when no relevant grader exists. Why: the review workflow can ship and
  remain testable without coupling it to a particular recognition service.
- **The existing correction-overlay and print geometry was retained while the
  workflow and visual UI were rebuilt.** Why: offsets, rotation, reverse order,
  and paper scaling are calibrated behavior whose semantics must not drift.
