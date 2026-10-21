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

## 2026-10-18 — Red-key proposals, linear answer key, and matching review

- **Detected areas are ordinary questions with `origin` and `confirmed` flags.** Manual and confirmed questions survive another detection run; unconfirmed proposals can be replaced. Editing or moving a proposal confirms it. Why: one question model keeps canvas, grading, deletion, and persistence consistent while preserving teacher decisions.
- **The existing question sidebar is the linear answer key.** Labels, crop thumbnails, types, expected answers, points, confirmation, and order are edited in this single list. Why: a second answer list would create competing sources of truth.
- **Key crops are cached in memory by question geometry, not persisted.** Why: repeated sidebar redraws should not recrop unchanged regions, while scans and derived images remain outside localStorage.
- **A separate score box controls printed score placement.** It behaves like the name area and is saved in the session. Without it, printing retains the existing top-right placement and calibrated geometry.
- **A student's total score is withheld when any answer is ungraded or flagged.** Graded, unflagged marks can still print; flagged answers print no mark. Why: an incomplete review must not appear to be a final total. Calibration remains unchanged.
- **Proportional matching credit lives in `record.credit`.** Matching details and corrected connections remain on the record for review. Ordinary teacher status buttons clear automatic credit/details; the matching review panel applies a connection-based fraction. Partial grades without credit retain the existing half-points behavior.
- **Split-box editing and page-identity rekeying are deferred.** Why: proposal review, merging, manual boxes, and the existing scan fingerprint cover this integration without expanding into new editing tools or session identity migration.

## 2026-10-18 — Red-ink detection and local matching grader

- **Red detection is local HSV thresholding on a ~1200 px working copy of the key only** (`redDetect.js`, DOM-free, Node-tested). Specks are dropped, strokes are joined with an anisotropic dilation (wider horizontally than vertically) so one handwritten word stays one region while answers ~2.5% of page width apart stay separate. Why: it is free, private, and fast, and only crops (never full pages) are ever handed to later graders. Rejected: OCR/AI on the full page.
- **Proposals are ordered row-major** (top-to-bottom, then left-to-right inside a row band). Column-major worksheets need "Renumber" plus ↑/↓, which is acceptable because labels are a convenience; grading order is the list order.
- **A region is proposed as `matching` when it is a sparse web with several line ends on both its left and right edges** (or contains ≥2 long separate strokes). Why: crossing lines form one connected component, so counting components alone missed real matching blocks, and a single-stroke rule misclassified wide red circles. Matching regions get extra padding so endpoint dots are inside the crop.
- **Detection is conservative:** uncertain regions are still proposed (amber, "?") and every proposal needs confirmation. Relabelling or reordering is not confirmation; moving, resizing or editing a box is.
- **Matching grading ladder:** whole-web similarity → connection-graph tracing → (future) AI fallback → teacher. Stage 2 always runs because it is free; high similarity alone can never mark a web correct if the traced graph disagrees, since one swapped pair barely changes pixel similarity. Any unresolved node, or one stroke claimed by two left nodes, sends the answer to review (status null) — never a confident wrong.
- **Printed background is the key crop's dark non-red ink** and is subtracted from the student crop before tracing; pale anti-aliased red edges must count as red, otherwise subtraction erases student strokes lying on the key's paths. `options.templateImage` is reserved for subtracting a blank test later.
- **AI fallback hook** (`registerFallback` in `graders.js`) receives only the small student crop plus endpoint coordinates and must return `{ connections, confidence }`, which is validated and compared locally. No fallback is registered.
- **Tests include realistic browser-rendered PNG crops** (`tests/fixtures/matching/`) decoded by a test-only PNG reader, because purely synthetic fixtures passed while real anti-aliased crops failed.

## 2026-10-18 — Offline build is generated, not hand-maintained

- **`offline/` is produced by `tools/build-offline.mjs`** from the web sources: modules are concatenated in dependency order inside isolated scopes with import/export removed, PDF.js comes from the bundled UMD `pdf.min.js` with its worker embedded, and the service worker, manifest and web fonts are dropped so it runs from `file://`. Why: the first offline build was a hand-made copy of build 1 and silently missed every later feature. A test compares the committed bundle with a fresh build so a stale bundle fails `npm test`/CI. Rejected: a bundler dependency (the project stays dependency-free) and editing `offline-app.js` by hand.
## 2026-10-21 — Separate setup scan: blank test + completed key

- **Test setup is a separate stage from student scanning.** The normal workflow is now: (1) load/scan a blank original test, (2) load/scan the teacher's completed answer key, (3) align the completed key to the blank original and extract only teacher-added ink/marks, then (4) load the student scan stack as a separate grading stage. Why: setup pages should not be mixed into the student PDF or student count, and the blank original provides a much stronger reference for subtraction, alignment, answer-region discovery, and later student-ink extraction.
- **The blank original is the canonical page coordinate system.** The completed key and every student page should be registered to it before crops, comparisons, or print-coordinate decisions are made. Registration should correct small translation, rotation, scale, crop, and—when needed—perspective/skew differences. Poor registration confidence must block automatic grading for that page rather than silently continuing.
- **Answer-region discovery should prefer image differencing between the aligned blank original and completed key.** Red-ink detection remains a useful optional accelerator/fallback, not a requirement; teacher answers may be any color if the blank original is available.
- **The student scan stack is a distinct input after setup.** It may be one multipage PDF containing one student sheet per page. The blank test and answer key are not student pages and are never printed as student corrections.
- **Registration marks are deferred/back-burner, not part of the normal workflow.** The default alignment strategy should work on ordinary existing tests using page geometry plus stable printed features/template matching. Fiducial marks may be revisited later as an optional reliability enhancement for teacher-generated worksheets, but the product must not depend on them.

## 2026-10-21 — Confidence, matching, print safety, and AI-cost policy

- **There is no single universal confidence threshold.** Alignment, extraction/OCR, and interpretation each keep their own confidence. The effective grading confidence is governed by the weakest material stage rather than multiplying scores or trusting a model's self-reported confidence as calibrated probability.
- **Starting auto-grade policy is intentionally conservative:** results at roughly 0.99+ may be eligible for automatic grading; roughly 0.95–0.99 should try the next deterministic/local method or an AI fallback when configured; below that goes to teacher review. A confident automatic × should be at least as strict as an automatic ○. These are starting thresholds only and must be calibrated against real classroom scans; the product goal is extremely high precision among answers it auto-grades, not maximizing coverage.
- **Matching does not require perfect path tracing when the answer web is clearly the same.** First compare the isolated/normalized student ink web with the key web. A very high web match can accept the section as correct without resolving every crossing. When the web differs, local endpoint/trajectory analysis determines individual pairings. At crossings, use directional continuity/minimum angular change and stroke continuity; genuinely ambiguous crossings must never be guessed.
- **Matching fallback ladder is:** whole-web similarity → local endpoint/connection analysis → optional AI on the small matching crop only → teacher review. If the local graph is clean, specific wrong pairings can be identified and proportional credit awarded.
- **Optional second stack scan before printing is a safety feature, not a required step.** When used, PaperGrader compares the physical print stack against the grading scans/template to detect swaps, missing sheets, reversed order, or off-by-one shifts and reorder/block overlays as needed. Skipping verification remains allowed with an explicit stack-order reminder.
- **Page identity must be separate from page index** so future verified/reordered print stacks can map correction overlays to the correct student rather than assuming scan order forever.
- **AI usage must be visible and bounded when AI is later enabled.** Session UI should show call count, answers sent to AI, model(s), token usage when returned by the provider, and estimated/actual cost. Support a configurable spend limit; once reached, unresolved answers become teacher-review items rather than silently making more paid calls.
- **Preferred cost ladder is local/deterministic first, then AI only for unresolved crops.** Simple structured items should never require AI. A small/cheap model may handle simple uncertain handwriting, while harder items can route directly to a stronger model or escalate only when that is demonstrably cost-effective. Repeated low-value escalation should be avoided because both calls cost money.
- **If any answer remains unresolved, its correction mark stays blank and the final score stays unprinted.** This remains the print-safety rule even when AI is available.
