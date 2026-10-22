# PaperGrader — ChatGPT Conversation Handoff

**Purpose:** A durable, human-readable memory of our design discussions, so a future ChatGPT conversation can pick up where we left off. **This is not app code and is not a claim that the features exist.**  
**Last discussion captured:** October 22, 2026.  
**GitHub repo:** https://github.com/nolancasama/paper-grader  
**Detailed, normative feature specification:** [docs/chatgpt-grading-spec.md](docs/chatgpt-grading-spec.md)  
**Existing app implementation and older architecture:** [README.md](README.md)

## How to use this handoff in a new ChatGPT conversation

Ask: **"Read `CHATGPT_HANDOFF.md` and `docs/chatgpt-grading-spec.md` in my `nolancasama/paper-grader` GitHub repository, then continue our PaperGrader discussion."**

The assistant should read both files using the connected GitHub tools, check the current repository code before making claims about implemented features, and treat this handoff as context rather than automatic instructions to make changes. The spec records intended requirements; this document records *why* we chose them, the trial observations, what is still unverified, and the user's priorities. GitHub won't automatically be reread in every new chat; the user must request it or provide the link.

## What we're trying to achieve

The user teaches elementary-school English in Japan and wants to grade handwritten/paper ESL worksheets quickly. The most important outcome is **printing only red correction marks and the right total score onto the original student papers** after feeding them back into the printer. Grade-only spreadsheets are insufficient.

The user originally had a browser-based app called **PaperGrader** in the `paper-grader` GitHub repository, with browser-local alignment, answer area selection, a matching-lines grader, manual ○/△/× marking, CSV, an offline build, and marks-only printing. We discussed whether grading could instead happen *directly through ChatGPT*: upload PDFs in a chat, let ChatGPT analyze/grade, and generate downloadable correction-overlay PDFs, possibly removing the need to use the app for grading. Another possibility is to keep the app as the alignment/printing front end while AI handles interpretation. **Architecture is not yet decided.** Do not silently assume we have committed to OpenAI API integration or to replacing the offline app.

## User's strongly expressed priorities

- The **physical original test** receives red ○, △, × marks and a numerical total in its **existing score box**. Print **only** the marks/score, never a new copy of the worksheet.
- **Preserve every student physical page/side** in the correction printing sequence. Uncertain tests must NOT be removed, because that would shift every later student's marks onto the wrong paper.
- Teacher should be able to put **Student 1 on top of the stack in normal order**, without manually reversing the stack. Generate correction pages in whatever order the calibrated printer needs.
- A low-confidence answer may remain blank, but all confidently graded answers on the same sheet should still get red marks. Do not print a total when the score is unresolved.
- Prioritize accurate grading and calibration over shaving off one upload step.
- Prefer automated, understandable operation. Minimize manual drawing of answer regions when feasible, but allow teacher review where needed.

## Locked input workflow and page organization

1. **Blank/empty original worksheet PDF is required.** The user explicitly rejected dropping this requirement.
2. **Completed teacher answer key PDF is required.**
3. **All scanned student tests** are uploaded as PDF(s), usually one multipage PDF representing the scanned stack.
4. The system itself converts image-based PDFs to renderable page images internally. The teacher should not have to manually convert files to PNGs.
5. Support either **three separate uploads** or **one combined PDF** whose logical order is:
   - all blank worksheet pages,
   - all teacher completed-key pages,
   - all pages of Student 1,
   - all pages of Student 2,
   - etc.
6. Multiple-page tests are supported. If the blank worksheet has N pages, the key has matching N pages, and each student generally has a corresponding N-page packet. Detect/flag missing/duplicate/out-of-order pages and do not silently reassign student pages.
7. Output correction-overlay page count corresponds to **every actual student page/printable side** (with duplex filler sides as required), not the blank/key pages. A wholly unresolved student still needs blank overlay page(s) in exactly the correct slot.

## Locked context-aware grading approach

The user noticed a fundamental issue on their example answer key: **Question 4** depicts one teacher example, **September / 9**, but students are asked to indicate **their own birth month**. If a student chooses April and writes 4, that can be correct; the key is *not* a fixed answer of September. The system must read the **entire blank worksheet instructions, the question, images, and the teacher's completed response** before deciding the rubric. Do not blindly regard the teacher's marks as the only permitted answer.

The intended order:
1. Analyze the complete blank and completed key.
2. Determine what each question is asking: fixed answer, multiple acceptable answers, personal/choice-based response, example, matching, open writing, etc.
3. Build a consistent, teacher-reviewable **per-question rubric** with points and partial credit.
4. Grade student answers using both crops and surrounding whole-page context when needed.
5. Flag ambiguous scans/handwriting/crossing matching lines and grading-rule uncertainty; don't invent certainty or grades.
6. Permit teacher rubric edits and **regrade all affected students consistently**.
7. Export grades/CSV/spreadsheet and produce the printable correction overlays.

The user explicitly said **"let's lock this in"** for context-aware grading.

## Locked correction and score printing rules

- Red symbols: ○ for correct, △ for partial, × for wrong. Provide appropriate score with rubric-based point total.
- Place red marks at the correct answer locations and **write the total score in the printed score area** of the corresponding student page. For example, if the worksheet already includes a printed `/100`, position the number rather than redundantly printing another denominator.
- Multi-page tests have **one total per student**, placed in the designated box (not one independent total per page).
- The **marks-only PDF** contains no worksheet image/text (so it can be printed on the originals). Produce a separate **visual preview PDF** for inspection.
- Use PDF layout alignment based on the **blank worksheet** plus individual student page alignment, printer-size settings, X/Y calibration, rotation, print-side orientation, and page-order mapping.
- **Never drop/reorder logical student identities due to low grading confidence.** Unresolved answers stay unmarked; a withheld score box remains blank; entirely unresolved sheets have blank overlay slots.
- Missing pages or an ambiguous **physical-sheet mapping** are a separate and more serious problem: hold printing until that mapping is corrected rather than just leave an answer unmarked.
- Print at actual size. First verify on photocopies before printing on real student papers.

## Printer trial: what actually happened and what's still unresolved

In a small, single-page, three-student trial, the user loaded originals **Student 1 on top, then 2, then 3**. The user reported **the last student's corrections printed on the BACK of the FIRST student's paper**. That identifies **two independent calibration dimensions**:
1. **Feed/page order:** correction PDF likely needs reverse page order for the printer/tray being used, so the teacher can retain Student 1 on top.
2. **Sheet face:** the papers were presented with the wrong side toward the printer's marking mechanism. Changing PDF page order alone does not correct the side.

The user said they had to **manually reverse the physical student papers** with the former correction PDF. They want that unnecessary in the final system. A **reversed-correction PDF** was proposed/generated during the prior trial, but the conversation does **not** establish that it was physically tested successfully. Don't state that the combination is proven. Provide **independent, persistent printer-profile settings** for output page order and face orientation. Calibrate both using photocopies, and verify every sheet/side receives the matching student's marks.

## Single-sided vs double-sided — finalized default

The user asked how the AI could know if originals were single-sided or double-sided. We established a PDF alone does not always reveal physical sheet sides, especially if scanning omits blank backs. Use any reliable evidence available (printed page labels, scan layout, blank backs, physical sheet count) and teacher confirmation where necessary.

**Explicit final choice: if uncertain, default to single-sided/simplex.** This is a fallback assumption, not permission to print with unverified or contradictory page mapping.

Support duplex as a selectable/confirmed option, including front/back pairing and blank placeholder sides where needed. Retain relevant verified printer profile settings.

## Prior example: scanned worksheet and grading test

Earlier in the conversation the user supplied a ZIP (containing **blank PDF**, **completed-key PDF**, and a **three-page student PDF**). The user was told the scanned PDFs were converted to images, a grading table was produced, and correction-overlay/preview/results files were generated. The trial's reported example was a **100-point English worksheet** with:
- Q1: number/birthday order, 30 points.
- Q2: matching students to birthdays, 40 points; lines can cross.
- Q3: matching words/pictures, 20 points.
- Q4: choosing one's birth month, 10 points; the written number must match the chosen/circled month. The key's September/9 is just a sample.
- Score box at top near Class/No./Name, with printed `/100` and diagonal guide.

The previous response reported **sample student totals 10, 100, 50**, but these are **initial AI trial outputs, not a teacher-verified ground truth**. In any subsequent implementation/testing, check against the actual scan and teacher's marking rather than trusting those figures.

Prior chat-linked correction PDFs/CSV files may not be accessible in another session. Don't assume file paths from old messages will work; request/upload source PDFs again if a new test requires the actual image data. The original GitHub repo contains the application source, not necessarily the uploaded student scans.

## Implementation context and relationship to existing code

As inspected in the previous conversation (2026-10-22):
- Repo: `nolancasama/paper-grader` (`main`).
- `README.md` documents existing local/offline workflow, manual grading, alignment, correction overlays, and a future optional AI ladder.
- `app.js` handles PDF rendering, template/student alignment, question areas, grade records, preview/printing, score boxes, PDF overlay generation, page reversal settings, and CSV.
- `graders.js` provides a grader registry.
- `graders/matching.js` provides the registered auto-matching grader; handwritten/open-response AI grading was not enabled.
- `tools/build-offline.mjs` creates the offline `file://` build.

This **ChatGPT-first** workflow is an agreed future design, **not already implemented or proven in the current app**. Reopen code for current truth before any change.

## Validation checklist to carry forward

- Read-and-understand rather than key-pixel comparison; Question 4 examples accepted properly.
- Good handling of handwritten English, circle answers, numbers, matching lines with crossings, partial credit, and uncertainty.
- One or many worksheet pages; combined or separate PDFs; correctly identified student groups.
- Preview and **marks-only** printable corrections, including correct red **total in score box**.
- Exact preservation of student print slots, including blank overlays for uncertain papers.
- Correct confirmed scores withheld when unresolved; consistent regrading after rubric edits.
- Printer mapping: Student 1 on top, natural physical order; appropriate PDF output order; correct **front** side; physical calibration verified.
- Single-sided default on uncertainty; optional duplex with correct blank-back placeholders.
- Privacy: anonymize student work for tests; verify school permission before sending real student data to ChatGPT/API.
- Use photocopies for initial print tests, not irreplaceable original student work.

## Outstanding decisions / next practical step

The next high-value step is a **physical, photographed verification trial** with a few photocopies, using numbered front/back test sheets. Establish the actual input tray's feed order and paper-face orientation, then confirm red marks and the score land correctly on *all* sheets. Only then bake printer-profile defaults into the pipeline.

Separately, decide whether to run grading **directly in ChatGPT** (manually upload PDFs each batch) or integrate a model via API into PaperGrader (automated app flow, separate cost and privacy implications). The user has *not* requested this implementation yet.

## Do not misinterpret prior decisions

- User's "lock in" means **agree the desired product requirement**, not silently push code.
- **Blank PDF remains mandatory**, despite exploring a key-only approach.
- **Single-sided is default**, not always fact.
- **Reversed PDF was proposed**, but correct back/front orientation and printer matching still require testing.
- **A low-confidence test is not discarded**; it still uses up exactly its physical overlay slots in the print sequence.
- The file [docs/chatgpt-grading-spec.md](docs/chatgpt-grading-spec.md) gives more formal acceptance criteria; **this file provides the conversational context and reasoning**.
