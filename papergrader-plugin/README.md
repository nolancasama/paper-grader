# PaperGrader plugin

Grade scanned paper tests in ChatGPT or Codex, then print red corrections and
scores back onto the original student papers.

**The assistant looks at every answer and decides. Python never does.** Python
handles PDFs, page order, arithmetic and print files. An earlier version trusted
OCR, which marked correct handwritten numbers wrong. This one has no OCR at all.

This is a personal tool, separate from the legacy browser app in the repository
root, which is unchanged. The rules live in
[CHATGPT_GRADING_INSTRUCTIONS.md](../CHATGPT_GRADING_INSTRUCTIONS.md), and the
plugin carries an exact copy of them.

## What has and hasn't been tested

| Claim | Status |
|---|---|
| PDF pipeline, validation, reports, artwork | **Tested** with synthetic data, on Windows 10 and Python 3.14 |
| Plugin installs in Codex CLI 0.162.1 | **Tested**: installed, enabled, and `pg.py doctor` ran from the installed copy |
| Codex actually running this skill and grading | **Not tested** |
| ChatGPT desktop app, Work mode | **Not tested** |
| ChatGPT web or mobile running the scripts | **Not tested.** OpenAI's docs don't say whether they can |
| Accuracy of visual grading on real handwriting | **Not tested.** No real scans have been through this |
| Alignment on the RISO ORPHIS GL7430 | **Not tested.** Requires your physical photocopy test |

Passing tests prove the files are built correctly from the records. They can't
show that a handwriting reading is right, or that ink lands in the right place.

## Install

You need Python 3.11 or newer. Install the libraries into whichever Python the
assistant will use:

```
pip install -r papergrader-plugin/requirements.txt
```

If you use a virtual environment, keep it **outside** `papergrader-plugin/`. Local
installs copy the whole folder, including anything left in it.

### Codex CLI

```
codex plugin marketplace add C:\path\to\paper-grader
codex plugin add papergrader@paper-grader-local
```

Start a new session and ask: *"Use PaperGrader. Run doctor and show me the output."*

### ChatGPT desktop app

OpenAI's documented route for local plugins, not yet tried with this plugin:

1. In a terminal: `codex plugin marketplace add C:\path\to\paper-grader`
2. Restart the ChatGPT desktop app.
3. In Work mode, open the Plugins Directory, choose **PaperGrader (private)**, and
   install PaperGrader.
4. In a new conversation, type `@` and pick it, then ask it to run doctor.

After changing plugin files, update the marketplace and restart the app.

### ChatGPT web

OpenAI documents plugin skills on the web, but not whether bundled scripts run
there. Workspace admins can upload `papergrader-plugin.zip` through the Admin
console (build it with `python scripts/build_bundle.py`). Then run the check below.

### Check before trusting any surface

Ask: *"Run PaperGrader's doctor, then the vision check, and show me the raw output."*

| Result | Meaning |
|---|---|
| `can_process_pdfs: true` and `vision-answer` says `passed: true` | This surface can do the job. |
| `can_process_pdfs: false` | Python or PyMuPDF is missing here. |
| No raw output, or a vague summary | Assume nothing ran. Use another surface. |

If a surface can't run the scripts, the options are in
[runtime-limits.md](skills/grade-paper-tests/references/runtime-limits.md). No hosted
server has been added, and none would be without your approval.

## Grade your first class

Before uploading real student work, check that your school allows it. Anonymized
scans are safer where possible.

1. Open a new conversation with the plugin active, and upload your blank test, your
   completed key and the student scans. One combined PDF also works.
2. It proposes which pages are the blank and the key. **Confirm them.** It won't
   grade until you do, even when the answer looks obvious.
3. It shows its reading of each question, such as "any month where the circle and
   number agree". Correct anything wrong, then approve.
4. It looks at each student's answers and records what it saw.
5. It builds the files, checks them, and inspects the finished pages.
6. You receive the files and a status. Print on **photocopies** until you've run the
   calibration below.

### What you get

| File | Use |
|---|---|
| `<class>_corrections_NORMAL_ORDER.pdf` | **Print this on the papers.** Marks, score and art only |
| `<class>_correction_PREVIEW_DO_NOT_PRINT.pdf` | Check marks against the scans |
| `<class>_student_score_roster.pdf` | One row per student, in scan order |
| `<class>_grading_summary.pdf` | Overview, and answers needing your decision |
| `<class>_answer_key_list.pdf` | The rules actually applied |
| `<class>_student_results.csv` / `.xlsx`, `_answer_details.csv` | Scores, and what was seen on each answer |
| `<class>_print_order_mapping.csv` | Which PDF page goes on which paper |
| `<class>_validation_report.json`, `PRINT_STATUS.txt` | What was checked, and the result |

### What the status means

| Status | What to do |
|---|---|
| `BLOCKED` | Don't print. The report says why. Failed files are in `NOT_PRINT_READY/`. |
| `AWAITING_VISUAL_AUDIT` | Not finished. The finished pages still need inspecting. |
| `READY_FOR_PHOTOCOPY_PROOF` | Print on photocopies only. |
| `READY_FOR_ORIGINALS` | You've confirmed a physical test, so originals are fine. |

## Grade a second class on the same test

In the same job, upload only the new student PDF and give the class a name. The
blank, key and rubric are reused, numbering restarts at 1, and each class gets its
own files.

For a later conversation, first ask it to export the test (`export-test`), and keep
that file privately: it contains your answer key. Upload it next time. Chats don't
reliably keep files, and the plugin won't claim to remember a key it can't open.

## When an answer can't be read

It stays **pending**, which is different from wrong:

- That answer gets no mark. Everything else on the paper still does.
- The score box stays blank, with no stamp or border.
- No REVIEW, PENDING or `?` ever prints on a paper.
- The roster shows "Pending review", and the summary lists each one.

Tell the assistant your decision ("student 4, question 1.3 is an 8, so it's wrong"),
and it records your words and rebuilds. If you change a rule, only the affected
answers are reset, and they are looked at again.

## Regenerate the files

Ask for a rebuild, or run:

```
python -m papergrader build --job <job> --class <class>
```

The same records give the same output, including stamp positions. A rebuild replaces
all earlier files, so a stale PDF can't be printed by accident.

## Print onto the original papers

Printer: RISO ORPHIS GL7430.

1. Print `<class>_corrections_NORMAL_ORDER.pdf`, never the preview.
2. Internal pull-out tray, original sheets face down.
3. Single-sided, **actual size / 100%**, with no fit-to-page.
4. Reverse Order / 逆順印刷 **off**.
5. Keep the stack in the order it was scanned.

PaperGrader never reverses pages. Every scanned page has a matching page, even a
blank one, so one unresolved paper can't shift the rest. Reversed output isn't
offered in this version.

## Calibrate the printer

Do this on photocopies before risking originals, and again whenever the tray or
setup changes.

1. Make the test sheet (run from `papergrader-plugin/`):
   ```
   python -m papergrader calibration-pdf --job <job> --out calibration.pdf --pages 5
   ```
2. Number five photocopies of the blank by hand, 1 to 5. Load them like the originals,
   and print.
3. Check that PDF page 1 landed on sheet 1 and so on, on the correct face, the right way up.
4. Measure a cross from the paper's edge. If the cross labelled 20 mm printed at 22 mm,
   the new offset is the current offset minus 2. Positive X moves marks right, and
   positive Y moves them down.
   ```
   python -m papergrader set-offsets --job <job> --x -2 --y 1
   ```
5. Rebuild, and print the corrections on photocopies of a few student papers.
6. When it lines up, record it. Nothing else can set this, and changing an offset
   clears it:
   ```
   python -m papergrader confirm-calibration --job <job> --teacher-statement "Sheets 1-5 lined up on 5 Nov."
   ```

## Run the tests

From `papergrader-plugin/`:

```
pip install -r requirements-dev.txt
python -m pytest tests -q -n auto
python -m papergrader demo --out <empty folder outside any git repo>
```

The demo builds two synthetic classes. Its grades are typed in and labelled synthetic,
so it shows the PDF pipeline, not grading accuracy. Finished examples are in
[examples/demo_output/](examples/demo_output/).

## How the pieces fit

| Path | Role |
|---|---|
| `plugin.json`, `.codex-plugin/` | Plugin manifests |
| `skills/grade-paper-tests/` | Instructions for the assistant, references and launcher |
| `papergrader/grading_models.py` | Strict record formats, plus the only place totals are computed |
| `papergrader/pdf_processor.py` | Page inventory, rendering, crops and grids, page-map proposals |
| `papergrader/correction_overlay.py` | Mark positions, rotation, drawing the PDFs |
| `papergrader/decorations.py` | Stamp and border placement, and measuring that they exist |
| `papergrader/validator.py` | Fail-closed checks on the inputs and the finished files |
| `papergrader/reports.py` | Roster, summary, answer key, spreadsheets |
| `papergrader/printer_config.py`, `printers/` | Printer profile, calibration sheet |
| `papergrader/pipeline.py`, `job.py` | Build-then-validate, status ladder, job folder |
| `papergrader/vision_check.py` | Proves a session can see images |
| `assets/`, `scripts/generate_art.py` | Original vector art, and the code that draws it |

## Privacy

This repository is **public**. Student scans, names, grades and answer keys must never
be committed.

- Job folders go outside any git checkout, and `init-job` refuses one inside.
- A test fails if a PDF, spreadsheet or grading record is tracked anywhere other than
  the synthetic examples folder.
- The package contains no analytics, telemetry or network code, and a test enforces
  that. Whatever you upload to ChatGPT or Codex is still subject to OpenAI's terms and
  your school's rules.

## Art and licensing

All stamps and embroidery are original, drawn from code in `scripts/generate_art.py`,
with no fonts or third-party images. The border is inspired by the title of your
reference listing (ORIGACH "Floral Border & Corner" embroidery paper). Its product
images couldn't be viewed, so this isn't a match to that artwork. Send a screenshot if
you want it closer.

PyMuPDF, a dependency, is AGPL-3.0. It's installed separately and not redistributed
here, which is fine for personal use. Review that license if this ever becomes a
distributed product.
