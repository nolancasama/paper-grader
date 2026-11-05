# Record formats

Validation is strict: unknown fields are errors, so check spelling. Run
`pg check` after editing anything by hand.

## test.json: the interpreted answer key

```json
{
  "schema_version": 1,
  "test_id": "english-unit3",
  "test_version": "2026-11",
  "title": "Unit 3 Check-Up",
  "template_pages": 1,
  "max_points": 100,
  "references": {
    "blank": {"kind": "scan", "source_pdf": "blank.pdf", "sha256": "<from add-source>", "pages": [1]},
    "key": {"kind": "scan", "source_pdf": "key.pdf", "sha256": "<from add-source>", "pages": [1]},
    "teacher_confirmation": {
      "confirmed": true,
      "confirmed_at": "2026-11-05T09:00:00+09:00",
      "teacher_statement": "Quote what the teacher actually said to confirm these pages."
    }
  },
  "rubric_status": "approved",
  "open_rubric_questions": [],
  "score_box": {"template_page": 1, "x_pct": 70, "y_pct": 5.5, "w_pct": 11, "h_pct": 5, "denominator_printed": true},
  "stamp_zone": {"template_page": 1, "x_pct": 50, "y_pct": 12, "w_pct": 44, "h_pct": 36},
  "protected_regions": [
    {"template_page": 1, "x_pct": 9, "y_pct": 5, "w_pct": 40, "h_pct": 7, "label": "name and class"}
  ],
  "questions": [
    {
      "id": "4",
      "template_page": 1,
      "kind": "personal",
      "prompt": "Circle your birth month and write its number.",
      "accepted_answers": ["Any month whose circled name and written number agree"],
      "rule": "Accept any month if the circled month and written number agree.",
      "rationale": "September/9 on the key is only the teacher's example.",
      "partial_credit": "",
      "points": 10,
      "answer_region": {"x_pct": 10, "y_pct": 79, "w_pct": 75, "h_pct": 14},
      "mark_anchor": {"x_pct": 80, "y_pct": 90},
      "mark_size_mm": 9
    }
  ]
}
```

- `kind`: `fixed`, `multiple_acceptable`, `personal`, `matching`, `open` or `ambiguous`.
  Ambiguous blocks the build until the teacher decides.
- A key entered by the teacher instead of scanned: `{"kind": "teacher_entered_list", "pages": []}`.
- `score_box` covers the space for the number, left of any printed `/100`. When the
  worksheet prints no denominator, set `denominator_printed: false` and optionally
  `append_denominator: true`.
- Optional: `perfect_stamp_zone`, if a PERFECT! stamp needs a bigger area.
- Points must add up to `max_points`. Editing rubric text changes the rubric hash and
  forces a regrade; moving an anchor doesn't.

## grading.json: one judgment per question

`scaffold-grading` creates this. Replace each pending answer as you inspect it.

A graded answer:

```json
{
  "question_id": "1.1",
  "observed_kind": "written",
  "observed_answer": "3",
  "decision": "correct",
  "awarded_points": 10,
  "max_points": 10,
  "verification": {"status": "visually_verified", "method": "direct_visual", "image_ref": "slot-0001", "crop_refs": ["slot-0001-view-001"]},
  "confidence": {"alignment": "high", "reading": "high", "interpretation": "high"},
  "notes": ""
}
```

An answer you can't read: stays pending, with no points and no mark.

```json
{
  "question_id": "1.3",
  "observed_kind": "unreadable",
  "observed_answer": "Could be 1 or 7",
  "decision": "pending",
  "awarded_points": null,
  "max_points": 10,
  "verification": {"status": "unreadable", "method": "direct_visual", "image_ref": "slot-0001"},
  "confidence": {"alignment": "high", "reading": "low", "interpretation": "high"},
  "notes": "Still unclear at 3x. Ask the teacher."
}
```

| Field | Values |
|---|---|
| `decision` | `correct`, `partial`, `incorrect`, `pending` |
| `observed_kind` | `written`, `circled`, `checked`, `selected`, `matched`, `drawn`, `blank`, `unreadable`, `not_inspected` |
| `verification.status` | `visually_verified`, `unreadable`, `low_confidence`, `not_inspected` |
| `verification.method` | `direct_visual`, or `teacher_override` with a `teacher_statement` |
| `confidence.*` | `high`, `medium`, `low`. Any `low` requires pending. |

Rules the validator enforces:

- `correct` awards full points, `incorrect` awards 0, and `partial` falls strictly
  between. `pending` must be `null`.
- A grade must be `visually_verified` and must cite a ref from `render` for that
  student and that page.
- A blank answer is `incorrect` with `observed_kind: "blank"` and a description.
- Every question needs an entry. A missing one blocks the build rather than counting
  as zero.
- Don't write totals. Python computes them. An optional `declared_total` on a student
  is checked against the arithmetic, and blocks the build if it disagrees.

Student fields: `student_order`, `name`, `number`, `source_pages`, `answers`, and
optionally `stamp_zone`, `notes`, `declared_total`. `name` and `number` are
`{"status": "read", "value": "..."}`, `{"status": "unreadable"}` or
`{"status": "not_provided"}`. A guess isn't permitted.

Optional on an answer: `mark` (`{"x_pct", "y_pct"}`) to place that mark by hand. It
must stay within the answer region.

## page_map.json

`propose-map` creates this. Each slot is one printable page, in print order:

```json
{
  "slot": 1, "kind": "scan", "student_order": 1, "page_in_packet": 1, "template_page": 1,
  "physical_sheet": 1, "side": "front", "source_pdf": "class2.pdf", "source_page": 3,
  "scan_rotation": 0, "rotation_status": "visually_confirmed",
  "content_offset_pct": {"dx": 0, "dy": 0}, "page_width_pt": 595.28, "page_height_pt": 841.89
}
```

- `kind: "blank_filler"` holds a duplex back with no scan: `source_pdf` and `source_page`
  are null, and the output page stays empty.
- `acknowledged_duplicates: [[3, 9]]` at the top level accepts two identical scans that
  someone checked are truly separate sheets.
