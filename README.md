# PaperGrader

A browser-based classroom tool for grading one-page paper tests and printing red correction marks back onto the original student sheets.

## Current implementation

The current app already supports:

- loading scanned PDFs/images
- editable answer areas
- red-key answer-area proposals
- linear answer-key sidebar
- name and score areas
- manual ○ / △ / × grading
- a local matching-lines grader with proportional credit and review
- results and CSV export
- correction-overlay printing with paper size, X/Y offsets, reverse order, rotation, and alignment test
- an automatically generated offline `file://` build for locked-down school PCs

Some question types still require teacher grading. Handwriting recognition and paid AI graders are not enabled by default.

## Frozen target workflow

The product direction is now:

### 1. Test setup — separate from student scans

Load:

1. **blank original test**
2. **completed teacher answer key**

PaperGrader aligns the completed key to the blank test, subtracts the shared printed worksheet content, and proposes answer regions from the teacher-added marks.

The teacher reviews/edits the proposed regions and the linear answer key, then optionally marks name and final-score areas.

Red ink remains useful but is optional when a blank original is available.

### 2. Student grading

Load the student papers separately, normally as one multipage PDF with one student sheet per page.

Every student page is aligned to the blank original before crops are extracted. Graders then use local/deterministic methods first and send only genuinely uncertain small crops to future AI graders if AI is configured.

Low-confidence answers are never silently guessed.

### 3. Physical correction printing

Re-feed the same physical student papers and print only ○ / △ / × plus the final score.

If an answer remains unresolved, that answer is left unmarked and the student's final score is withheld.

An optional future second scan can verify the physical print-stack order and detect swapped/missing/reversed/off-by-one sheets before marks are printed.

## Alignment

The blank original is the canonical template.

Default alignment should use page geometry and stable printed features/template matching to correct ordinary scan shift, rotation, scale, crop, and reasonable skew/perspective.

Special registration marks are **not required** and are currently back-burner.

Questionable pages should get a confidence warning and optional translucent overlay/blink review rather than being silently accepted.

## Matching questions

Matching is treated as one region.

The grading ladder is:

1. compare the normalized overall ink web to the key web
2. if clearly identical, accept as correct
3. otherwise infer endpoint connections and trace trajectories locally
4. ambiguous crossings are not guessed
5. future AI may inspect only the small matching crop
6. unresolved cases go to teacher review

When connections are resolved, PaperGrader can identify individual wrong pairings and award proportional credit.

## Confidence

There is no single universal confidence score.

Alignment, recognition/extraction, and interpretation have separate confidence values; the weakest relevant stage governs whether an answer may be auto-graded.

Initial conservative target:

- about **0.99+**: eligible for automatic grading
- about **0.95–0.99**: try another reliable method / configured fallback
- below about **0.95**: teacher review

These values must be calibrated using real classroom scans. Precision is more important than maximizing automatic coverage.

## AI philosophy and cost

PaperGrader is designed to work without AI and to keep future AI usage small.

Preferred ladder:

`local CV/rules -> local OCR -> AI only for uncertain answer crops -> teacher review`

When AI is enabled, the planned usage meter should show calls, answers sent, model(s), token usage when available, cost, escalation rate, and unresolved answers. A configurable spend cap should stop further paid calls and send remaining items to teacher review.

## Offline build

The offline build lives in `offline/` and is generated from the web sources with:

```
npm run build:offline
```

It is designed for direct `file://` use on restricted school PCs without requiring installation.

## Privacy

Local alignment, subtraction, detection, matching, scoring, and printing stay in the browser. Student scans should not be uploaded by default.

If future AI grading is configured, only the minimum answer crop required for that grading call should be sent.

## First real-world copier test

Use photocopies rather than the only copy of a student's test.

The most important physical measurements are:

- whether scan/template alignment remains stable from page to page
- whether printer output has a consistent X/Y offset
- whether tray orientation/order is consistent
- whether correction marks land accurately after re-feeding
