"""Unit tests for the change-type classifier's pure core.

No DB, no network, stdlib only — run with:  python -m pytest tests/ -q
(or plain `python tests/test_change_type_classifier.py`). Cases are drawn from
real Feedback titles in the Client Feedback Master DB.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workers.change_type_classifier import classify, TAXONOMY  # noqa: E402


# (feedback, expected_category) — clear-cut cases we commit to.
# Taxonomy revised 2026-07-09: the classifier proposes only the four
# issue-nature buckets (Tool / Behavioral / Flow / Data Processing).
CLEAR = [
    ("API error after greeting", "Tool Issue"),
    ("Register New patient doesn't save patientId", "Tool Issue"),
    ("Pickup date time column doesn't save date", "Tool Issue"),
    ("Change wording of kapan bisanya", "Behavioral Issue"),
    ("Intro message is too long", "Behavioral Issue"),
    ("Nudge too aggressively in follow ups", "Behavioral Issue"),
    ("Too many emojis in replies", "Behavioral Issue"),
    ("shouldn't escalate", "Flow Issue"),
    ("Falsely escalated to customer service", "Flow Issue"),
    ("Didn't ask for whatsapp number", "Flow Issue"),
    ("Hallucinated available slots", "Data Processing"),
    ("Fix AI hallucinating phone", "Data Processing"),
    ("Wrong Date, 8th June is Monday not Sunday", "Data Processing"),
]


def test_clear_cases():
    for feedback, expected in CLEAR:
        got = classify(feedback)
        assert got.category == expected, (
            f"{feedback!r}: expected {expected}, got {got.category} "
            f"(score={got.score}, matched={got.matched})"
        )


def test_wording_beats_checkout_stage():
    # "wording of payment confirmation": Behavioral (wording=3) must win over
    # Flow (payment=2 + confirmation=1) — taxonomy order breaks the tie.
    got = classify("Change wording of payment confirmation")
    assert got.category == "Behavioral Issue"


def test_tool_malfunction_beats_flow_stage():
    # A registration-stage ticket about a SAVE failure is a Tool Issue.
    assert classify("Register New patient doesn't save patientId").category == "Tool Issue"


def test_empty_is_unclassifiable():
    got = classify("")
    assert got.category is None
    assert got.confidence == "low"


def test_no_signal_falls_back_to_other_low():
    got = classify("asdfqwer zxcv")
    assert got.category == "Other"
    assert got.confidence == "low"


def test_trace_flag_is_a_noop():
    # has_trace used to nudge the human "AI Fix" label; since the taxonomy
    # revision the classifier only proposes issue-nature buckets, so no effect.
    base = classify("Hallucinated available slots", has_trace=False)
    traced = classify("Hallucinated available slots", has_trace=True)
    assert traced.category == base.category
    assert traced.score == base.score


def test_every_category_is_in_taxonomy():
    for feedback, _ in CLEAR:
        got = classify(feedback)
        assert got.category in TAXONOMY


def test_confidence_values_are_valid():
    for feedback, _ in CLEAR:
        assert classify(feedback).confidence in {"high", "medium", "low"}


if __name__ == "__main__":
    # Lightweight runner so this works without pytest installed.
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{'ALL PASSED' if not failures else f'{failures} FAILED'}")
    sys.exit(1 if failures else 0)
