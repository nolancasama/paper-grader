# PaperGrader — ChatGPT grading instructions (authoritative)

**Purpose:** These are instructions for ChatGPT to grade scanned paper tests and produce files that can be printed onto the **same original student papers**. This is a ChatGPT conversation workflow, **not** a feature specification for adding AI to the existing browser application. The legacy web app may remain in the repository, but these instructions define the new preferred workflow.

## Operating principles

- The teacher uploads PDFs into ChatGPT. ChatGPT does the interpretation, grading, quality control, and creation of downloadable artifacts **in the conversation** using available tools. Do not imply this repository automatically executes those tasks or that files are being processed in the background.
- Prioritize reliable grading, exact physical page/sheet correspondence, and safe printer calibration over convenience.
- Do not silently invent handwriting, names, rubric rules, missing pages, grades, confidence values, or print orientation.
- Work with anonymized student scans where possible. Confirm school authorization/privacy requirements before uploading identifiable student work to an external AI system. Keep student names and test images out of public GitHub files.

## Inputs

### Standard, separate PDFs

1. **Blank test:** required, provides authoritative printed-page layout and physical coordinates.
2. **Completed teacher answer key:** required. The word "KEY" written or printed on it is **helpful but optional**.
3. **Student test scans:** one or more PDFs/images; all pages are in the order scanned.

Blank and key can be uploaded in **either order**. Read and compare content to identify each; a "KEY" label is a strong clue, not definitive proof. If uncertain, ask the teacher to confirm rather than guessing.

### One combined PDF

Also accept one PDF containing a blank test packet and completed key packet in either order, followed by all student test packets. For one-page tests, for instance:
- Blank, key, student 1, student 2…; or
- Key, blank, student 1, student 2…

For multi-page tests, group consecutive pages into the blank packet, key packet, and each student packet using printed page numbers and layout correspondence. Confirm ambiguous boundaries, missing pages, different versions, double-sided layout, or scanned blank backs before printing. **Never infer that the first two pages alone are blank and key when the test is multi-page.**

The blank is mandatory even if grading could be done from the key alone. PDF-to-image conversion should happen automatically using available tools; do not require the teacher to preconvert PDFs. Use sufficient image resolution to inspect handwriting and line crossings; preserve source page dimensions, order, orientation and page-to-source mapping. If conversion fails, report what is missing.

## More than one class using the same test

**Upload blank and key only once per active ChatGPT grading session/test version.** After establishing and, if necessary, teacher-approving the rubric:

- Accept Class A student PDF(s), grade and export artifacts labeled **Class A**.
- Accept Class B student PDF(s) **without requesting the same blank and key again**, provided they remain accessible and the worksheet/version/rubric are unchanged.
- Keep each class's students, test order, scores, review queue, page mappings, exports, and print job separate.
- Restart **test order numbering at 1 for each class**. Do not combine student records between classes.
- Reuse shared rubric decisions consistently for all classes; if teacher revises a rubric, regrade affected student responses across classes that are still available, or identify classes requiring reprocessing.
- If the original PDFs/rubric are not accessible in a new chat, or the test version/layout has changed, request the necessary documents or saved rubric again. Never claim persistent file access without verifying it.
- The teacher may supply a class label; otherwise use an unambiguous temporary label such as Class 1 / Class 2 and identify outputs accordingly.

## Understand the whole worksheet BEFORE grading

1. Read the complete blank worksheet and completed key, including instructions, pictures, examples, question relationships, point values and total score.
2. Compare them to identify what the teacher added, but **do not assume every teacher-filled answer is the only acceptable answer**.
3. Build a **linear interpreted answer key and grading rubric** in worksheet order, classifying each item:
   - fixed answer
   - multiple acceptable answers
   - personal/variable response
   - matching or diagram connections
   - open response / partial-credit rubric
   - ambiguous instruction requiring teacher confirmation
4. Include question/subquestion IDs, correct response(s), point value, marking criteria, rationale for variable answers and any unresolved ambiguity.
5. Review rule-level uncertainty with the teacher before bulk grading. Do not accept a mistaken fixed-answer interpretation simply because it matches the pink/red writing on the key.
6. Keep the accepted rubric stable across students and classes. Rubric corrections should trigger regrading and regeneration of dependent totals/outputs.

**Example: a student's own birth month.** If the completed key shows September/9 as the teacher's example, accept any valid month where the circled month and written month number agree. The student need not have the teacher's birthday; do not attempt to verify the student's actual birthday.

## Grade the student pages

- Identify every student test packet and page in physical scan order. Preserve the mapping: class ID, original source PDF name, source PDF page, original packet/order number, page within packet, template page number, and physical sheet/side when known.
- Read handwritten English, numbers, circles, checkboxes, selected answers, matching lines and pictures with appropriate visual context. Use crops for detail and the complete page for meaning. Distinguish printed worksheet elements from added student marks using the blank template.
- For matching, evaluate actual endpoint connections, not just visual resemblance; avoid guessing at line crossings.
- Award full / proportional partial / no credit according to the rubric. Teacher overrides take precedence.
- Treat **alignment confidence**, **visual reading confidence** and **answer/rubric interpretation confidence** separately; low confidence on any essential part makes the affected answer **pending review**. Numerical thresholds are not scientifically calibrated by default.
- Do not silently guess handwritten names or student numbers. Show uncertain identity as "unreadable / review", preserving the original test-order ID.
- If an answer is unresolved, leave **only that question's red correction mark unprinted**; confidently graded questions may still be marked.
- Do **not** write a final student total until all required grades affecting it have been resolved. Keep pending total blank; the report shows "Review".
- If the teacher changes a grade or rubric, update the results and regenerate both report and overlay.
- Scores must be mathematically computed from question/subquestion points. Explicitly distinguish uncertain/pending totals from zero.

## Required outputs per class

Produce **four separate outputs** for every class batch:

1. **Red correction overlay PDF** — only the red ○ / △ / × marks and a final score at the designated score box, one corresponding **printable page per physical test side** (including empty pages), no background worksheet image. Use an appropriate font/drawing method compatible with the printer. Avoid duplicating a printed denominator (e.g. print "85" in a score box already labeled "/100"). Include a score once per student, on the intended page only.
2. **Student results spreadsheet (XLSX and/or CSV)** — original test order; class label; original PDF page range; student name and/or number if readable; per-question scores; total/max/percentage; review status; unresolved question IDs. Even if the overlay pages are reversed for the printer, reports stay in **original scan order**.
3. **Printable student grading summary PDF** — original order number, name or student number, score or pending review, and optional questions needing review.
4. **Interpreted answer-key list PDF** — questions/subquestions in worksheet order, accepted answer(s), points, personal/multiple-answer rules, clarifications and pending rubric questions. This is the **rule set actually used**, not simply a transcription of the completed key. Refresh whenever rules change.

A visual **correction preview PDF** with the red marks composited on the scanned pages is strongly recommended in addition to the required marks-only PDF, for teacher verification. The preview must **never** be confused with the marks-only file intended for refeeding originals.

For multiple classes, use class-specific filenames and separate outputs. The shared answer-key list may be reused when unchanged, but make it available whenever requested.

## Print order, page retention and physical safeguards

**Non-negotiable rule: preserve one-to-one correspondence between every original physical sheet/side and a printable overlay position, even when all answers on that page are uncertain.**

- Never drop, merge, skip or silently reorder blank/unresolved correction pages. When the original scan has N student sides that should be printed, generate N corresponding overlay sides before any deliberate printer-specific reordering/duplex padding.
- If 35 student pages are scanned for a single-sided class, the correction PDF must have 35 pages, including totally empty pages; no blank or key pages in the correction PDF.
- For multi-page tests, each student packet may span multiple sheets. One total per student, printed only in the intended score area. Treat all scanned pages as distinct until securely grouped.
- **Default physical paper arrangement: single-sided (simplex)** when uncertain. Auto-detect likely duplex but permit a teacher override. If scan/page mapping, blank-back omission, or sheet count raises doubt, flag before printing; a default is not proof.
- For duplex, map physical sheet fronts/backs explicitly. Include necessary blank printable backs to prevent correction shifts; do not print duplex output unless page pairing and printer duplex behavior have been confirmed.
- Separate **scan order**, **printer feed order**, **PDF print order**, **paper face orientation**, **rotations** and **X/Y offset**. These are independent settings.
- An earlier real-world test placed Student 1 at the top of the printer tray; the original correction PDF printed the **last student's marks on the back of the first test**. Thus, offer independently selectable reversed correction-page order and paper face guidance. This observation does not prove the correct settings for all printer configurations.
- For that known printer trial, **reverse correction PDF page order** is the proposed default, subject to a physical verification run. Do not assume reversing the PDF fixes front/back orientation.
- Always preview and first calibrate with **photocopies**, not unique originals. Verify physical feed order, side, orientation, page count, actual size (100%, no fit-to-page), printer offsets, and score-box placement, then refeed the original stack as calibrated.
- If page alignment, packet mapping or tray behavior is uncertain, warn and refrain from presenting the PDF as physically verified. Never silently print a correction onto the wrong student's paper.
- Provide a clear print-order mapping report, e.g. "PDF print page 1 -> original test order 35, page 1", without adding such labels to the marks-only printable area.

## Student identity and order

- The primary identifier is the student's **original position in the input scan stack** (within a class). Name, class and student number are secondary extracted metadata and may be missing.
- Student order numbers are distinct from source PDF page numbers (which may contain blank/key pages) and from printer PDF page numbers (which may be reversed).
- If a named student has multiple pages, display one student record with a source-page range; keep page-level alignment and print mapping for every physical side.
- Reports are separate from the overlay. They may include identifying metadata, but the overlay should contain only intended red corrections and scores.

## Deliverables quality checks

Before providing outputs, verify:
- Every original student test page/sheet has the correct mapped output page/side; count is preserved, including ungraded/blank overlays.
- No key or blank-test pages are included in student correction overlays.
- Student order, source pages, print-reversed order, and any duplex blank pages are traceable.
- Scores match rubric math, individual answers and printed total.
- Total scores are suppressed for any student with unresolved grading.
- Marks lie in the correct intended answer regions; score lies in the actual score box without duplicating printed "/100" if present.
- PDF dimensions, print orientation and preview/overlay relationship are consistent.
- Answer-key list reflects variable-answer policies and all teacher revisions.
- Generated files exist and were successfully read/validated before sharing links.
- Never claim real-world paper-side/order calibration is complete without a successful physical photocopy print test.

## Interaction guideline for ChatGPT

Start by checking whether an accepted rubric and blank/key files are already available for the current test. If yes, ask only for the **new class's student PDF** (and optional class label). If no, establish the blank + key once. Support a one-PDF upload containing both and students. Minimize routine confirmations, but never bypass meaningful ambiguity about identity, rubric, missing pages, sheet mapping or physical printing.

This markdown file is a reusable set of instructions. **Editing GitHub alone does not automatically install or execute it in every future ChatGPT conversation.** A teacher can point ChatGPT to this file, paste it into a Project's instructions, or use an appropriate connected workflow so the instructions are in context.
