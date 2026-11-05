# Command reference

`pg` means `python <skill folder>/scripts/pg.py`. Every command prints one JSON
object. Exit code 0 means success, 1 means a problem or blocked build, and 2 means
this runtime can't work at all.

## Setup

| Command | Purpose |
|---|---|
| `pg doctor` | Test what this runtime can really do. |
| `pg init-job --job DIR` | Create a private job folder. Refuses a folder inside a git checkout. |
| `pg vision-check --job DIR` | Create an image only a seeing session can answer. |
| `pg vision-answer --job DIR NUMBER` | Answer it. Three attempts. |
| `pg add-source --job DIR a.pdf b.pdf` | Copy PDFs into the job, and list pages and hashes. |
| `pg inspect FILE.pdf` | List a PDF's pages without changing anything. |
| `pg view-source --job DIR FILE --pages 1,2 [--rotation R] [--rect x,y,w,h] [--zoom Z] [--grid]` | Render pages to look at. |
| `pg set-test --job DIR test.json [--replace]` | Validate and save the rubric. |
| `pg export-test --job DIR --out test.zip` | Save the confirmed test for a later session. Private: it holds the key. |
| `pg import-test --job DIR test.zip` | Load a saved test into a new job, verifying hashes. |

## Each class

| Command | Purpose |
|---|---|
| `pg propose-map --job DIR --class ID --label "2年1組" scans.pdf [--exclude FILE:ROLE:PAGES] [--paper-mode duplex]` | Propose packets in scan order. |
| `pg set-rotation --job DIR --class ID --rotation 180 --slots 5,7` | Record orientation you saw: clockwise degrees to make the page upright. Add `--rest` for all other pages. |
| `pg scaffold-grading --job DIR --class ID` | Create the record with every answer pending. Never overwrites. |
| `pg render --job DIR --class ID [--slots 1-5] [--dpi 200]` | Render page images. Each gets a ref to cite. |
| `pg render --job DIR --class ID --slots 3 --rect 20,10,30,10 --zoom 3 [--grid]` | Enlarge a detail. |
| `pg check --job DIR --class ID` | Validate records and show totals, without building. |
| `pg rebase-grading --job DIR --class ID` | After a rubric change, reset only the affected answers. |
| `pg build --job DIR --class ID` | Generate and validate everything. |
| `pg attest-audit --job DIR --class ID --slots 1,4 --statement "..."` | Record which finished pages you viewed. |
| `pg status --job DIR --class ID` | Re-check the files, and say whether they may be printed. |

## Reading positions

All positions are percentages of the **upright** page: `x_pct` from the left and
`y_pct` from the top. A `--grid` view prints those numbers on the image, so read
them straight off it. Python rotates everything to match the physical sheet.

If a student's copy has its printed content shifted relative to the template, set
`content_offset_pct` on that slot in `page_map.json`. Marks and the score then move
with the print. Set `mark` on one answer to place a single mark by hand.

Choose `stamp_zone` from blank paper near the score, at least about 70 x 55 mm so a
PERFECT! stamp keeps its natural variation. List headings, names and anything else
near the page edge in `protected_regions`; the border interrupts itself around them.
If one student has writing in the zone, give that student their own `stamp_zone`.

## Output files

In `classes/<class>/output/`, all prefixed with the class id:

| File | Contents |
|---|---|
| `_corrections_NORMAL_ORDER.pdf` | Red marks, score and earned art only. **The print file.** One page per scanned page. |
| `_correction_PREVIEW_DO_NOT_PRINT.pdf` | The same marks over the scan, for checking. |
| `_student_results.csv` / `.xlsx`, `_answer_details.csv` | Scores, and each observation behind them. |
| `_grading_summary.pdf` | Class overview and the teacher's review list. |
| `_student_score_roster.pdf` | One row per student in scan order. |
| `_answer_key_list.pdf` | The rule set actually applied. |
| `_print_order_mapping.csv` | Each PDF page to its student, sheet and source page. |
| `_validation_report.json`, `PRINT_STATUS.txt` | Machine-readable checks, and a plain summary. |
| `_decoration_audit.json`, `proofs/` | The pages to inspect, rendered to PNG. |

A failed build puts its files in `NOT_PRINT_READY/`, with that phrase in each name.

## Printing and calibration (RISO ORPHIS GL7430)

Locked setup: internal pull-out tray, original sheets face down, single-sided,
actual size / 100%, PDF order 1 to N, Reverse Order / 逆順印刷 off.

These settings came from the teacher, but they aren't proof. The first run is always
on photocopies:

1. `pg calibration-pdf --job DIR --out cal.pdf --paper A4 --pages 5`. With `--job`, the
   sheet also shows this test's score box and mark positions.
2. Number five photocopies of the blank by hand, 1 to 5, and load them in the same
   arrangement as the originals. Print `cal.pdf`.
3. Check feed order (PDF page N on sheet N), printed face and orientation.
4. Measure each cross from the paper edge. If a cross labelled 20 mm prints at 22 mm,
   the new offset is the current offset minus 2. Positive X moves marks right, and
   positive Y moves them down.
5. `pg set-offsets --job DIR --x -2 --y 1`, rebuild, and print the correction PDF on
   photocopies of a few student papers.
6. Only once the teacher says it lined up:
   `pg confirm-calibration --job DIR --teacher-statement "the teacher's words"`.

Changing an offset clears the confirmation. Don't run `confirm-calibration` on your
own judgment. A preview, however good it looks, says nothing about the printer.

Paper feed and face direction depend on the machine and tray. An earlier trial
printed the last student's marks on the back of the first student's paper, so
check this physically every time the setup changes.
