PaperGrader v2 Offline

1. Extract this ZIP/folder.
2. Keep all files together in the same folder.
3. Double-click index.html.
4. Choose Chrome or Edge if Windows asks.
5. No installation is required.
6. No AI connection is required.
7. Student scans stay on this computer.

This build is based on the current PaperGrader v2 web interface, but it removes ES-module and service-worker dependencies so it can run from file:// on a locked-down school PC.

Files:
- index.html
- styles.css
- offline-app.js
- pdf.min.js

PDF.js is bundled locally. Its worker code is embedded inside offline-app.js.

For the first printer test, use photocopies rather than the only copy of a student's paper.
