# PaperGrader v2

A no-install, browser-based tool for grading a stack of one-page student tests and printing red marks back onto the originals.

## Workflow

1. **Scan** — choose one PDF or a set of JPG/PNG scans. “First page is the answer key” is on by default. The key page is not counted as a student and is never printed. If the same scan has saved work, PaperGrader offers to resume it.
2. **Answer areas** — draw question boxes on the answer key, choose each answer type, points, and an optional expected answer. Boxes can be selected, moved, resized, and deleted. A separate name area can also be marked.
3. **Grade** — review one question across the class. Question tabs show progress and flagged counts; the key crop stays visible above compact student cards. Filter all, ungraded, or needs-review cards, or mark all remaining unflagged answers correct. Use the buttons or keyboard shortcuts below.
4. **Results** — edit student names, review totals, percentages, per-question marks, class average, and question correct rates. Export a UTF-8-with-BOM CSV for Japanese Excel.
5. **Print** — print only the red ○ / △ / × marks and scores onto the re-fed originals, with paper size, X/Y offset, reverse order, rotation, and alignment-test controls.

The app includes a frozen grader registry for later auto-graders. No auto-graders are registered in v2 build 1, so the auto-grade button remains hidden.

## Current limits

- No automatic graders are included yet.
- One physical test page per student.
- Partial credit is fixed at half the question's points.
- The normal browser print dialog is used; the app does not silently control the printer.
- Scan pages are assumed to be in the correct student order.

These constraints keep the first real-world test focused on whether scanned coordinates align accurately when originals are re-fed through the school copier.

## Run / host it

This is a static web app built with vanilla JavaScript ES modules. It has no build step, server, or database. Host the folder on GitHub Pages or any static web server; student scans are processed locally in the browser.

Opening `index.html` directly with `file://` is not recommended because browser module and security rules can block some features.

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

Question definitions, grades, names, and print settings are stored in the browser. Scanned page images are not stored. Re-select the same scan to restore its saved session.

## Likely next work

1. Test and calibrate alignment with a real copier.
2. Implement and register graders for circle choices, written words, numbers, and matching.
3. Reduce full-grid rerendering and page-canvas memory use for large classes.
4. Add reusable templates and multi-page or duplex tests.
5. Add configurable partial credit and score placement.
