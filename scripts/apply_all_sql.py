"""Apply every db/*.sql in order (01 schema, 02 seed, 03 views, 90 snapshot).

Used as the deploy pre-step so a fresh managed Postgres comes up with the schema,
views, and the real 606-ticket snapshot already loaded. Idempotent — safe on every
deploy (schema IF NOT EXISTS, seed ON CONFLICT, views CREATE OR REPLACE, snapshot
DROP IF EXISTS + recreate).

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
        for path in sorted(DB_DIR.glob("*.sql")):
            print(f"applying {path.name} ...", file=sys.stderr)
            await conn.execute(path.read_text())
        print("all SQL applied.", file=sys.stderr)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
