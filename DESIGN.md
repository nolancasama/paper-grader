# PaperGrader — Frozen Product / Architecture Spec

Audience: classroom teachers grading one-page paper tests with a school copier/printer.
Primary constraint: fast, private, inexpensive grading that can still work on locked-down school PCs.

## Core workflow

### Stage A — Test setup

1. **Blank test** — load or scan one untouched original test.
2. **Completed answer key** — load or scan the same test completed by the teacher.
3. **Align key to blank** — register the completed key to the blank-test coordinate system.
4. **Extract teacher additions** — subtract the aligned blank test from the completed key so teacher-added writing, circles, checks, and matching lines remain.
5. **Propose answer regions** — group the added ink into candidate graded regions.
6. **Teacher verification** — move, resize, merge, delete, or manually add regions. Manual box drawing always remains available.
7. **Linear answer key** — the question sidebar is the authoritative list: label/order, key crop, question type, expected answer, points, confirmation state.
8. **Name area / score area** — optional name box plus a separate final-score box saved with the setup.

Red-ink detection remains an optional accelerator/fallback. It is no longer required when a blank original is available.

### Stage B — Student grading

9. **Student scan stack** — load a separate multipage PDF/images containing one student sheet per page.
10. **Register every student page to the blank template** before extracting answer crops.
11. **Auto-grade by question type** using the cheapest reliable method first.
12. **Review only uncertain answers.**
13. **Results** — totals, percentages, per-question marks, CSV, class/question statistics.

### Stage C — Physical correction printing

14. Re-feed the same physical student sheets.
15. Optional **second stack verification scan** can identify swaps, missing sheets, reversed order, or off-by-one shifts before printing.
16. Print only the correction overlay: ○ / △ / × and final score.
17. Any unresolved/flagged answer stays unmarked; if a student has any unresolved answer, the final score is not printed.

## Canonical coordinate system and alignment

The **blank original test is the canonical page coordinate system**.

Before answer extraction or grading, align the answer key/student page to the blank template. Default alignment must not depend on special registration marks.

Preferred alignment ladder:

1. page-boundary / orientation normalization
2. stable printed-feature or template matching
3. translation + rotation + scale correction
4. affine/perspective correction when needed
5. confidence score
6. low-confidence pages go to visual review, never silent auto-grading

A translucent overlay/blink view is a human verification tool for questionable pages, not the normal alignment method.

Registration/fiducial marks are explicitly back-burner: optional future reliability aids only.

## Answer discovery

Preferred setup pipeline:

`aligned completed key - aligned blank test -> teacher-added ink -> connected/grouped regions -> proposed questions`

Do not OCR or send a whole test page to AI just to find answers.

Question proposals are editable and use the same question model as manually drawn boxes.

## Automatic grading architecture

Auto-graders plug into the shared grader registry. Different answer types use different strategies.

### Structured/local-first examples

- blank/nonblank detection: local
- circle/bubble/checkbox choice: local image analysis
- matching: local web/connection analysis
- clean numbers/printed text: local OCR where practical
- scoring/results/printing: deterministic local logic

### Written / difficult answers

Use tight answer crops only. Local OCR/recognition first; AI only for unresolved cases when enabled.

Never send an entire student test to AI when only one answer needs help.

## Confidence policy

Do not use one universal confidence score for every subsystem.

Track at least:

- alignment confidence
- answer extraction/recognition confidence
- interpretation/comparison confidence

The weakest material stage governs whether an answer may be auto-graded.

Initial conservative policy:

- ~0.99+ — eligible for automatic grading
- ~0.95–0.99 — try another reliable local method / configured AI fallback
- below ~0.95 — teacher review

Automatic wrong marks should be at least as conservative as automatic correct marks.

These thresholds are starting points, not truths. Calibrate them against real classroom scans and optimize for extremely high precision among auto-graded answers.

## Matching grader

Treat the whole matching exercise as one region.

Matching ladder:

1. isolate/normalize the student ink web and compare it with the key web
2. if the web is extremely similar, accept the whole section as correct without needing perfect crossing reconstruction
3. when the web differs, infer left/right endpoints and connection paths
4. at intersections, prefer directional continuity / minimum angular change / stroke continuity
5. if a crossing is genuinely ambiguous, do not guess
6. optional future AI sees only the small matching crop and returns structured connections
7. unresolved answers go to teacher review

When the connection graph is clean, identify specific wrong pairings and award proportional credit.

## AI cost policy

PaperGrader is **AI-assisted, not AI-dependent**.

Cost ladder:

`local deterministic/CV -> local OCR -> cheap AI for suitable uncertain crops -> stronger AI only for genuinely hard crops -> teacher review`

Avoid automatically escalating every cheap-model failure if the escalation rate makes double-calling uneconomical.

When AI is enabled, show a session usage meter with:

- number/percentage of answers handled locally
- number sent to AI
- model(s)
- call count
- token usage when provided
- estimated/actual cost
- escalation count/rate
- unresolved teacher-review count

Support an optional spending cap. At the cap, further uncertain answers become review items.

## Page identity and print safety

Do not permanently equate a student with page index.

Store page/student identity separately so a future second verification scan can remap overlays if the physical stack order changes.

The optional verification scan should be able to detect:

- swapped sheets
- missing sheets
- extra sheets
- reversed stack
- one-sheet/off-by-one shift

If verification confidence is insufficient, block automatic correction printing for affected sheets rather than risk printing another student's marks.

## Printing

Existing print calibration remains:

- paper size
- X/Y print offsets
- reverse order
- rotate 180°
- alignment test
- score-area placement

Scan/template alignment and printer calibration are separate problems.

## Privacy / offline requirements

- Student page processing stays local by default.
- Scanned page images are not uploaded merely for alignment or local grading.
- Offline build must remain functional from `file://` on locked-down school PCs.
- Runtime CDN dependencies should not be required by the offline package.
- If AI is later configured, send only the minimum answer crop required and make that usage explicit to the teacher.
