# Current State

## Status

PaperGrader is a static vanilla JavaScript ES-module app with no build step or dependencies. `npm test` runs the algorithm tests. The repository is configured to deploy from the `main` root to GitHub Pages at https://nolancasama.github.io/paper-grader/. The current UI integrates red-key detection and the local matching-lines grader.

## What Exists

Five-step workflow: scan an answer key plus student pages → review proposed or manual answer areas → review one question across the class → inspect/export results → print correction overlays onto the original student sheets.

- Answer-key-first mode defaults on; the key is excluded from student counts, results, and printing. Red-key detection runs once when a loaded session has no questions, with a manual detection button on Scan and Answer areas. Rerunning replaces only unconfirmed proposals and skips proposals overlapping retained areas.
- Proposals are ordinary questions with origin, confirmation, confidence, and uncertainty metadata. Dashed red/amber boxes distinguish proposals, and editing or moving confirms them. Teachers can confirm individually or together, draw manually, delete, reorder, renumber by position, and merge multiple selected questions.
- The existing sidebar is the linear answer key, with editable labels, cached key thumbnails, six answer types, expected answers, points, and proposal/OCR status. Name and score areas are separate from graded questions.
- Grading includes question progress and flagged counts, key and name crops, compact cards, filters, bulk remaining-○, and keyboard navigation.
- Results include editable names, totals, percentages, per-question marks, class average, per-question correct rate, and UTF-8-with-BOM CSV export. Matching partial credit uses `record.credit`; ordinary manual partial grades retain half credit.
- Japanese and English UI, defaulted from browser language and persisted locally.
- Matching grading runs locally through the registry, retaining details even when confidence requires review. Its review panel lets teachers correct connections and apply proportional credit.
- Sessions persist under `papergrader-session-v2`, keyed by scan fingerprint, including question metadata, score/name areas, and matching detail/credit. Older questions without proposal fields behave as confirmed manual questions. Page images and key thumbnails are not persisted; thumbnails are cached in memory by geometry. Printer settings persist across scans.
- Existing calibrated print geometry remains intact: paper size, X/Y offset, 180° rotation, reverse order, and alignment test. Scores use the optional score box or the existing top-right fallback. Students with any ungraded or flagged answer receive no printed score; flagged answers receive no mark. Graded, unflagged marks still print. Calibration output is unchanged.
- A double-click offline build for locked-down PCs lives in `offline/` (classic scripts, bundled PDF.js with embedded worker, no network). It is generated from the web sources by `npm run build:offline`; `npm test` fails if the committed bundle is stale, and CI packages it as an artifact.
- Reliability safeguards remain: network-first service worker, natural file sort, beforeunload prompt, unreviewed-print confirmation, aspect-ratio warning, and pointer-cancel handling. Detection and matching modules are included in the offline core cache.

## Known Issues

- The whole grade grid rerenders on every grade; this may be slow for 35–40 students.
- Every page is held as a full-size canvas (roughly 10 MB each), creating memory risk on iPads and Chromebooks.
- Red-region detection proposes areas rather than recognizing answer text. Joined or split regions can require teacher adjustment; a split-box tool is deferred.
- Matching node labels use L1/R1 numbering; letters/numbers OCR is out of scope. Uncertain matching results require teacher review.
- Automatic grading for other answer types is not included.
- Saved-session identity still uses the scan fingerprint. Page-identity rekeying for changed scans is deferred.
- Real-copier alignment has not yet been tested.
- Detection ordering is row-major; column-major worksheets need Renumber/reorder.

## Next Steps

1. Run a real copier alignment test with a photocopy (see README).
2. Evaluate proposal quality and matching review with representative classroom scans.
3. Reduce rerendering and page-canvas memory use.
4. Extend answer-type graders and consider reusable templates or multi-page tests.
5. Revisit split-box editing and page-identity rekeying after classroom feedback.
