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
CLEAR = [
    ("Fix pushy CTA", "AI Fix"),
    ("Fix English in payment confirmation (aftersales)", "AI Fix"),
    ("Fix AI inventing child names", "AI Fix"),
    ("Fix AI hallucinating phone", "AI Fix"),
    ("output currently overall too long", "AI Fix"),
    ("API error after greeting", "AI Fix"),
    ("Wrong pricing for Omnia Bundling with Reina", "AI Fix"),
    ("Repetitive main info on going schedule", "AI Fix"),
    ("Integrate with their Product API", "PRD Change"),
    ("register payment success tool", "PRD Change"),
    ("Implement gcal integration", "PRD Change"),
]


def test_clear_cases():
    for feedback, expected in CLEAR:
        got = classify(feedback)
        assert got.category == expected, (
            f"{feedback!r}: expected {expected}, got {got.category} "
            f"(score={got.score}, matched={got.matched})"
        )


def test_confirmation_noun_does_not_trigger_monitoring():
    # The 'confirmation' trap: this must be AI Fix, never Monitoring/Confirmation.
    got = classify("Fix English in payment confirmation")
    assert got.category == "AI Fix"


def test_api_bug_is_not_prd_change():
    # 'API' alone must not pull a behaviour bug into PRD Change.
    assert classify("API error after greeting").category == "AI Fix"


def test_empty_is_unclassifiable():
    got = classify("")
    assert got.category is None
    assert got.confidence == "low"


def test_no_signal_falls_back_to_other_low():
    got = classify("asdfqwer zxcv")
    assert got.category == "Other"
    assert got.confidence == "low"


def test_trace_signal_nudges_ai_fix():
    # A neutral string that otherwise scores nothing tips to AI Fix with a trace.
    base = classify("update the thing", has_trace=False)
    traced = classify("update the thing", has_trace=True)
    assert traced.category == "AI Fix"
    assert traced.score > base.score


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
