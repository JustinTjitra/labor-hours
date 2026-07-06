"""Interval auto-closer (cron). Closes open intervals that the human never
stopped, so active-hours don't run away overnight.

Three closers, all flagged auto_closed=true / confidence='low' — these are the
rows Micro View sampling targets to calibrate:
  * idle   — open longer than idle_timeout_seconds (~2h) with no newer activity.
  * eod    — still open past Asia/Jakarta EOD hour.
  * status_left — the ticket left In Progress (someone moved it to REVIEW/Done),
                  so whoever had it open is no longer working it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .. import db
from ..config import settings

_JAKARTA = ZoneInfo("Asia/Jakarta")


async def close_idle() -> int:
    res = await db.execute(
        "UPDATE intervals SET ended_at = now(), auto_closed = TRUE, "
        "confidence = 'low', close_reason = 'idle' "
        "WHERE ended_at IS NULL "
        "AND now() - started_at > make_interval(secs => $1)",
        settings.idle_timeout_seconds,
    )
    return _count(res)


async def close_status_left() -> int:
    res = await db.execute(
        "UPDATE intervals i SET ended_at = now(), auto_closed = TRUE, "
        "confidence = 'low', close_reason = 'status_left' "
        "FROM tickets t "
        "WHERE i.ticket_id = t.id AND i.ended_at IS NULL "
        "AND t.status IS DISTINCT FROM 'In Progress'"
    )
    return _count(res)


async def close_eod() -> int:
    now_jkt = datetime.now(_JAKARTA)
    if now_jkt.hour < settings.jakarta_eod_hour:
        return 0
    res = await db.execute(
        "UPDATE intervals SET ended_at = now(), auto_closed = TRUE, "
        "confidence = 'low', close_reason = 'eod' WHERE ended_at IS NULL"
    )
    return _count(res)


async def run_once() -> dict:
    return {
        "status_left": await close_status_left(),
        "idle": await close_idle(),
        "eod": await close_eod(),
        "at": datetime.now(timezone.utc).isoformat(),
    }


def _count(status: str) -> int:
    # asyncpg returns e.g. "UPDATE 3"
    try:
        return int(status.split()[-1])
    except (ValueError, IndexError):
        return 0
