# PaperGrader — Design Spec (v2)

Audience: one teacher (ESL, Japan) on a laptop/school PC with mouse + keyboard,
later shared with Japanese colleagues. Goal: a class stack goes copier → app →
copier, and the teacher only *reviews* instead of judging every answer.

## Workflow (5 steps)

1. **スキャン / Scan** — upload one PDF (or images). Toggle "1ページ目は解答 /
   First page is the answer key" (default ON). With the toggle on, page 1 is the
   key and is never treated as a student. If a saved session exists, show a
   banner: "保存された採点があります (12枚) — 同じファイルを選ぶと再開します /
   Saved session for 12 pages — choose the same files to resume."
2. **解答欄 / Answer areas** — the key page is shown large. Drag to draw a box;
   each new box opens a small inline editor in the sidebar:
   - **Type**: 記述 Written word · 数字 Number · ○で囲む Circle choice ·
     線で結ぶ Matching
   - **Points** (default 1)
   - **Expected answer** (text; optional; shown for Written/Number; hint
     "空欄ならAIが解答用紙から読み取ります / Leave blank to read it from the key")
   - Boxes can be **moved** (drag inside) and **resized** (drag corner handles);
     selected box highlighted; Delete key removes the selected box.
   - A separate button "名前欄を指定 / Mark name area" draws the single **name
     box** (dashed, not graded, not a question).
   - Sidebar lists questions in order with type icon, points and expected
     answer; clicking selects the box.
3. **採点 / Grade** — one question at a time across all students.
   - Question tabs across the top (Q1 Q2 Q3 …) each with a tiny progress ring /
     "8/12" and a ⚠ count when flagged items exist.
   - Header strip shows the **key crop** for this question (and the expected
     answer text) so the teacher always sees what's correct.
   - **Auto-grade button** "自動採点" — runs registered graders (see Grader
     interface). Hidden when no grader is registered for any question type.
   - Compact student cards: name crop (if a name box exists, else typed name),
     answer crop, status mark. Target ≥ 10 cards visible at 1366×820.
   - Clear selected-card state (thick red-pen outline + slight lift).
   - Keyboard: `1` ○ · `2` △ · `3` × · `0` clear · ←/→ move · after the last
     student, advance to the next question's first ungraded student.
   - Bulk: "残りを全部○ / Mark remaining ○" (only ungraded, non-flagged cards).
   - Filter chips: すべて All · 未採点 Ungraded · 要確認 ⚠ Needs review.
   - Status labels are consistent everywhere: ○ 正解 Correct · △ 部分点 Partial ·
     × 不正解 Wrong.
4. **結果 / Results** — table: name crop + editable name, total, percentage,
   per-question marks; class average and per-question correct rate. **CSV
   export** (UTF-8 with BOM so Excel-JP opens it correctly; columns: No., Name,
   Q1…Qn, Total, Max, %).
5. **印刷 / Print** — current print panel (paper size, X/Y offset, reverse,
   rotate, alignment test, aspect warning, ungraded confirm). Key page is never
   printed.

Top-level steps unlock in order as now.

## Grader interface (frozen)

`graders.js` exports a registry. Auto-graders live in their own files and
register themselves; the core app never imports a specific grader.

```js
// graders.js
export function registerGrader(type, fn)  // type: 'written'|'number'|'circle'|'matching'
export function hasGrader(type)
export async function runGrader(type, input)
// fn(input) -> Promise<{ status: 'correct'|'partial'|'wrong'|null,
//                        confidence: number /*0..1*/, reading?: string, note?: string }>
// input = { question, expected, keyCrop: HTMLCanvasElement, studentCrop: HTMLCanvasElement }
```

Grade record per student/question:
`{ status, source: 'teacher'|'auto', flagged: boolean, reading?, confidence? }`.
Auto-grade never overwrites a `source: 'teacher'` grade. Result with
`confidence < 0.8` or `status: null` → `status: null, flagged: true`. Teacher
setting a grade clears `flagged` and sets `source: 'teacher'`. Auto-graded
cards show a small "自動 / auto" tag and the AI `reading` if present.

## Visual direction — "Calm teacher's desk"

- Warm paper background `#f6f1e7`, cards `#fffdf8`, hairlines `#e4dccb`,
  ink text `#2b2a27`, muted `#7a7466`.
- **Red pen** accent `#c8322b` for primary actions, selection and the ○/△/×
  marks (Japanese marking convention). Correct/partial/wrong chips are
  differentiated by symbol first, tint second (soft red / amber / grey) — not
  green/red traffic lights.
- Needs-review amber `#b7791f` on `#fbf0d9`.
- Type: "Zen Kaku Gothic New" (Google Fonts) for UI, falling back to
  system-ui / "Hiragino Sans" / "Yu Gothic". Numbers tabular.
- One compact top bar (~56px): app name, the 5 steps inline, language toggle
  (日本語 / EN). No large hero header on working screens.
- Generous but not wasteful spacing; radius 10px; soft shadows only on lifted
  elements.
- Works at 1280–1920 wide; iPad width must not break but is not optimised.

## Language

All UI strings in one dictionary (`i18n.js`, `ja` and `en`). Default `ja` when
`navigator.language` starts with `ja`, else `en`. Toggle persists in
localStorage. Mark symbols ○ △ × are language-independent.

## Out of scope for v2 build 1

Actual auto-graders (ink comparison for circles; AI for written/number/
matching) — separate builds against the Grader interface. Saved templates,
multi-page tests, custom partial credit.
