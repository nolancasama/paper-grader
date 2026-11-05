"""Phase 1: the grading schema rejects anything that could turn into a silent wrong grade."""
from fractions import Fraction

import pytest

from papergrader import demo
from papergrader.common import Issues
from papergrader.grading_models import compute_outcome, format_points, parse_grading, parse_page_map, parse_test, to_points


def graded_answer(**changes):
    answer = {
        "question_id": "1.1", "observed_kind": "written", "observed_answer": "3", "decision": "correct", "awarded_points": 10, "max_points": 10,
        "verification": {"status": "visually_verified", "method": "direct_visual", "image_ref": "slot-0001"},
        "confidence": {"alignment": "high", "reading": "high", "interpretation": "high"},
    }
    answer.update(changes)
    return answer


def pending_answer(**changes):
    answer = graded_answer(
        decision="pending", awarded_points=None, observed_kind="unreadable", observed_answer="?",
        verification={"status": "unreadable", "method": "direct_visual", "image_ref": "slot-0001"},
        confidence={"alignment": "high", "reading": "low", "interpretation": "high"},
    )
    answer.update(changes)
    return answer


def grading_with(answer):
    return {
        "schema_version": 1, "class_id": "c", "test_id": "t", "test_version": "v", "rubric_hash": "h", "question_hashes": {},
        "grader": {"type": "chatgpt_visual", "name": "x"},
        "students": [{"student_order": 1, "name": {"status": "unreadable"}, "number": {"status": "unreadable"}, "source_pages": [], "answers": [answer]}],
    }


def codes(answer) -> set:
    issues = Issues()
    parse_grading(grading_with(answer), issues)
    return issues.codes()


def test_a_visually_verified_grade_is_accepted():
    assert codes(graded_answer()) == set()


def test_a_pending_answer_is_accepted():
    assert codes(pending_answer()) == set()


def test_unknown_fields_are_rejected_so_ocr_output_cannot_slip_in():
    assert "schema_unknown_field" in codes(graded_answer(ocr_text="3"))


@pytest.mark.parametrize("method", ["ocr", "tesseract", "pixel_threshold", None])
def test_only_direct_viewing_or_a_teacher_can_establish_a_grade(method):
    answer = graded_answer(verification={"status": "visually_verified", "method": method, "image_ref": "slot-0001"})
    assert "judgment_bad_method" in codes(answer)


def test_a_grade_needs_visual_verification():
    answer = graded_answer(verification={"status": "not_inspected", "method": "direct_visual", "image_ref": "slot-0001"})
    assert "judgment_not_verified" in codes(answer)


def test_a_grade_must_name_the_image_it_came_from():
    answer = graded_answer(verification={"status": "visually_verified", "method": "direct_visual", "image_ref": None})
    assert "judgment_no_image_ref" in codes(answer)


def test_pending_cannot_carry_points_not_even_zero():
    assert "pending_has_points" in codes(pending_answer(awarded_points=0))


def test_a_graded_answer_with_missing_points_is_an_error_not_a_zero():
    assert "judgment_missing_points" in codes(graded_answer(decision="incorrect", awarded_points=None))


def test_an_unreadable_answer_cannot_be_marked_wrong():
    answer = graded_answer(decision="incorrect", awarded_points=0, observed_kind="unreadable")
    assert "judgment_on_unseen_answer" in codes(answer)


def test_low_confidence_must_stay_pending():
    answer = graded_answer(confidence={"alignment": "high", "reading": "low", "interpretation": "high"})
    assert "judgment_low_confidence" in codes(answer)


@pytest.mark.parametrize("decision,points", [("correct", 5), ("incorrect", 3), ("partial", 10), ("partial", 0)])
def test_points_must_agree_with_the_decision(decision, points):
    assert "points_decision_mismatch" in codes(graded_answer(decision=decision, awarded_points=points))


def test_a_blank_must_be_established_by_looking_and_described():
    assert "judgment_no_observation" in codes(graded_answer(decision="incorrect", awarded_points=0, observed_kind="blank", observed_answer=""))
    assert codes(graded_answer(decision="incorrect", awarded_points=0, observed_kind="blank", observed_answer="Answer box is empty")) == set()


def test_a_teacher_override_must_quote_the_teacher():
    answer = graded_answer(verification={"status": "visually_verified", "method": "teacher_override", "image_ref": "slot-0001"})
    assert "override_no_statement" in codes(answer)
    assert codes({**answer, "teacher_statement": "Give the point."}) == set()


def test_a_guessed_identity_is_rejected():
    data = grading_with(graded_answer())
    data["students"][0]["name"] = {"status": "unreadable", "value": "Maybe Tanaka"}
    issues = Issues()
    parse_grading(data, issues)
    assert "schema_bad_value" in issues.codes()


def valid_test() -> dict:
    return {
        "schema_version": 1, "test_id": "t", "test_version": "v", "title": "T", "template_pages": 1, "max_points": 100,
        "references": {
            "blank": {"kind": "scan", "source_pdf": "b.pdf", "sha256": "x", "pages": [1]},
            "key": {"kind": "scan", "source_pdf": "k.pdf", "sha256": "y", "pages": [1]},
            "teacher_confirmation": {"confirmed": True, "confirmed_at": "now", "teacher_statement": "Yes."},
        },
        "rubric_status": "approved", "open_rubric_questions": [],
        "score_box": {"template_page": 1, "x_pct": 70, "y_pct": 5, "w_pct": 11, "h_pct": 5, "denominator_printed": True},
        "stamp_zone": {"template_page": 1, "x_pct": 50, "y_pct": 12, "w_pct": 40, "h_pct": 30},
        "protected_regions": [], "questions": demo.question_table(),
    }


def test_the_synthetic_test_definition_is_valid():
    issues = Issues()
    assert parse_test(valid_test(), issues) is not None
    assert issues.ok, issues.to_json()


def test_rubric_points_must_add_up_to_the_maximum():
    data = valid_test()
    data["max_points"] = 90
    issues = Issues()
    parse_test(data, issues)
    assert "rubric_points_mismatch" in issues.codes()


def test_a_personal_response_question_needs_a_written_rule():
    data = valid_test()
    data["questions"][-1]["rule"] = ""
    issues = Issues()
    parse_test(data, issues)
    assert "rubric_rule_missing" in issues.codes()


def test_a_second_denominator_cannot_be_requested_when_one_is_printed():
    data = valid_test()
    data["score_box"]["append_denominator"] = True
    issues = Issues()
    parse_test(data, issues)
    assert "schema_bad_value" in issues.codes()


def test_a_page_map_slot_needs_its_source_page():
    issues = Issues()
    parse_page_map({
        "schema_version": 1, "class_id": "c", "class_label": "C", "test_id": "t", "test_version": "v", "paper_mode": "simplex", "sources": [],
        "slots": [{"slot": 1, "kind": "scan", "student_order": 1, "page_in_packet": 1, "template_page": 1, "physical_sheet": 1, "side": "front", "source_pdf": None,
                   "source_page": None, "scan_rotation": 0, "rotation_status": "unconfirmed", "page_width_pt": 595, "page_height_pt": 842}],
    }, issues)
    assert "schema_bad_value" in issues.codes()


# ---------------------------------------------------------------------------
# Arithmetic and award thresholds
# ---------------------------------------------------------------------------
def outcome_for(points_by_question):
    """Evaluate fixture judgments through the same code path a real grade takes."""
    issues = Issues()
    test = parse_test(valid_test(), issues)
    answers = []
    for question in test.questions:
        awarded = points_by_question.get(question.id, 10)
        if awarded is None:
            answers.append(pending_answer(question_id=question.id))
        else:
            decision = "correct" if awarded == 10 else ("incorrect" if awarded == 0 else "partial")
            answers.append(graded_answer(question_id=question.id, decision=decision, awarded_points=awarded))
    data = grading_with(answers[0])
    data["students"][0]["answers"] = answers
    grading = parse_grading(data, issues)
    assert issues.ok, issues.to_json()
    return compute_outcome(grading.students[0], test)


def test_a_full_score_earns_the_perfect_award():
    outcome = outcome_for({})
    assert (outcome.total, outcome.award) == (100, "perfect")


def test_exactly_ninety_earns_praise():
    outcome = outcome_for({"1.5": 0})
    assert (outcome.total, outcome.award) == (90, "praise")


def test_just_below_ninety_earns_nothing():
    outcome = outcome_for({"1.5": 0, "1.1": 9.5})
    assert (outcome.total, outcome.award) == (Fraction(179, 2), "none")


def test_ninety_nine_point_five_is_praise_not_perfect():
    outcome = outcome_for({"1.5": 9.5})
    assert (outcome.total, outcome.award) == (Fraction(199, 2), "praise")


def test_any_pending_answer_withholds_the_total_and_the_award():
    outcome = outcome_for({"1.5": None})
    assert (outcome.resolved, outcome.total, outcome.award, outcome.unresolved) == (False, None, "none", ("1.5",))


def test_a_missing_judgment_is_unresolved_never_zero():
    issues = Issues()
    test = parse_test(valid_test(), issues)
    data = grading_with(graded_answer())
    grading = parse_grading(data, issues)
    outcome = compute_outcome(grading.students[0], test)
    assert not outcome.resolved and outcome.total is None and len(outcome.unresolved) == 9


def test_totals_are_exact_not_floating_point():
    assert to_points(0.1) + to_points(0.2) == to_points(0.3)
    assert format_points(Fraction(175, 2)) == "87.5"
    assert format_points(Fraction(90)) == "90"


@pytest.mark.parametrize("bad", [True, None, float("nan"), float("inf"), "abc"])
def test_non_numbers_are_never_treated_as_points(bad):
    assert to_points(bad) is None
