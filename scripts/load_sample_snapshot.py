"""Load the real 606-ticket aggregates from labor_analytics.db into Postgres as
`snap_*` snapshot tables, so the dashboard shows real numbers without a Notion pull.

This is a "for now" demo overlay: the metrics API prefers a snap_ table over its live
view when present (see app/metrics.py). To revert to the live architecture, drop the
snap_ tables:  DROP TABLE snap_by_client_type, snap_by_week_type, ... ;

The source .db is AGGREGATED (not raw tickets), so active_hours stays 0 — that number
only comes from the /on interval toggle or a live Notion sync.

Usage:
    python scripts/load_sample_snapshot.py /path/to/labor_analytics.db
"""
import asyncio
import os
import sqlite3
import sys

import asyncpg

# (sqlite source table, snap table, DDL, ordered column list)
SPECS = [
    ("by_client_type", "snap_by_client_type",
     "(client text, change_type text, tickets int, "
     "proxy_avg_days_reported_to_done double precision, "
     "proxy_avg_hours_inprogress_to_done double precision, "
     "proxy_avg_days_queue_reported_to_start double precision, "
     "active_hours double precision default 0)",
     ["client", "change_type", "tickets", "proxy_avg_days_reported_to_done",
      "proxy_avg_hours_inprogress_to_done", "proxy_avg_days_queue_reported_to_start"]),
    ("by_week_type", "snap_by_week_type",
     "(iso_week text, change_type text, tickets int)",
     ["iso_week", "change_type", "tickets"]),
    ("by_fde_type", "snap_by_fde_type",
     "(fde text, change_type text, tickets int, "
     "proxy_avg_days_reported_to_done double precision, "
     "proxy_avg_hours_inprogress_to_done double precision, "
     "active_hours double precision default 0)",
     ["fde", "change_type", "tickets", "proxy_avg_days_reported_to_done",
      "proxy_avg_hours_inprogress_to_done"]),
    ("backlog_client_status", "snap_backlog",
     "(client text, status text, tickets int)",
     ["client", "status", "tickets"]),
    ("qa_failed_open", "snap_qa_failed_open",
     "(client text, feedback text, change_type text, priority text, reported text)",
     ["client", "feedback", "change_type", "priority", "reported"]),
    ("recurrence_examples", "snap_recurrence",
     "(client text, detail text, kind text)",
     ["client", "detail", "kind"]),
    ("clients", "snap_clients",
     "(name text, phase text, alive text, scoping_date text, actual_copilot_date text, "
     "actual_autopilot_date text, days_scoping_to_copilot double precision, "
     "days_scoping_to_autopilot double precision)",
     ["name", "phase", "alive", "scoping_date", "actual_copilot_date",
      "actual_autopilot_date", "days_scoping_to_copilot", "days_scoping_to_autopilot"]),
    ("data_quality", "snap_data_quality",
     "(measure text, value text)",
     ["measure", "value"]),
]


async def main(sqlite_path: str):
    dsn = os.environ.get("DATABASE_URL", "postgresql://labor:labor@127.0.0.1:5433/labor")
    lite = sqlite3.connect(sqlite_path)
    pg = await asyncpg.connect(dsn=dsn)
    try:
        for src, snap, ddl, cols in SPECS:
            rows = lite.execute(f"SELECT {', '.join(cols)} FROM {src}").fetchall()
            await pg.execute(f"DROP TABLE IF EXISTS {snap}")
            await pg.execute(f"CREATE TABLE {snap} {ddl}")
            placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
            await pg.executemany(
                f"INSERT INTO {snap} ({', '.join(cols)}) VALUES ({placeholders})", rows
            )
            print(f"{snap}: {len(rows)} rows", file=sys.stderr)
        print("snapshot loaded — /metrics/* now serves real 606-ticket aggregates.", file=sys.stderr)
    finally:
        await pg.close()
        lite.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/load_sample_snapshot.py /path/to/labor_analytics.db")
    asyncio.run(main(sys.argv[1]))
