# PaperGrader MVP

A no-install, browser-based prototype for this workflow:

1. Scan a stack of one-page student tests to PDF/JPG/PNG.
2. Open the scan in the web app.
3. Draw answer boxes once on the first student's page.
4. Grade the same question across every student with buttons or keyboard shortcuts.
5. The app calculates totals.
6. Re-feed the original test stack into the copier/printer.
7. Print only red ○ / △ / × marks and scores onto the originals.

## What this MVP deliberately does NOT do

- No AI/OCR yet.
- One physical test page per student.
- Partial credit is fixed at half the question's points.
- It does not silently control the printer; the normal browser print dialog is used.
- It assumes the scan pages are already in the correct student order.

Those constraints keep the first experiment focused on the hardest real-world question: **Can the scanned coordinates line up accurately enough when the originals are re-fed through the school copier?**

## Run / host it

This is a static web app. Host the folder on GitHub Pages or any static web server. No server database is required, and student scans are processed locally in the browser.

Opening `index.html` directly with `file://` is not recommended because browser module/security rules can block some features.

## PDF support

The app first tries to load local files:

- `vendor/pdf.mjs`
- `vendor/pdf.worker.mjs`

If those are not present, it falls back to Mozilla PDF.js 6.3.289 from jsDelivr at runtime.

For a school deployment where you do not want a CDN dependency, place the matching PDF.js build files in `vendor/` before deploying. The rest of the app has no external runtime dependency.

## First copier test

Do **not** test first on a real student's only copy.

1. Scan 2–3 sample sheets.
2. Define a few answer boxes and assign fake grades.
3. Make a photocopy of one of those sheets.
4. Put that photocopy in the printer feed tray.
5. Use **Print alignment test**.
6. In the browser print dialog choose the exact paper size, Actual Size / 100%, and disable headers/footers/fit-to-page.
7. If the marks are uniformly shifted, change the X/Y offset in the app and print again.
8. If the sheet comes out upside down, enable **Rotate correction overlay 180°**.
9. If stack order is reversed between scan output and printer feed, enable **Reverse page order**.

If marks shift differently from page to page rather than by one consistent offset, that is a printer-feed registration issue and is the key thing to measure before adding AI.

## Keyboard grading

Click a student card, then:

- `1` = correct and advance
- `2` = partial and advance
- `3` = wrong and advance
- `0` = clear
- Left / Right arrows = move between students

## Privacy

The app itself does not upload student pages anywhere. PDF rendering via the CDN fallback downloads JavaScript code from jsDelivr; it does not send the selected PDF to jsDelivr. For a fully self-contained deployment, host the PDF.js files locally as described above.

## Best next features after the copier test works

1. Save/reuse test templates.
2. Two-page tests and duplex scanning.
3. Custom partial-credit values.
4. OCR for fixed answers.
5. AI suggestions for handwritten English, with teacher confirmation for uncertain answers.
6. Optional typed correction comments printed beside answers.
