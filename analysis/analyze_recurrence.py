"""Recurrence / rework signal over the ticket export.

A client whose tickets quietly repeat is more expensive than its ticket count
suggests: the same problem keeps coming back. This finds that from a static
snapshot two ways, neither of which needs the (empty) active-hours column:

  1. Repeated issues — feedback titles that recur within the same client, matched
     by normalized near-duplicate similarity (so "Language issue" / "Language
     issues" / "Language issue again" collapse into one recurring problem).
  2. QA-Failed count — the current explicit rework signal.

Note: this is the snapshot version. The richer "how many times did a ticket bounce
backward through the pipeline" signal needs Justin's live ticket_transitions log,
which a CSV export does not carry. This approximates it via repeated strings.

Usage:
    python analyze_recurrence.py --csv tickets.csv
    python analyze_recurrence.py --csv tickets.csv --threshold 0.82 --min-tickets 5
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from difflib import SequenceMatcher

_STOP = re.compile(r"\b(again|pls|please|fix|the|a|an|to|of|on|in|for|is|are|be|and)\b")


def clean_client(v: str | None) -> str:
    v = (v or "").strip()
    return v.split(" (http")[0].strip() if v else ""


def norm(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = _STOP.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def load(csv_path: str):
    rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
    for r in rows:
        if "﻿Feedback" in r:
            r["Feedback"] = r.pop("﻿Feedback")
    return rows


def cluster(items: list[str], thr: float):
    """Greedy near-duplicate clustering. Returns [(canonical, [members]), ...]."""
    reps: list[list] = []
    for fb in items:
        n = norm(fb)
        if not n:
            continue
        for rep in reps:
            if SequenceMatcher(None, n, rep[0]).ratio() >= thr:
                rep[1].append(fb)
                break
        else:
            reps.append([n, [fb]])
    return reps


def report(rows, threshold: float, min_tickets: int):
    by_client = defaultdict(list)
    qaf = defaultdict(int)
    tot = defaultdict(int)
    for r in rows:
        cl = clean_client(r.get("Client Page"))
        if not cl:
            continue
        tot[cl] += 1
        fb = (r.get("Feedback") or "").strip()
        if fb:
            by_client[cl].append(fb)
        if (r.get("Status") or "").strip() == "QA Failed":
            qaf[cl] += 1

    print("=== RECURRENCE — repeated/near-duplicate issues within a client ===")
    print(f"{'client':18} {'tickets':>7} {'in-repeat':>9} {'recur%':>7} {'QAfail':>6}")
    clusters_all = []
    for cl in sorted(tot, key=lambda c: -tot[c]):
        reps = cluster(by_client[cl], threshold)
        in_repeat = sum(len(m) for _, m in reps if len(m) > 1)
        rate = in_repeat / tot[cl] if tot[cl] else 0
        for _, m in reps:
            if len(m) >= 2:
                clusters_all.append((len(m), cl, m))
        if tot[cl] >= min_tickets:
            print(f"{cl[:18]:18} {tot[cl]:7d} {in_repeat:9d} {rate:7.0%} {qaf[cl]:6d}")

    print("\n=== TOP REPEATED ISSUE CLUSTERS (the actual recurring problems) ===")
    for size, cl, m in sorted(clusters_all, reverse=True)[:15]:
        print(f"  x{size}  [{cl}]  e.g. {m[0][:60]!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default="tickets.csv")
    ap.add_argument("--threshold", type=float, default=0.82,
                    help="near-duplicate similarity 0-1 (higher = stricter)")
    ap.add_argument("--min-tickets", type=int, default=5,
                    help="only print clients with at least this many tickets")
    args = ap.parse_args()
    report(load(args.csv), args.threshold, args.min_tickets)


if __name__ == "__main__":
    main()
