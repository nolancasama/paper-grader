# ChatGPT-based PaperGrader — Agreed Product Specification

**Status:** Agreed design requirements; **not implemented or fully validated**  
**Last updated:** 2026-10-22  
**Repository:** `nolancasama/paper-grader`  
**Scope:** ChatGPT-assisted or ChatGPT-first grading workflow with physically printable corrections. This is a future workflow proposal, separate from the existing offline/local-first implementation described in `README.md`.

## Goal

A teacher uploads a blank worksheet, a completed teacher answer key, and scanned student work as PDFs. The system understands the *meaning* of each question, grades consistently, flags uncertainty, produces a results report, and generates accurately positioned **red-only corrections** for printing onto the **same original physical student papers**, without losing sheet order.

**Core principle:** Understand the question → interpret the key → establish the rubric → grade students → review uncertainty → print corrections.

## 1. Supported input workflows

### Separate files

1. Upload the **blank/original unanswered test PDF** (**required**).
2. Upload the **completed teacher answer key PDF** (**required**).
3. Upload the scanned student tests as one multipage PDF or several PDFs.

### One combined PDF

Support a single PDF in this exact logical order:

1. All blank-test pages, in worksheet order.
2. All completed-key pages, in the same worksheet order.
3. All students' test pages, grouped by student and in physical scan order.

For an `N`-page worksheet: blank pages 1–N; key pages N+1–2N; student 1's N pages; student 2's N pages; etc. Determine or confirm N before processing. Detect missing, duplicated, rotated, unexpected, or misordered pages; don't silently guess a student/page mapping.

**The blank test remains mandatory**, even if AI might be able to infer the worksheet from the key alone.

### Automatic scan conversion

Accept image-based/scanned PDFs without asking the teacher to convert them. Render PDF pages to images internally at sufficient resolution, preserve source page indices, and inspect high-resolution crops where necessary. Split oversized batches when processing constraints require it, without changing the physical page mapping.

## 2. Understand the test before interpreting the key

Read the entire **blank test** (instructions, printed text, pictures, directions, answer spaces, relationships between questions) and the **completed key** before grading any students.

Distinguish:
- fixed, objectively correct answers;
- several acceptable answers;
- personal responses and free choices;
- an example response written by the teacher rather than the only correct answer;
- matching/connection questions (including intersecting lines);
- written English, numbers, circles, checkboxes, short responses, and open-ended work.

**Never blindly treat the teacher's completed response as the sole permitted answer.**

Example from the initial worksheet: in Question 4, the key uses September/9 as an example of a *student's birth month*. A student choosing April and writing 4 should receive credit when the chosen month and written number agree. September is not the sole correct response.

Generate a **per-question grading rubric** with answer criteria, point values, permissible alternatives, and treatment of partial credit. Apply the same rubric consistently to the class. Surface unclear instructions or ambiguous rubric decisions for teacher approval before applying them. Teacher rubric edits must allow regrading every affected student.

## 3. Grading and review

- Align every student page to its corresponding blank-template page before placing marks.
- Recognize handwritten answers, selected options, and drawn matching lines; assess whether the response meets the rubric, not simply whether the pixels resemble the key.
- Support ○ (correct), △ (partial), and × (incorrect), with configurable partial-credit rules. Award proportional credit for reliably resolved matching connections.
- Track uncertainty separately for **page alignment**, **answer recognition**, and **answer interpretation**. Confidence estimates are not proof of correctness; calibrate thresholds against teacher-marked examples.
- Never silently guess ambiguous handwriting, line crossings, question mapping, or scores.
- Show uncertain answers to the teacher; allow corrections and regrade affected scores.
- Confirmed answers on a partly unresolved test can still be marked. Leave uncertain answer locations unmarked.
- If any score-contributing item is unresolved, withhold the final total score rather than printing a potentially incorrect number.
- Produce a per-student results report, per-question breakdown, and CSV/spreadsheet export.

## 4. Correction overlays printed onto the original papers

Produce two outputs:

1. **Marks-only correction PDF**: transparent/otherwise unprinted background, with only the red ○ / △ / × corrections and confirmed totals. Do **not** reprint the worksheet text, pictures, or students' answers.
2. **Preview PDF**: worksheet scan with the proposed marks overlaid for visual review.

Requirements:
- Place each correction in its designated answer area on the actual paper.
- Identify and use the worksheet's **score box**, and write each student's **one overall total** in the appropriate place. Respect an already printed `/100` rather than duplicating it when applicable.
- For a multipage test, calculate a **single test total**, printed once in its designated location (regardless of which page contains the score box).
- Keep printer paper-size and scale correct, with **actual-size/100%** printing and calibrated X/Y offsets, rotation, and sheet orientation as necessary.
- Provide a calibration test before using the originals.
- Support common paper sizes such as A4, B4, etc., determined or confirmed from the source.

### Non-negotiable page-slot preservation

There must be a **one-to-one mapping between each physical student page/side to be printed and its overlay slot**. Never remove an overlay slot merely because grading is incomplete.

- Keep all students in their original *logical* scan order and preserve stable student identifiers/page indices.
- If just one answer is unresolved, print all other confirmed correction marks on that student's page and keep the score box empty.
- If no correction is safe, include a completely **blank overlay page** in that same position.
- Do not omit low-confidence student papers, compact the PDF, or cause later correction marks to move onto someone else's test.
- Missing/misordered student pages or uncertain mapping are different from uncertain grading: **hold physical printing until sheet mapping is resolved**, instead of proceeding with a shifted stack.
- The output PDF page order may be **reversed or otherwise transformed for the calibrated printer feed**, while retaining a verified mapping back to original student pages. The desired teacher experience is to load **Student 1 on top in natural order**, without manually reversing the student stack.

### Lessons from the first physical print trial

The initial three-student trial put the **last student's corrections on the back of the first student's paper** when Student 1 was at the top of the tray. This indicates two *separate* parameters to calibrate:
- **PDF correction page order versus physical sheet feed order** (a reversed PDF was proposed);
- **paper face orientation**, so marks land on the printed front rather than the back.

A reversed PDF by itself does **not** solve face orientation. The revised orientation/order must be physically verified with photocopies before classroom printing. Do not generalize a calibration result to another printer/tray without checking.

## 5. Multipage and duplex tests

Support 1-page and N-page worksheets, including questions spanning pages, missing-page detection, and template-to-student-page matching.

Two paper modes:
- **Single-sided (simplex): the default fallback whenever sidedness cannot be confidently determined.**
- **Double-sided (duplex): selectable by the teacher, or inferred and confirmed when the scan and worksheet supply reliable clues.**

A PDF alone does not always prove the physical paper arrangement: some scanners omit blank backs. For duplex, preserve front/back pairings **and insert blank overlay sides where needed** to avoid an off-by-one pairing or printing on the next student's paper. Duplex needs its own calibration.

Remember confirmed printer settings (feed order, face orientation, simplex/duplex, paper size, offsets, and rotation) as a reusable **printer profile**. Never interpret a guessed mode as verified; warn and seek confirmation if document mapping conflicts with the single-sided default.

## 6. Safety, privacy, and operational constraints

- Teacher remains the final authority; grades and printer alignment require a real classroom validation phase.
- Where student data is sent to an AI service, confirm school privacy/permission requirements. Prefer anonymized sample tests during testing; do not require unnecessary student identifiers.
- ChatGPT conversation grading and API-integrated grading are **different implementation options**; direct ChatGPT file processing does not automatically mean the existing browser app uses the same model or has the same limits. API costs/limits and the browser app's offline requirements need explicit architecture decisions.
- Preserve the existing local/offline solution unless explicitly replaced. This specification describes **desired behavior**, not a claim of completed implementation.

## 7. Acceptance tests

Before class-wide deployment, verify with photocopies and teacher-marked samples:

1. A combined scanned PDF with one blank, one key, and multiple student tests can be parsed into the correct roles and page groups.
2. A personal-response question such as the birth-month example accepts every valid response, not only the teacher's example.
3. A rubric change regrades all affected student papers consistently.
4. Ambiguous handwriting or intersecting lines flag review, never invent marks.
5. A student with unresolved items retains confirmed marks but **does not receive an unverified final total**.
6. A fully unresolved student still gets a **blank overlay page** at the correct physical slot.
7. Multipage tests get corrections on every applicable page and exactly one overall score.
8. Missing pages, duplicated pages, or incorrect physical-sheet mapping block printing rather than shift others' marks.
9. The teacher can load **Student 1 at the top** without reversing the stack, and all pages receive the corresponding student's marks.
10. Both page order and printed side are physically verified; test simplex default and duplex page pairing separately.
11. The score prints inside the designated score box; X/Y offsets and actual-size printing work on the real printer.

## 8. Implementation status / decisions pending

**Agreed requirements above are locked in as the target product behavior.** They have **not** been implemented in the GitHub application by the act of saving this file.

Open implementation choices:
- ChatGPT-only file-processing workflow, ChatGPT/API inside PaperGrader, or a hybrid;
- exact printer-profile UX, calibration process, and scan-to-overlay transform;
- batch limits, failure recovery, confidence calibration, and image-processing strategy;
- privacy approvals for any real student work uploaded to a remote model.

The existing `README.md` remains authoritative for **what is already implemented**.
