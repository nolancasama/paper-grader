# PaperGrader v2

A no-install, browser-based tool for grading a stack of one-page student tests and printing red marks back onto the originals.

## Workflow

1. **Scan** — choose one PDF or a set of JPG/PNG scans. “First page is the answer key” is on by default. With no saved question areas, red ink on the key is detected locally once and proposed as answer areas. Use **Detect red answers** to run it again. The key page is not counted as a student and is never printed. If the same scan has saved work, PaperGrader offers to resume it.
2. **Answer areas** — review the proposed boxes or draw your own. Dashed red boxes are proposals; amber boxes need a closer check. Confirm individually or all at once; editing a proposal also confirms it. The sidebar is the linear answer key: edit labels, inspect key thumbnails, choose types, points, and optional expected answers, and reorder or renumber by position. Shift-click boxes or sidebar items to select several and merge them. Separate name and score areas can also be marked.
3. **Grade** — review one question across the class. Question tabs show progress and flagged counts; the key crop stays visible above compact student cards. The local matching-lines grader awards proportional credit and flags uncertain answers. Select a matching card to inspect key/student crops and correct detected connections in the review panel, then Apply. Filter all, ungraded, or needs-review cards, or mark all remaining unflagged answers correct. Use the buttons or keyboard shortcuts below.
4. **Results** — edit student names, review totals, percentages, per-question marks, class average, and question correct rates. Export a UTF-8-with-BOM CSV for Japanese Excel.
5. **Print** — print only the red ○ / △ / × marks and scores onto the re-fed originals, with paper size, X/Y offset, reverse order, rotation, and alignment-test controls. Scores are centred inside the optional score area, otherwise at the existing top-right position. A student with any ungraded or flagged answer receives no printed total; graded, unflagged answer marks still print. Alignment-test output is unchanged.

The app uses a grader registry and includes a local matching-lines grader. Other answer types remain available for teacher grading; additional graders can register through the same interface. All detection and matching processing stays in the browser.

## Current limits

- Automatic grading currently covers matching lines; handwriting recognition is not included.
- One physical test page per student.
- Matching credit is the fraction of expected connections answered correctly. A manually assigned partial grade without matching review remains half the question's points.
- The normal browser print dialog is used; the app does not silently control the printer.
- Scan pages are assumed to be in the correct student order.

These constraints keep the first real-world test focused on whether scanned coordinates align accurately when originals are re-fed through the school copier.

## Run / host it

This is a static web app built with vanilla JavaScript ES modules. It has no build step, server, or database. Host the folder on GitHub Pages or any static web server; student scans are processed locally in the browser.

Opening `index.html` directly with `file://` is not recommended because browser module and security rules can block some features.

## Offline build

The self-contained `file://` build lives in `offline/`. After changing web sources, regenerate it with `npm run build:offline`.

## PDF support

The app first tries to load local files:

- `vendor/pdf.mjs`
- `vendor/pdf.worker.mjs`

If those are not present, it falls back to Mozilla PDF.js 6.3.289 from jsDelivr at runtime.

For a school deployment where you do not want a CDN dependency, place the matching PDF.js build files in `vendor/` before deploying. The Google Font stylesheet is the only other external runtime dependency.

## First copier test

Do **not** test first on a real student's only copy.

1. Scan an answer key followed by 2–3 sample student sheets.
2. Define a few answer boxes on the key page and assign fake grades to the students.
3. Make a photocopy of one student sheet.
4. Put that photocopy in the printer feed tray.
5. Use **Print alignment test**.
6. In the browser print dialog choose the exact paper size, Actual Size / 100%, and disable headers, footers, and fit-to-page.
7. If the marks are uniformly shifted, change the X/Y offset in the app and print again.
8. If the sheet comes out upside down, enable **Rotate correction overlay 180°**.
9. If stack order is reversed between scan output and printer feed, enable **Reverse page order**.

The answer-key page is excluded from student totals and print output. If marks shift differently from page to page rather than by one consistent offset, that is a printer-feed registration issue and is the key thing to measure before adding auto-graders.

## Keyboard grading

Select a student card, then use:

- `1` = correct and advance
- `2` = partial and advance
- `3` = wrong and advance
- `0` = clear
- Left / Right arrows = move between students

After the final student, grading advances to the next question's first ungraded student.

## Privacy and saved work

The app does not upload student pages. PDF rendering via the CDN fallback downloads JavaScript code from jsDelivr; it does not send the selected PDF to jsDelivr. For a fully self-contained deployment, host the PDF.js files locally as described above.

Question definitions (including proposal status), grades (including matching review details and credit), names, name/score areas, and print settings are stored in the browser. Scanned page images and key thumbnails are not stored; thumbnails are cached in memory by question geometry. Re-select the same scan to restore its saved session.

## Likely next work

1. Test and calibrate alignment with a real copier.
2. Extend local recognition and add graders for circle choices, written words, and numbers.
3. Reduce full-grid rerendering and page-canvas memory use for large classes.
4. Add reusable templates and multi-page or duplex tests.
5. Explore a split-box tool and stronger page-identity rekeying for changed scans.
