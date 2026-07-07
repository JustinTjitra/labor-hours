"""Apply every db/*.sql in order (01 schema, 02 seed, 03 views, ...).

Used as the deploy pre-step so a fresh managed Postgres comes up with the schema,
views, and seeds. Idempotent — safe on every deploy (schema IF NOT EXISTS, seed
ON CONFLICT, views CREATE OR REPLACE).

The 90_sample_snapshot.sql demo overlay is SKIPPED by default: its snap_* tables
shadow the live views (app/metrics.py serves snap_<slug> when present), and it is
DROP + recreate, so applying it on every deploy would keep resurrecting stale demo
aggregates on top of real ticket data. Set APPLY_SAMPLE_SNAPSHOT=1 to include it
(demo/empty-DB mode), or use scripts/load_sample_snapshot.py locally.

    python scripts/apply_all_sql.py
"""
import asyncio
import os
import sys
from pathlib import Path

import asyncpg

DB_DIR = Path(__file__).resolve().parent.parent / "db"


async def main():
    dsn = os.environ.get("DATABASE_URL", "postgresql://labor:labor@127.0.0.1:5433/labor")
    dsn = dsn.replace("postgres://", "postgresql://", 1)  # Render/Heroku form
    conn = await asyncpg.connect(dsn=dsn)
    try:
        include_snapshot = os.environ.get("APPLY_SAMPLE_SNAPSHOT") == "1"
        for path in sorted(DB_DIR.glob("*.sql")):
            if path.name.startswith("90_") and not include_snapshot:
                print(f"skipping {path.name} (demo overlay; APPLY_SAMPLE_SNAPSHOT=1 to include)",
                      file=sys.stderr)
                continue
            print(f"applying {path.name} ...", file=sys.stderr)
            await conn.execute(path.read_text())
        print("all SQL applied.", file=sys.stderr)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
