# PaperGrader — ChatGPT grading instructions (authoritative)

**Purpose:** These are instructions for ChatGPT to grade scanned paper tests and produce files that can be printed onto the **same original student papers**. This is a ChatGPT conversation workflow, **not** a feature specification for adding AI to the existing browser application. The legacy web app may remain in the repository, but these instructions define the new preferred workflow.

## Operating principles

- The teacher uploads PDFs into ChatGPT. **ChatGPT must personally inspect and judge every student response using its visual understanding of the scanned worksheet**, rather than handing grading judgments to OCR, pixel-matching, or a script. ChatGPT also performs interpretation, quality control, and creation of downloadable artifacts **in the conversation** using available tools. Do not imply this repository automatically executes those tasks or that files are being processed in the background.
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

## Mandatory method: ChatGPT grades visually, not automated OCR

**Teacher's explicit requirement (after the USB-0011 grading failure): ChatGPT itself must visually read and assess the answers on every student's paper. Do not delegate scoring to an OCR engine or automated image-difference algorithm.** This is a mandatory workflow rule, not a preference or optional enhancement.

- Render each scanned paper at sufficient resolution and **inspect its actual image**. For each student and every assessed question, visually determine what was written, circled, connected or selected, then judge it against the interpreted, teacher-confirmed rubric. Use close-up crops and enlarged images when handwriting, lines or answer endpoints are difficult to see. Preserve each original page's physical orientation and order for printing even if images are rotated temporarily for reading.
- **Never assign grades, marks or final totals using Tesseract/OCR digit recognition, automatic circle detection, thresholded pixel counts, image differencing, computer-vision line detection, or programmatic answer classification.** These techniques previously misread visibly correct handwritten 3, 1, 2 answers as blanks and wrongly deducted points. Even if such techniques are used as non-authoritative navigation aids, their outputs must not become grades without an independent, direct visual review of **every** answer.
- **Python/code is for mechanics after human-readable visual decisions:** rasterizing/cropping PDFs; tracking source order and orientation; page alignment and printer offsets; storing already visually verified per-question judgments; arithmetic from those verified judgments; generating ○/△/× overlays, decorations, rosters, CSV/XLSX and PDFs; and validating page mappings. Never allow the PDF-production code to infer or silently overwrite an answer or its correctness.
- Record a **per-student, per-question visual assessment** (observed answer, rubric comparison, awarded points, and confidence/pending flag) before calculating that student's total. An empty OCR result is **never** evidence of a blank or wrong student answer. A blank or incorrect answer must be established by looking at the student's actual page.
- For matching tasks, trace each student's line to its actual source and destination by sight, even when lines cross, curve, are redrawn or go beyond the usual region. For multiple choice, visually inspect each handwritten number/circle; do not infer correctness from common answer patterns.
- **Quality control before generating print-ready files:** review the visual decisions against the original student scans, check that the same item is treated consistently across the batch, flag suspicious class-wide error clusters (especially many apparent blanks on an easy item), and verify every printed score against the visually determined item scores. Perform a final visually grounded spot-check of the composed overlays against their corresponding source sheets for orientation, answer positions and score placement. Never substitute a statistical spot-check for the initial required visual grading of all answers.
- **If a large batch cannot be fully and reliably inspected visually, do not switch to automated grading to finish it.** Grade only the papers/questions actually visually assessed, mark the rest pending **in teacher-facing reports only**, suppress unverified scores and awards, and explicitly disclose incomplete grading. Do not label uninspected work as graded, and never describe an OCR-derived result as visually verified.
- The teacher's grades, corrections, authorized overrides, and explicit rubric judgments take precedence. If grading is disputed, re-open the original scan and re-examine it visually before altering the report and correction PDF.

## Grade the student pages

- Identify every student test packet and page in physical scan order. Preserve the mapping: class ID, original source PDF name, source PDF page, original packet/order number, page within packet, template page number, and physical sheet/side when known.
- Read handwritten English, numbers, circles, checkboxes, selected answers, matching lines and pictures with appropriate visual context. Use crops for detail and the complete page for meaning. Distinguish printed worksheet elements from added student marks using the blank template.
- For matching, evaluate actual endpoint connections, not just visual resemblance; avoid guessing at line crossings.
- Award full / proportional partial / no credit according to the rubric. Teacher overrides take precedence.
- Treat **alignment confidence**, **visual reading confidence** and **answer/rubric interpretation confidence** separately; low confidence on any essential part makes the affected answer **pending review**. Numerical thresholds are not scientifically calibrated by default.
- Do not silently guess handwritten names or student numbers. Show uncertain identity as "unreadable / review", preserving the original test-order ID.
- If an answer is unresolved, leave **only that question's red correction mark unprinted**; confidently graded questions may still be marked.
- Do **not** write a final student total until all required grades affecting it have been resolved. Keep the pending total **completely blank on the physical-test correction overlay**; put the status **"Review" / "Pending" only in the separate roster, results spreadsheet, grading summary and teacher review list.**
- **NEVER print the word "REVIEW", "PENDING", a question mark, or any similar review/status label on a student test**, including in a red-only overlay or its superimposed preview. Pending answers receive no correction mark; confidently graded answers can still receive ○ / △ / ×. If the whole test is unresolved, its correction overlay may be entirely blank, but its page must still be present to maintain physical order.
- If the teacher changes a grade or rubric, update the results and regenerate both report and overlay.
- Scores must be mathematically computed **only from ChatGPT's previously recorded, visually verified question/subquestion judgments**. Explicitly distinguish uncertain/pending totals from zero; never convert a recognition error or unreadable answer into a zero.

## Required outputs per class

Produce **five separate outputs** for every class batch:

1. **Red correction overlay PDF** — only confirmed red ○ / △ / × marks, optional qualifying celebratory stamp/frame, and a **confirmed** final score at the designated score box, one corresponding **printable page per physical test side** (including empty pages), no background worksheet image. Use an appropriate font/drawing method compatible with the printer. Avoid duplicating a printed denominator (e.g. print "85" in a score box already labeled "/100"). Include a score once per student, on the intended page only. **Do not print REVIEW/PENDING/status text anywhere on original tests**, even when grading is incomplete.
2. **Student results spreadsheet (XLSX and/or CSV)** — original test order; class label; original PDF page range; student name and/or number if readable; per-question scores; total/max/percentage; review status; unresolved question IDs. Overlay PDFs and reports both stay in **original scan order** by default. An explicitly teacher-selected printer-order override affects only the overlay file, never the reports.
3. **Printable student grading summary PDF** — original test order number, student name, student number, confirmed score or "Pending review", and optional questions needing review. Include a clear class title.
4. **Printable student score roster PDF (separate teacher-facing file)** — a compact, easy-to-print table with **one row for EVERY student**, in the **original scan/test order**, showing at minimum **test-order position**, **student name**, **student number (No.)**, and **confirmed total score / maximum score (e.g. 90/100)**. Include **class** when known and an optional separate **status** column. If a score is unresolved, do **not** present a guessed or provisional number as final: show **"Pending review"** in the roster score/status field. For an unreadable or missing name or number, write **"Unreadable" / "Not provided"**, not a guessed identity, and keep the position ID for traceability. Fit on a single page when feasible, using as many roster pages as necessary for a large class without tiny illegible text. Title the document clearly, e.g. "Class 2 — Student Scores", and name it with a "student_score_roster.pdf" suffix. **Never insert roster pages into either correction overlay PDF**, since doing so would shift the printed corrections onto the wrong physical tests.
5. **Interpreted answer-key list PDF** — questions/subquestions in worksheet order, accepted answer(s), points, personal/multiple-answer rules, clarifications and pending rubric questions. This is the **rule set actually used**, not simply a transcription of the completed key. Refresh whenever rules change.

A visual **correction preview PDF** with the red marks composited on the scanned pages is strongly recommended in addition to the required marks-only PDF, for teacher verification. The preview must **never** be confused with the marks-only file intended for refeeding originals.

For multiple classes, use class-specific filenames and separate outputs. The shared answer-key list may be reused when unchanged, but make it available whenever requested.

## Decorative achievement awards (required on print outputs)

Add celebratory artwork **only when the student's full grading is resolved**. These awards are integrated into the same red correction overlay page as the final score and reproduced on the color preview. Keep the normal-order overlay and exact front/back mapping intact (or an explicitly authorized, calibrated alternative); decorations must never create, omit, merge or reorder physical sheets.

- **90-99% (inclusive):** Include one attractive school praise stamp in a blank area near the student's confirmed total score. Use concise text such as **GREAT JOB!**, **EXCELLENT!**, **GENIUS!** or **AMAZING!** and an original chibi/anime-inspired mascot. Slightly vary rotation and position between students so it resembles a real teacher's hand stamp; variations must be deterministic for repeatable printing, and must never overlap answer or score writing.
- **100%:** Include **both** a larger **PERFECT!** artistic stamp featuring an original chibi/anime-inspired character, **and** a decorative full-page embroidered-style border or frame with stitched floral motifs, colorful threads, stars, leaves and/or elegant filigree. Full color is explicitly allowed for the embroidered border. Keep all artwork inset within printer-safe margins and off student answers, instructions and the score box. For multipage tests, prefer the page holding the designated final score rather than framing every sheet.
- **Mandatory decorative output verification, not just instructions:** The generator **must actually embed** a visible, finely detailed, multicolored embroidery-style margin border **and** illustrated cute-character PERFECT! stamp in both the marks-only correction PDF and the on-test preview for **every visually verified 100% student**. A plain rounded rectangle, several concentric lines, a text-only stamp, a placeholder, or omitting the artwork does **not** satisfy this requirement. The border should look like actual floral needlework, with delicate repeated motifs and botanical stitching as in the teacher's reference. If production of that artwork fails, do not silently deliver or call the PDF complete; report the failure and produce an explicitly labeled incomplete/non-print-ready version pending correction. Never add the artwork on an unverified/provisional 100%.
- **Per-student decoration audit:** Before delivery, create a visual checklist from the **verified** grades identifying every 90–99 and 100 student by original test-order position. Render and inspect **each** corresponding finished overlay page and superimposed preview page, checking that each eligible student actually has the right stamp, each 100 has embroidered margins, the artwork does not cover answers, and the orientation and page index match the original physical stack. Confirm that no ineligible or pending student has a stamp or border. Record any missing decoration as a delivery-blocking defect; do not merely assume the decoration code ran.
- **Cute character required on every achievement stamp:** Both 90–99 praise stamps and 100 PERFECT! stamps should feature a cheerful, original, cute anime-style **chibi character or adorable mascot**. Prefer expressive happy faces, rounded proportions, friendly celebratory poses, and school-appropriate designs. It can vary by student (e.g., chibi student, cat, rabbit, small fantasy creature). Integrate the character with the lettering so the result feels like a real illustrated teacher stamp, not plain text inside a circle. No licensed character reproductions are assumed.
- **Human hand-stamp placement (required):** Never place every stamp at exactly the same X/Y coordinate or angle. Introduce **small, student-specific, natural-looking variation** relative to a safe target area: e.g., shift left/right by approximately 2–6 mm, up/down by 1–4 mm, and rotate by roughly -7° to +7°, using both clockwise and counterclockwise angles across the batch. Slight, optional stamp-texture/ink-strength differences are fine if legibility remains high. Use a stable per-student/per-batch seed so the exact same correction PDF can be regenerated without artwork drifting between prints. **Constrain the jitter to the actual available blank area**: never cover student answers, printed questions, the score box, red grading marks, or other artwork; if necessary reduce variation or move the baseline stamp location. Respect original orientation (including upside-down physical pages) and normal-order mapping. Do not let natural-looking variation become misalignment.
- **Art direction for the perfect-score margin/frame — teacher-provided reference:** https://www.amazon.co.uk/ORIGACH-Embroidery-Patterns-Stabilizers-Beginners/dp/B0GGHSX1X4 . Use the *embroidery / stitched lace border* aesthetic as the primary visual reference, not a chunky red outline, thick cartoon border, cross-hatch grid, big repeated X marks, or a large distracting frame. Prefer intricate **delicate embroidered edging**: narrow lace-like repeating motifs, intertwined floral vines, tiny blossoms and leaves, small scallops, thread-stitch texture, botanical corners, and balanced negative space. Allow full multicolor embroidery threads (e.g., muted greens, lilac, coral, rose, pale gold, soft blue) with a coherent elegant palette rather than only red; reserve red chiefly for the grading marks. Render as ORIGINAL vector/print-resolution artwork inspired by the reference, not copied product artwork. If the exact reference listing artwork cannot be viewed, retain the URL and do not falsely claim an exact reproduction; ask for a screenshot only if an exact match is essential.
- **Frame integration and print constraints:** On 100% worksheets, arrange the decorative border *within the actual printer's verified printable area*; target a fine, narrow band, and dynamically simplify or interrupt it wherever the worksheet's printed header, name, score box, instructions or answers come close to the edges. No covering student work. Keep a clear area for the PERFECT! chibi stamp, which may be separate from the embroidery. Align the border to each ORIGINAL scan side and preserve its 0°/180° orientation and **normal-order** page index exactly. Reprint onto originals only after a 100%-scale calibration proof on photocopies.
- **Below 90%:** Do not add a celebratory stamp or frame; normal red answer marks and score only.
- **Pending / low-confidence / unresolved:** Do not award a stamp or frame and do not print an unconfirmed final score. Preserve its (possibly blank) correction overlay page and its correct physical order.
- Use *original* mascots rather than assuming third-party licensed characters can be reused commercially. Allow artistic designs and color variation without compromising print alignment or readability.
- Proof the overlays on photocopies at actual size; intricate borders can be clipped by printers' nonprintable margins. A vivid preview is useful, but the dedicated **marks-only** PDF must contain only the awards and correction marks, not the scanned worksheet background.

## Print order, page retention and physical safeguards

**Non-negotiable rule: preserve one-to-one correspondence between every original physical sheet/side and a printable overlay position, even when all answers on that page are uncertain.**

- Never drop, merge, skip or silently reorder blank/unresolved correction pages. When the original scan has N student sides that should be printed, generate N corresponding overlay sides before any explicitly authorized printer-specific adjustment or duplex padding.
- If 35 student pages are scanned for a single-sided class, the correction PDF must have 35 pages, including totally empty pages; no blank or key pages in the correction PDF.
- For multi-page tests, each student packet may span multiple sheets. One total per student, printed only in the intended score area. Treat all scanned pages as distinct until securely grouped.
- **Default physical paper arrangement: single-sided (simplex)** when uncertain. Auto-detect likely duplex but permit a teacher override. If scan/page mapping, blank-back omission, or sheet count raises doubt, flag before printing; a default is not proof.
- For duplex, map physical sheet fronts/backs explicitly. Include necessary blank printable backs to prevent correction shifts; do not print duplex output unless page pairing and printer duplex behavior have been confirmed.
- Separate **scan order**, **printer feed order**, **PDF print order**, **paper face orientation**, **rotations** and **X/Y offset**. These are independent settings.
- **LOCKED DEFAULT: NORMAL CORRECTION PDF ORDER (1 → N).** The first correction PDF page corresponds to student test 1 / its first printable side, the second to student test 2 (or the next test side), and so on. Never automatically reverse the page sequence. Name the default overlay `*_corrections_NORMAL_ORDER.pdf` (or `*_corrections_NORMAL_ORDER_decorated.pdf`), and label its mapped order plainly.
- **Printer setup selected by teacher:** RISO ORPHIS GL7430, **internal pull-out tray**, tests placed **face down**, print **single-sided**, **actual size / 100%**, and turn OFF any driver, PDF viewer, or printer setting for `Reverse Order` / `逆順印刷`. Face orientation, feed order and physical alignment must still be verified on photocopies; choosing normal PDF order is not proof of successful calibration.
- **Why this is locked:** During an earlier trial, a reversed correction PDF failed to match the intended originals; after discussing the printer configuration, the teacher explicitly selected **normal order** as the default. Do not resurrect the previous suggestion to reverse PDF pages simply because of that older failed print. A last-page-first or manually reversed print job may be generated **only at the teacher's explicit request after a measured calibration**, and must be labeled as an exception, never silently substituted for the normal-order default.
- Do not assume that a face-down stack determines whether the topmost or bottommost sheet physically feeds first. Paper feed order and PDF print sequence are independent; confirm both with a small photocopy test.
- Always preview and first calibrate with **photocopies**, not unique originals. Verify physical feed order, side, orientation, page count, actual size (100%, no fit-to-page), printer offsets, and score-box placement, then refeed the original stack as calibrated.
- If page alignment, packet mapping or tray behavior is uncertain, warn and refrain from presenting the PDF as physically verified. Never silently print a correction onto the wrong student's paper.
- Provide a clear print-order mapping report, e.g. "Normal-order PDF page 1 -> original test order 1, page 1", without adding such labels to the marks-only printable area.

## Student identity and order

- The primary identifier is the student's **original position in the input scan stack** (within a class). Name, class and student number are secondary extracted metadata and may be missing.
- Student order numbers are distinct from source PDF page numbers (which may contain blank/key pages) and from printer PDF page numbers (normal order by default; different only after explicit teacher-approved calibration).
- If a named student has multiple pages, display one student record with a source-page range; keep page-level alignment and print mapping for every physical side.
- Reports are separate from the overlay. They may include identifying metadata, but the overlay should contain only intended red corrections and scores.

## Deliverables quality checks

Before providing outputs, verify:
- For every new test version, a complete mandatory blank reference and teacher-provided/teacher-approved key were identified, their full page ranges were explicitly confirmed by the teacher, and neither was silently inferred from a student's submission.
- Every original student test page/sheet has the correct mapped output page/side; count is preserved, including ungraded/blank overlays.
- No key or blank-test pages are included in student correction overlays.
- Student order, source pages, **normal-order print mapping**, and any duplex blank pages are traceable; any exceptional, explicitly authorized reordering is separately recorded.
- **Every score has a documented visual reading of every relevant student answer**; no point was assigned or deducted merely because OCR, image differencing, circle detection or a Python classifier returned a value or blank. **If any answer has not been visually reviewed, no final total or achievement award is printed for that student.**
- Scores match rubric math, individually visually assessed answers and printed total; compare a representative set of fully composed preview pages to the original scans, and verify no apparent cohort-wide pattern of 'blank' responses was produced by recognition failure.
- Total scores are suppressed for any student with unresolved grading; **no "REVIEW"/"PENDING" or other review text may appear on a test-print overlay or its preview.** Review statuses belong in the separate teacher-facing roster, results spreadsheet, grading summary or review queue.
- Marks lie in the correct intended answer regions; score lies in the actual score box without duplicating printed "/100" if present.
- PDF dimensions, print orientation and preview/overlay relationship are consistent.
- Answer-key list reflects variable-answer policies and all teacher revisions.
- The separate printable roster contains **every student** in scan order, with name (or clearly marked unreadable), student number (or clearly marked unavailable), confirmed score (or pending-review status) and class where known; its pages are **not part of the print-overlay page count**.
- **For every visually verified 90–99 and 100 paper, visually inspect the final rendered correction page; 100% must show BOTH embroidered border and illustrated PERFECT! character stamp, and 90–99 must show its cute character praise stamp.** Do not deliver a plain-border/text-only substitute as though decoration were complete. Never put celebratory art on pending or unverified results.
- Generated files exist and were successfully read/validated before sharing links.
- Never claim real-world paper-side/order calibration is complete without a successful physical photocopy print test.

## Interaction guideline for ChatGPT

Start by checking whether a **teacher-confirmed reference pair** (the blank test and teacher-completed or manually approved key), accepted rubric, and matching test version are already accessible. If yes, ask only for the **new class's student PDF** (and optional class label). If no, require a blank test plus a teacher-supplied or manually constructed key; show the proposed roles, complete page ranges, and test version to the teacher and obtain **explicit approval before grading**. Support a one-PDF upload containing references and students. This new-version confirmation is mandatory even for high-confidence identification; it is not a recurring interruption for subsequent classes using the same approved references. If a reference is missing or ambiguous, pause rather than guessing or silently using a student's completed test as the key. Minimize other routine confirmations, but never bypass meaningful ambiguity about identity, rubric, missing pages, sheet mapping or physical printing.

This markdown file is a reusable set of instructions. **Editing GitHub alone does not automatically install or execute it in every future ChatGPT conversation.** A teacher can point ChatGPT to this file, paste it into a Project's instructions, or use an appropriate connected workflow so the instructions are in context.
