"""Notion write-back via outbox — queued locally, flushed on the worker's cadence.

Two kinds of write-back:
  * status_nudge         — a start-press moved a ticket to In Progress locally; the
                           record of truth should eventually catch up.
  * active_hours_rollup  — a summary number for a read-only "Active Hours" property
                           on the ticket, updated at most once per rollup cycle. Raw
                           intervals themselves NEVER go to Notion (hard design rule);
                           this is a per-ticket total only, so we don't turn a
                           high-frequency event stream into page edits that hammer
                           the rate limit and pollute last_edited_time.

SAFETY: while settings.notion_write_enabled is False (the default), flush_once()
sends NOTHING — rows stay 'pending' and the job only reports queue depth. Flipping
the switch later drains the backlog gradually (small batches, spaced calls, 429-safe).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from .. import db
from ..config import settings

log = logging.getLogger("writeback")

_FLUSH_BATCH = 10          # small batches per tick — Notion 429s aggressively
_CALL_SPACING_SECONDS = 1  # pause between PATCHes within a batch
_MAX_ATTEMPTS = 8


# --- enqueue -----------------------------------------------------------------

async def enqueue_status_nudge(conn, ticket_id: str, pressed_at: datetime) -> None:
    """Queue the In-Progress catch-up for a start-press. Runs on the toggle's own
    connection/transaction so the queue entry commits atomically with the interval."""
    payload = {"status": "In Progress", "pressed_at": pressed_at.isoformat()}
    await _upsert_pending(conn, ticket_id, "status_nudge", payload)


async def enqueue_rollups() -> int:
    """Compute per-ticket active-hour totals and queue an update wherever the total
    changed since the last enqueue/send. Returns how many were (re)queued."""
    rows = await db.fetch(
        "SELECT ah.ticket_id, round(ah.active_hours::numeric, 2) AS hours "
        "FROM v_ticket_active_hours ah"
    )
    pool = await db.get_pool()
    queued = 0
    async with pool.acquire() as conn:
        for r in rows:
            last = await conn.fetchrow(
                "SELECT payload->>'hours' AS hours FROM notion_outbox "
                "WHERE ticket_id = $1 AND kind = 'active_hours_rollup' "
                "ORDER BY created_at DESC LIMIT 1",
                r["ticket_id"],
            )
            if last and last["hours"] == str(r["hours"]):
                continue  # unchanged since last queue/send
            await _upsert_pending(conn, r["ticket_id"], "active_hours_rollup",
                                  {"hours": float(r["hours"])})
            queued += 1
    return queued


async def _upsert_pending(conn, ticket_id: str, kind: str, payload: dict) -> None:
    # At most one pending row per (ticket, kind); a re-enqueue refreshes the payload.
    await conn.execute(
        "INSERT INTO notion_outbox (ticket_id, kind, payload) "
        "VALUES ($1, $2, $3::jsonb) "
        "ON CONFLICT (ticket_id, kind) WHERE status = 'pending' "
        "DO UPDATE SET payload = EXCLUDED.payload, created_at = now()",
        ticket_id, kind, json.dumps(payload),
    )


# --- flush -------------------------------------------------------------------

async def flush_once() -> dict:
    pending = await db.fetchrow(
        "SELECT count(*) AS n FROM notion_outbox WHERE status = 'pending'"
    )
    n_pending = pending["n"] if pending else 0

    # THE GATE. Writes stay off until both are explicitly configured.
    if not settings.notion_write_enabled or not settings.notion_token:
        return {"writes_enabled": False, "pending": n_pending, "sent": 0,
                "at": datetime.now(timezone.utc).isoformat()}

    batch = await db.fetch(
        "SELECT id, ticket_id, kind, payload FROM notion_outbox "
        "WHERE status = 'pending' AND attempts < $1 "
        "ORDER BY created_at LIMIT $2",
        _MAX_ATTEMPTS, _FLUSH_BATCH,
    )
    sent = errors = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for row in batch:
            try:
                await _send(client, row)
                await db.execute(
                    "UPDATE notion_outbox SET status='sent', sent_at=now(), "
                    "attempts=attempts+1 WHERE id=$1", row["id"])
                sent += 1
            except Exception as e:  # includes 429s — row retries next tick
                await db.execute(
                    "UPDATE notion_outbox SET attempts=attempts+1, last_error=$2 "
                    "WHERE id=$1", row["id"], str(e)[:500])
                errors += 1
                log.warning("outbox %s failed: %s", row["id"], e)
            await asyncio.sleep(_CALL_SPACING_SECONDS)
    return {"writes_enabled": True, "pending": n_pending, "sent": sent,
            "errors": errors, "at": datetime.now(timezone.utc).isoformat()}


async def _send(client: httpx.AsyncClient, row) -> None:
    payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"])
    headers = {
        "Authorization": f"Bearer {settings.notion_token}",
        "Notion-Version": settings.notion_version,
        "Content-Type": "application/json",
    }
    page_url = f"{settings.notion_api_base}/pages/{row['ticket_id']}"

    if row["kind"] == "status_nudge":
        # Status is a SELECT property on the live ticket DB (schema fetch confirmed).
        props = {"Status": {"select": {"name": payload["status"]}}}
        # Idempotency: only set Moved-to-In-Progress if Notion doesn't have one —
        # never overwrite a real first-touch timestamp.
        resp = await client.get(page_url, headers=headers)
        resp.raise_for_status()
        existing = (resp.json().get("properties", {})
                    .get("Moved to In Progress", {}).get("date"))
        if not existing:
            props["Moved to In Progress"] = {"date": {"start": payload["pressed_at"]}}
    elif row["kind"] == "active_hours_rollup":
        props = {settings.notion_active_hours_prop: {"number": payload["hours"]}}
    else:
        raise ValueError(f"unknown outbox kind: {row['kind']}")

    resp = await client.patch(page_url, headers=headers, json={"properties": props})
    resp.raise_for_status()


async def run_once() -> dict:
    """Worker entrypoint: refresh rollup queue, then (maybe) flush."""
    queued = await enqueue_rollups()
    result = await flush_once()
    result["rollups_queued"] = queued
    return result
