"""Capacity concentration — allocation view over the ticket export.

Answers two questions the MVP Dashboard asks, using only reliable, auto-captured
assignment data (PIC x Client), so it does NOT depend on the empty active-hours
column:

  * Per FDE:   how spread is their week, or is it dominated by one client?
  * Per client: is one person carrying it (key-person / bus-factor risk)?

Consistent with the design's no-ranking rule: this measures *distribution*, never
who is faster. People are anonymized to FDE-A, FDE-B, ... by descending load.

Usage:
    python analyze_capacity_concentration.py --csv tickets.csv
    python analyze_capacity_concentration.py --csv tickets.csv --show-names   # reveal map (private)

Concentration is summarized with HHI (Herfindahl index): sum of squared shares,
from ~0 (evenly spread) to 1.0 (everything on one). Rule of thumb: > 0.5 = heavy
concentration; 1.0 = a single client or single person.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict


def clean_client(v: str | None) -> str:
    v = (v or "").strip()
    return v.split(" (http")[0].strip() if v else ""


def split_pics(v: str | None) -> list[str]:
    v = (v or "").strip()
    return [p.strip() for p in v.split(",") if p.strip()] if v else []


def hhi(shares) -> float:
    return round(sum(s * s for s in shares), 3)


def load(csv_path: str):
    rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
    for r in rows:                     # strip a BOM on the first header if present
        if "﻿Feedback" in r:
            r["Feedback"] = r.pop("﻿Feedback")
    return rows


def build(rows):
    """Fractional credit: a ticket with k PICs gives 1/k to each, so shared work
    is not double-counted."""
    pair = defaultdict(float)
    pic_tot = defaultdict(float)
    cli_tot = defaultdict(float)
    for r in rows:
        cl = clean_client(r.get("Client Page"))
        ps = split_pics(r.get("PIC"))
        if not cl or not ps:
            continue
        w = 1.0 / len(ps)
        for p in ps:
            pair[(p, cl)] += w
            pic_tot[p] += w
            cli_tot[cl] += w
    order = sorted(pic_tot, key=lambda p: -pic_tot[p])
    anon = {p: f"FDE-{chr(65 + i)}" for i, p in enumerate(order)}
    return pair, pic_tot, cli_tot, order, anon


def report(rows, show_names: bool, top: int):
    pair, pic_tot, cli_tot, order, anon = build(rows)

    print("=== CAPACITY CONCENTRATION — per FDE (how spread is their week) ===")
    print(f"{'FDE':6} {'tickets':>7} {'clients':>7} {'top-client':>10} {'HHI':>6}  top client")
    for p in order:
        tot = pic_tot[p]
        cls = {c: pair[(p, c)] for c in cli_tot if pair.get((p, c), 0) > 0}
        shares = [v / tot for v in cls.values()]
        tc, tv = max(cls.items(), key=lambda kv: kv[1])
        print(f"{anon[p]:6} {tot:7.1f} {len(cls):7d} {tv/tot:10.0%} {hhi(shares):6}  {tc}")

    print("\n=== KEY-PERSON RISK — per client (is one FDE carrying it) ===")
    print(f"{'client':18} {'tickets':>7} {'FDEs':>5} {'top-FDE':>8} {'HHI':>6}  carried by")
    for cl in sorted(cli_tot, key=lambda c: -cli_tot[c])[:top]:
        tot = cli_tot[cl]
        fs = {p: pair[(p, cl)] for p in pic_tot if pair.get((p, cl), 0) > 0}
        shares = [v / tot for v in fs.values()]
        tp, tv = max(fs.items(), key=lambda kv: kv[1])
        flag = "  <-- single-person" if len(fs) == 1 else ""
        print(f"{cl[:18]:18} {tot:7.1f} {len(fs):5d} {tv/tot:8.0%} {hhi(shares):6}  {anon[tp]}{flag}")

    if show_names:
        print("\n[PRIVATE] anon -> real:", {anon[p]: p for p in order})
    else:
        print("\n(names hidden; run with --show-names to reveal the private map)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default="tickets.csv", help="exported ticket CSV")
    ap.add_argument("--show-names", action="store_true", help="reveal the FDE->name map")
    ap.add_argument("--top", type=int, default=20, help="clients to show (default 20)")
    args = ap.parse_args()
    report(load(args.csv), args.show_names, args.top)


if __name__ == "__main__":
    main()
