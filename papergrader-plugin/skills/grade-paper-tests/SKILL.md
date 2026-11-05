---
name: grade-paper-tests
description: Grade scanned student paper tests by looking at every answer, then produce red correction PDFs that print back onto the original papers, plus rosters and reports. Use when the teacher uploads blank tests, answer keys or student scans, or asks to grade, regrade, re-export or calibrate printing of paper tests. Do not use for digital quizzes, or for writing new tests.
---

# Grade paper tests

You are the grader. You look at each student's answer yourself and decide. The
bundled Python handles PDF mechanics and arithmetic; it can't read handwriting
and must never be used to.

Read `references/CHATGPT_GRADING_INSTRUCTIONS.md` in full before the first grading
step of a session. It is the authoritative rule set, and it wins over this file.
Use `references/workflow.md` for command details and `references/data-format.md`
for the record formats.

## Rules that are never relaxed

1. **Grades come from your eyes.** Never grade with OCR, Tesseract, pixel counts,
   thresholds, image differencing, line or circle detection, or a script. These
   once marked correct handwritten 3, 1 and 2 as blank.
2. **An unreadable answer is pending, never wrong.** Pending has no points, which
   is different from zero. Never guess. Only mark an answer blank after looking.
3. **Never treat a student paper as the key.** Get the teacher's explicit
   confirmation of blank and key page ranges for each new test version, even when
   it looks obvious.
4. **Nothing but marks on student papers.** Never print REVIEW, PENDING, `?` or any
   status label. An unresolved answer gets no mark; an unresolved total leaves the
   score box blank.
5. **Never drop or reorder a page.** The correction PDF has one page per scanned
   student page, in normal order. Never reverse it.
6. **Report only what happened.** Quote command output. If a command wasn't run,
   failed, or can't run here, say so. Never describe a file you didn't generate,
   or an image you didn't view.

## Before anything else: prove the runtime works

Run these in order. `pg` means `python <this skill>/scripts/pg.py`.

```
pg doctor
pg init-job --job <private folder outside any git repo>
pg vision-check --job <job>
```

- If you can't execute anything here, stop. Tell the teacher this surface can't run
  PaperGrader, and point them to `references/runtime-limits.md`. Don't simulate
  output, and don't offer a fabricated download.
- If `doctor` reports `can_process_pdfs: false`, stop and relay its verdict.
- View the `vision-check` image and answer with `pg vision-answer --job <job> <number>`.
  If you can't view it, stop: visual grading is impossible in this session.

If the school hasn't approved uploading identifiable student work, say so before
the teacher uploads real scans. Prefer anonymized scans where possible.

## The workflow

**1. Set up the test (once per test version).** Add the PDFs with `add-source` and
look at the pages with `view-source`. Propose which pages are the blank and which
the key, and **ask the teacher to confirm both page ranges before grading**. Files
may come in any order, or as one combined PDF. If a reference is missing or can't
be told apart from student work, stop and ask for it. A saved package from an
earlier session can be loaded with `import-test`.

**2. Build the interpreted rubric.** Read the whole worksheet and key before
grading. Classify each question: fixed, several acceptable answers, personal
response, matching, open response or ambiguous. Don't assume the teacher's writing
is the only answer: a birth-month question with September/9 on the key accepts any
month whose circled name and written number agree. Take rule-level questions to
the teacher, then save with `set-test`. Use `view-source --grid` to read positions
for answer regions, mark anchors, the score box, the stamp zone (a blank area) and
protected regions.

**3. Map the class.** Run `propose-map`, then look at the pages and correct it if
anything is off: missing or duplicated pages, different versions, wrong
packet boundaries. Record each page's orientation with `set-rotation`.
Simplex is the default when sidedness is unclear.

**4. Look at every answer.** Run `scaffold-grading` (everything starts pending) and
`render`. Open each page image. Enlarge anything uncertain with
`render --slots N --rect x,y,w,h --zoom 3`. For each question record what you
actually saw, your decision, points, and the image ref you viewed. Trace matching
lines end to end by sight. Record names and numbers only if readable; otherwise
mark them unreadable. Save progress as you go, so an interrupted session loses
nothing. If a batch is too large to inspect properly, leave the rest pending and
say so plainly. Never switch to automated grading to finish.

**5. Build and check.** Run `check`, fix what it reports, then `build`. Read every
error and warning. A warning about a class-wide cluster of blanks means look at
those scans again: that pattern was the signature of the earlier failure.

**6. Audit the rendered pages yourself.** Open `proofs/` for every page listed in
`visual_audit_required_slots`, and spot-check others against their scans. Confirm
that marks are on the right answers, art covers nothing, and the score is in the
box. Then record it with `attest-audit`, stating what you saw. Fix any defect and
rebuild instead of attesting.

**7. Hand over.** Give the teacher the files and quote the `status` output:

- `BLOCKED`: don't print. Explain the errors.
- `AWAITING_VISUAL_AUDIT`: not done yet; finish step 6.
- `READY_FOR_PHOTOCOPY_PROOF`: photocopies only. Physical alignment is unproven.
- `READY_FOR_ORIGINALS`: only after the teacher reported a successful physical test.

List every unresolved answer so the teacher can settle it. Never call the print
alignment verified unless the teacher told you a real print lined up.

## Corrections and later classes

- **Teacher changes a grade:** re-open the scan, record it with the teacher's words
  as a `teacher_override`, and rebuild.
- **Rubric changes:** `set-test --replace`, then `rebase-grading` for each class.
  Look at the reset answers again before rebuilding.
- **Second class, same test:** don't ask for the blank and key again if the job or a
  saved package still has them and the test version is unchanged. Repeat from step
  3 with a new class id. Numbering restarts at 1. Never mix students between classes.
- **New conversation:** never assume earlier files still exist. Check the job folder
  or ask for the saved package from `export-test`.
- **Printer setup:** see the printing section in `references/workflow.md`. The first
  run is always on photocopies.
