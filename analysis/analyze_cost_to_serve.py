"""Cost-to-serve index + over/undercharge overlay.

The index (severity x rework weighted effort per client) answers the PRD's
headline question: how expensive is each client to serve, beyond naive ticket
counts. Ranking alone is useful; add your price list and it flags who you're
over/undercharging.

    # Index only (no prices needed):
    python analyze_cost_to_serve.py --csv tickets.csv

    # Emit a price template to fill in (client, monthly_price):
    python analyze_cost_to_serve.py --csv tickets.csv --write-price-template prices.csv

    # Overlay prices to flag over/undercharging:
    python analyze_cost_to_serve.py --csv tickets.csv --prices prices.csv

Over/undercharge logic is share-based and needs no calibration: compare each
client's share of total effort against its share of total revenue. Effort share
well above revenue share = undercharged (you do a big slice of the work for a
small slice of the pay). Dollars stay here in the CLI, never on the shared
dashboard (the design forbids dollars there).
"""
from __future__ import annotations

import argparse
import csv

from build_dashboard import cost_to_serve, load, clean_client


def write_template(rows, path):
    clients = sorted({clean_client(r.get("Client Page")) for r in rows if clean_client(r.get("Client Page"))})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["client", "monthly_price"])
        for c in clients:
            w.writerow([c, ""])
    print(f"wrote {path} with {len(clients)} clients — fill in monthly_price and re-run with --prices")


def read_prices(path):
    prices = {}
    for row in csv.DictReader(open(path, newline="", encoding="utf-8")):
        v = (row.get("monthly_price") or "").strip().replace(",", "")
        if v:
            try:
                prices[row["client"].strip()] = float(v)
            except ValueError:
                pass
    return prices


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default="tickets.csv")
    ap.add_argument("--prices", help="CSV of client,monthly_price to flag over/undercharge")
    ap.add_argument("--write-price-template", metavar="PATH", help="write a blank price template and exit")
    ap.add_argument("--min-tickets", type=int, default=5)
    args = ap.parse_args()

    rows = load(args.csv)
    if args.write_price_template:
        write_template(rows, args.write_price_template)
        return

    cts = [c for c in cost_to_serve(rows) if c["tickets"] >= args.min_tickets]
    total_effort = sum(c["effort"] for c in cts)

    if not args.prices:
        print(f"{'client':16}{'tix':>5}{'effort':>8}{'eff/tix':>8}{'crit+high':>10}{'effort%':>9}")
        for c in cts:
            print(f"{c['client'][:16]:16}{c['tickets']:5}{c['effort']:8}{c['eff_per_ticket']:8}"
                  f"{int(c['crit_high_share']*100):9}%{100*c['effort']/total_effort:8.1f}%")
        print("\nNo prices given. Add --prices prices.csv (template: --write-price-template prices.csv) "
              "to flag over/undercharging.")
        return

    prices = read_prices(args.prices)
    priced = [c for c in cts if c["client"] in prices]
    total_price = sum(prices[c["client"]] for c in priced)
    print(f"{'client':16}{'effort%':>9}{'revenue%':>10}{'ratio':>7}  flag")
    rowsout = []
    for c in priced:
        es = c["effort"] / total_effort if total_effort else 0
        rs = prices[c["client"]] / total_price if total_price else 0
        ratio = es / rs if rs else float("inf")
        flag = "UNDERCHARGED" if ratio >= 1.2 else "overcharged" if ratio <= 0.8 else "ok"
        rowsout.append((ratio, c["client"], es, rs, flag))
    for ratio, cl, es, rs, flag in sorted(rowsout, key=lambda x: -x[0]):
        rr = f"{ratio:.2f}" if ratio != float("inf") else "inf"
        print(f"{cl[:16]:16}{100*es:8.1f}%{100*rs:9.1f}%{rr:>7}  {flag}")
    print("\nratio = effort share / revenue share. >=1.2 undercharged, <=0.8 overcharged.")


if __name__ == "__main__":
    main()
