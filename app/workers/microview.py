"""Micro View sampler (cron). The screen-recording calibration layer that sits ON
TOP of intervals — a sampled check, never a replacement.

Selection rules (session_handoff_mvp.md):
  * 1-in-N sampling (default 1-in-5).
  * Sensitive clients excluded by default (clients.sensitive).
  * Target auto_closed intervals (the low-confidence ones) and new task categories.

This stub selects candidates and logs them; the Gemini File API upload/analysis
of the recording is wired later. No recording is captured here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import db
from ..config import settings


async def select_candidates() -> list[dict]:
    return await db.fetch(
        "SELECT i.id, i.ticket_id, i.person_user_id, i.started_at, i.ended_at "
        "FROM intervals i "
        "JOIN tickets t ON t.id = i.ticket_id "
        "LEFT JOIN clients c ON c.id = t.client_id "
        "WHERE i.auto_closed = TRUE "
        "AND COALESCE(c.sensitive, FALSE) = FALSE "
        "AND i.id % $1 = 0 "  # 1-in-N deterministic sample
        "AND i.created_at > now() - interval '1 day'",
        settings.microview_sample_rate,
    )


async def run_once() -> dict:
    candidates = await select_candidates()
    # TODO: enqueue each candidate for Micro View capture + Gemini File API analysis.
    return {"sampled": len(candidates), "at": datetime.now(timezone.utc).isoformat()}
