"""Run the change-type classifier.

Three modes:

  # See it work with zero setup — classifies a built-in sample, no DB needed:
  python scripts/run_change_type_classifier.py --demo

  # Against a real DB, show proposals WITHOUT writing anything:
  python scripts/run_change_type_classifier.py --dry-run

  # Against a real DB, write proposals into change_type_inferences:
  python scripts/run_change_type_classifier.py
  python scripts/run_change_type_classifier.py --min-confidence medium

--dry-run and the live run need DATABASE_URL set and the 04 migration applied.
--demo needs nothing.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workers.change_type_classifier import classify  # noqa: E402

# Real Feedback titles from the Client Feedback Master DB, for --demo.
_SAMPLE = [
    "Fix pushy CTA",
    "Fix English in payment confirmation (aftersales)",
    "register payment success tool",
    "output currently overall too long",
    "Fix AI inventing child names",
    "Fix AI hallucinating phone",
    "API error after greeting",
    "Integrate with their Product API",
    "Wrong pricing for Omnia Bundling with Reina",
    "No brochure sent on first greeting",
    "complex case should escalate",
    "missing salutation",
]


def _print_row(feedback: str, r) -> None:
    cat = r.category or "(none)"
    print(f"  [{r.confidence:<6}] {cat:<24} <- {feedback!r}")
    if r.matched:
        print(f"           why: {r.rule}")


def demo() -> None:
    print("DEMO — rule classifier over sample Feedback (no DB):\n")
    for fb in _SAMPLE:
        _print_row(fb, classify(fb))


async def dry_run() -> None:
    from app import db  # noqa: E402
    rows = await db.fetch(
        "SELECT id, feedback FROM tickets "
        "WHERE change_type IS NULL AND feedback IS NOT NULL AND feedback <> '' "
        "ORDER BY id"
    )
    print(f"DRY RUN — {len(rows)} untyped tickets, proposals below (nothing written):\n")
    for row in rows:
        _print_row(row["feedback"], classify(row["feedback"]))
    await db.close_pool()


async def live(min_confidence: str) -> None:
    from app.workers.change_type_classifier import run_once
    from app import db
    result = await run_once(min_confidence=min_confidence)
    print(f"WROTE proposals: {result}")
    await db.close_pool()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true", help="classify a built-in sample, no DB")
    ap.add_argument("--dry-run", action="store_true", help="classify real tickets, write nothing")
    ap.add_argument("--min-confidence", default="low", choices=["low", "medium", "high"],
                    help="lowest confidence to persist on a live run (default: low)")
    args = ap.parse_args()

    if args.demo:
        demo()
    elif args.dry_run:
        asyncio.run(dry_run())
    else:
        asyncio.run(live(args.min_confidence))


if __name__ == "__main__":
    main()
