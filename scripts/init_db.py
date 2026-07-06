"""Apply db/01_schema.sql, 02_seed.sql, 03_views.sql in order.

Use for a Postgres you didn't bootstrap via docker-compose (compose runs these
automatically on first init). Idempotent: schema/seed/views all use IF NOT EXISTS /
CREATE OR REPLACE / ON CONFLICT.

    python scripts/init_db.py
"""
import asyncio
import os
import sys
from pathlib import Path

import asyncpg

DB_DIR = Path(__file__).resolve().parent.parent / "db"
FILES = ["01_schema.sql", "02_seed.sql", "03_views.sql"]


async def main():
    dsn = os.environ.get("DATABASE_URL", "postgresql://labor:labor@localhost:5432/labor")
    conn = await asyncpg.connect(dsn=dsn)
    try:
        for name in FILES:
            sql = (DB_DIR / name).read_text()
            print(f"applying {name} ...", file=sys.stderr)
            await conn.execute(sql)
        print("done.", file=sys.stderr)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
