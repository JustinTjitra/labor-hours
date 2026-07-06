"""Conversation-volume ingest (gap #5, cron hourly). Pulls per-client daily
conversation counts from Portal / Eden Flow and upserts conversations_daily.
Powers "active hours per 1,000 conversations".

Stubbed: the Portal/Eden Flow export endpoint + auth are not wired yet. Fill in
`fetch_counts` when the source is available; the upsert path is ready.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from .. import db


async def fetch_counts() -> list[tuple[str, date, int]]:
    """Return [(client_id, day, conversations), ...]. TODO: call Portal/Eden Flow."""
    return []


async def run_once() -> dict:
    rows = await fetch_counts()
    for client_id, day, count in rows:
        await db.execute(
            "INSERT INTO conversations_daily (client_id, day, conversations, source) "
            "VALUES ($1, $2, $3, 'portal') "
            "ON CONFLICT (client_id, day) DO UPDATE SET conversations = EXCLUDED.conversations",
            client_id, day, count,
        )
    return {"upserted": len(rows), "at": datetime.now(timezone.utc).isoformat()}
