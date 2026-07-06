"""Interval capture — the real-time active-time layer. Never routed through Notion.

Decided design (session_handoff_mvp.md):
  * Single toggle ("▶ Working / ⏸"), not two buttons. Engineers only signal
    "what I'm on now" — one press per ticket pickup.
  * One OPEN interval per person: starting ticket B auto-stops ticket A.
  * Validity enforced by automation, not humans: if the ticket is not already
    In Progress when someone starts working it, move it there (a free, correct
    timestamp) rather than trusting a human to have done it.

The whole toggle runs in one transaction so the "one open interval per person"
unique index can never be tripped by a race between the auto-stop and the insert.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import db
from ..workers import notion_writeback

# Statuses from which starting work should nudge the ticket to In Progress.
_NEEDS_MOVE_FROM = {"Not Started", "REVIEW", "QA Failed", "Blocked", None}


async def toggle(ticket_id: str, person_user_id: str, source: str = "slack") -> dict:
    """Toggle work on `ticket_id` for `person_user_id`.

    Returns a small dict describing what happened, suitable for a Slack reply:
      {action: started|stopped, ticket_id, prev_ticket_id?, moved_to_in_progress}
    """
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            ticket = await conn.fetchrow(
                "SELECT id, status, pic_user_id FROM tickets WHERE id = $1", ticket_id
            )
            if ticket is None:
                # We only know tickets the sync worker has seen. Refuse rather than
                # invent a row the metrics layer can't attribute to a client.
                raise UnknownTicket(ticket_id)

            open_iv = await conn.fetchrow(
                "SELECT id, ticket_id FROM intervals "
                "WHERE person_user_id = $1 AND ended_at IS NULL",
                person_user_id,
            )

            # Pressing the ticket you're already on = stop (the ⏸ half of the toggle).
            if open_iv and open_iv["ticket_id"] == ticket_id:
                await conn.execute(
                    "UPDATE intervals SET ended_at = now(), close_reason = 'toggle' WHERE id = $1",
                    open_iv["id"],
                )
                return {"action": "stopped", "ticket_id": ticket_id, "moved_to_in_progress": False}

            # Switching tickets: auto-stop whatever was open first.
            prev_ticket_id = None
            if open_iv:
                prev_ticket_id = open_iv["ticket_id"]
                await conn.execute(
                    "UPDATE intervals SET ended_at = now(), close_reason = 'switch' WHERE id = $1",
                    open_iv["id"],
                )

            await conn.execute(
                "INSERT INTO intervals (ticket_id, person_user_id, source) VALUES ($1, $2, $3)",
                ticket_id,
                person_user_id,
                source,
            )

            # Validity: if the ticket wasn't In Progress, make it so and log the
            # transition. This is the "free correct timestamp" — the press itself
            # is the ground truth that work started.
            moved = False
            if ticket["status"] in _NEEDS_MOVE_FROM or ticket["status"] != "In Progress":
                await _move_to_in_progress(conn, ticket_id, ticket["status"], person_user_id)
                moved = True

            return {
                "action": "started",
                "ticket_id": ticket_id,
                "prev_ticket_id": prev_ticket_id,
                "moved_to_in_progress": moved,
            }


async def _move_to_in_progress(conn, ticket_id: str, from_status, actor_user_id: str) -> None:
    """Local status move + first-class transition row. The Notion write-back is
    queued separately so intervals never block on the Notion API."""
    await conn.execute(
        "UPDATE tickets SET status = 'In Progress', "
        "moved_to_in_progress = COALESCE(moved_to_in_progress, now()), "
        "status_last_updated = now(), updated_at = now() WHERE id = $1",
        ticket_id,
    )
    await conn.execute(
        "INSERT INTO ticket_transitions "
        "(ticket_id, from_status, to_status, is_backward, actor_user_id, occurred_at, source) "
        "VALUES ($1, $2, 'In Progress', FALSE, $3, now(), 'interval-toggle')",
        ticket_id,
        from_status,
        actor_user_id,
    )
    # Queue the Notion catch-up in the outbox (same transaction — commits atomically
    # with the interval). The flush job sends it later, and ONLY once
    # NOTION_WRITE_ENABLED is true; until then it just sits pending locally.
    await notion_writeback.enqueue_status_nudge(
        conn, ticket_id, pressed_at=datetime.now(timezone.utc)
    )


class UnknownTicket(Exception):
    def __init__(self, ticket_id: str):
        super().__init__(f"unknown ticket: {ticket_id}")
        self.ticket_id = ticket_id
