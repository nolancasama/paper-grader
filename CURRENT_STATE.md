# Current State

## Status
MVP live on GitHub Pages: https://nolancasama.github.io/paper-grader/
(repo nolancasama/paper-grader, deploys from `main` root). Static vanilla JS, no build, no tests.

## What Exists
Upload scans (PDF/images) → draw answer boxes → grade per question (○/△/×, keys 1/2/3/0) →
print red marks + score onto re-fed originals, with X/Y offset, 180° rotate, reverse order.
Reliability pass (2026-10-05): session saved to localStorage (keyed by scan fingerprint,
restored on re-loading the same files), printer settings persist across scans,
network-first service worker, natural file sort, ungraded-print confirm, aspect-ratio warning.

## Known Issues
- Whole grade grid re-renders on every grade; slow for 35–40 students.
- Every page held as a full-size canvas (~10 MB each); risk on iPads/Chromebooks.
- Score always printed top-right; may overlap the paper's name/score area.
- Real-copier alignment not yet tested.

## Next Steps
1. Real copier alignment test with a photocopy (see README).
2. Performance/memory pass (items above).
3. Configurable score position.
