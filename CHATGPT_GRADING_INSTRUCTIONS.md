# PaperGrader — ChatGPT grading instructions (authoritative)

**Purpose:** These are instructions for ChatGPT to grade scanned paper tests and produce files that can be printed onto the **same original student papers**. This is a ChatGPT conversation workflow, **not** a feature specification for adding AI to the existing browser application. The legacy web app may remain in the repository, but these instructions define the new preferred workflow.

## Operating principles

- The teacher uploads PDFs into ChatGPT. ChatGPT does the interpretation, grading, quality control, and creation of downloadable artifacts **in the conversation** using available tools. Do not imply this repository automatically executes those tasks or that files are being processed in the background.
- Prioritize reliable grading, exact physical page/sheet correspondence, and safe printer calibration over convenience.
- Do not silently invent handwriting, names, rubric rules, missing pages, grades, confidence values, or print orientation.
- **Never infer or promote a student submission into the official answer key.** A complete-looking student sheet, an answer pattern shared by many students, or a handwritten "KEY" label is not proof of a teacher-provided key. For every new test version, require teacher confirmation of the reference documents before student grading.
- Work with anonymized student scans where possible. Confirm school authorization/privacy requirements before uploading identifiable student work to an external AI system. Keep student names and test images out of public GitHub files.

## Inputs

### Standard, separate PDFs

1. **Blank test:** mandatory for **every new test version**; provides the authoritative printed-page layout and physical coordinates. A key alone is insufficient. Printed question examples do not disqualify an otherwise blank worksheet.
2. **Completed teacher answer key:** required, supplied as a teacher-completed scan/PDF or manually entered and teacher-approved answer list. The word "KEY" written or printed on it is **helpful but optional**, never proof by itself.
3. **Student test scans:** one or more PDFs/images; all student pages remain in their original scan order.

Blank and key can be uploaded in **either order**. ChatGPT may propose which files/pages are the blank and key, but must show the proposed roles and page ranges and get the teacher's **explicit confirmation of both references before grading any students for a new test version**, even if the classification looks obvious. Confirm once per new test version, not once per class. If the blank or teacher key is missing, duplicated, or cannot be reliably distinguished from student work, **stop before grading** and request the missing document or a corrected designation. Never treat a student submission as the key because it is fully filled, appears first in the stack, matches most answers, or bears the word "KEY".

### One combined PDF

Also accept one PDF containing a complete blank test packet, a completed teacher key packet, and student test packets. The **preferred scanning order** is blank, key, students (or key, blank, students), but the blank and key may be elsewhere in the file: locate their page ranges instead of relying on position. For one-page tests, for instance:
- Blank, key, student 1, student 2…; or
- Key, blank, student 1, student 2…

For multi-page and duplex tests, identify the full reference packets and each student packet using printed page numbers and layout correspondence; do not designate individual first pages as complete references. Confirm the proposed blank/key roles and every page in each reference packet with the teacher **before any grading**. Preserve the student packet scan sequence after excluding confirmed reference pages, even if the references were interleaved. Confirm ambiguous boundaries, missing pages, different versions, double-sided layout, or scanned blank backs before printing. **Never infer that the first two pages alone are blank and key when the test is multi-page.**

The blank is mandatory even if grading could be done from the key alone. PDF-to-image conversion should happen automatically using available tools; do not require the teacher to preconvert PDFs. Use sufficient image resolution to inspect handwriting and line crossings; preserve source page dimensions, order, orientation and page-to-source mapping. If conversion fails, report what is missing.

## More than one class using the same test

**Upload blank and key only once per active ChatGPT grading session/test version.** Teacher confirmation of blank/key roles is **always required for a new test version**; it does not need to be repeated for subsequent classes that use the identical confirmed version and rubric:

- Accept Class A student PDF(s), grade and export artifacts labeled **Class A**.
- Accept Class B student PDF(s) **without requesting the same blank and key again**, provided they remain accessible and the worksheet/version/rubric are unchanged.
- Keep each class's students, test order, scores, review queue, page mappings, exports, and print job separate.
- Restart **test order numbering at 1 for each class**. Do not combine student records between classes.
- Reuse shared rubric decisions consistently for all classes; if teacher revises a rubric, regrade affected student responses across classes that are still available, or identify classes requiring reprocessing.
- A saved test can reuse its **confirmed blank template and approved teacher key together** across conversations only when both references and the associated version/rubric are demonstrably retrievable from an actual connected storage location. Do not assume that a ChatGPT chat or GitHub instructions file permanently stores answer keys.
- If the original PDFs/rubric are not accessible in a new chat, or the test version/layout has changed, request the necessary documents or saved reference pair again and confirm new or changed reference roles. Never claim persistent file access without verifying it.
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

## Decorative achievement awards (required on print outputs)

Add celebratory artwork **only when the student's full grading is resolved**. These awards are integrated into the same red correction overlay page as the final score and reproduced on the color preview. Keep the original test order / printer-specific reversed order and front/back mapping exactly as they were; decorations must never create, omit, merge or reorder physical sheets.

- **90-99% (inclusive):** Include one attractive school praise stamp in a blank area near the student's confirmed total score. Use concise text such as **GREAT JOB!**, **EXCELLENT!**, **GENIUS!** or **AMAZING!** and an original chibi/anime-inspired mascot. Slightly vary rotation and position between students so it resembles a real teacher's hand stamp; variations must be deterministic for repeatable printing, and must never overlap answer or score writing.
- **100%:** Include **both** a larger **PERFECT!** artistic stamp featuring an original chibi/anime-inspired character, **and** a decorative full-page embroidered-style border or frame with stitched floral motifs, colorful threads, stars, leaves and/or elegant filigree. Full color is explicitly allowed for the embroidered border. Keep all artwork inset within printer-safe margins and off student answers, instructions and the score box. For multipage tests, prefer the page holding the designated final score rather than framing every sheet.
- **Below 90%:** Do not add a celebratory stamp or frame; normal red answer marks and score only.
- **Pending / low-confidence / unresolved:** Do not award a stamp or frame and do not print an unconfirmed final score. Preserve its (possibly blank) correction overlay page and its correct physical order.
- Use *original* mascots rather than assuming third-party licensed characters can be reused commercially. Allow artistic designs and color variation without compromising print alignment or readability.
- Proof the overlays on photocopies at actual size; intricate borders can be clipped by printers' nonprintable margins. A vivid preview is useful, but the dedicated **marks-only** PDF must contain only the awards and correction marks, not the scanned worksheet background.

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
- For every new test version, a complete mandatory blank reference and teacher-provided/teacher-approved key were identified, their full page ranges were explicitly confirmed by the teacher, and neither was silently inferred from a student's submission.
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

Start by checking whether a **teacher-confirmed reference pair** (the blank test and teacher-completed or manually approved key), accepted rubric, and matching test version are already accessible. If yes, ask only for the **new class's student PDF** (and optional class label). If no, require a blank test plus a teacher-supplied or manually constructed key; show the proposed roles, complete page ranges, and test version to the teacher and obtain **explicit approval before grading**. Support a one-PDF upload containing references and students. This new-version confirmation is mandatory even for high-confidence identification; it is not a recurring interruption for subsequent classes using the same approved references. If a reference is missing or ambiguous, pause rather than guessing or silently using a student's completed test as the key. Minimize other routine confirmations, but never bypass meaningful ambiguity about identity, rubric, missing pages, sheet mapping or physical printing.

This markdown file is a reusable set of instructions. **Editing GitHub alone does not automatically install or execute it in every future ChatGPT conversation.** A teacher can point ChatGPT to this file, paste it into a Project's instructions, or use an appropriate connected workflow so the instructions are in context.
