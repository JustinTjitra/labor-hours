"""Notion -> Postgres incremental sync (build-order step 3).

Near-real-time tier: poll the ticket + clients databases every ~2 min, filtered by
last_edited_time so we upsert only what changed. Engineers batch-update statuses at
EOD, so this tier is deliberately eventually-consistent — the real-time signal lives
in the intervals stream, never here.

Every status change is appended to ticket_transitions (reopens first-class); a
regression (Done/REVIEW -> earlier stage, or -> QA Failed) is flagged is_backward and,
on a Blocked transition, a blocked_events episode is opened and the SL is prompted for
the blocked-by cause.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import db, notion
from ..config import settings

# Field-name -> our column map for the Client Feedback Master DB. Adjust the
# left-hand strings to the exact Notion property names if they differ.
_STATUS_ORDER = ["Not Started", "In Progress", "Blocked", "REVIEW", "QA Failed", "Done"]


def _is_backward(from_status: str | None, to_status: str) -> bool:
    if from_status is None or to_status not in _STATUS_ORDER:
        return False
    if to_status == "QA Failed":
        return True  # a QA fail is always a regression
    if from_status not in _STATUS_ORDER:
        return False
    return _STATUS_ORDER.index(to_status) < _STATUS_ORDER.index(from_status)


async def _sync_cursor(name: str) -> datetime | None:
    row = await db.fetchrow(
        "SELECT max(last_edited_time) AS m FROM tickets" if name == "tickets"
        else "SELECT max(last_edited_time) AS m FROM clients"
    )
    return row["m"] if row and row["m"] else None


async def sync_clients() -> int:
    since = await _sync_cursor("clients")
    n = 0
    async for page in notion.iter_pages(settings.notion_clients_db_id, since=since):
        p = page["properties"]
        await db.execute(
            """INSERT INTO clients (id, name, phase, alive, scoping_date,
                 actual_copilot_date, actual_autopilot_date, fde_user_id, sl_user_id,
                 last_edited_time, updated_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10, now())
               ON CONFLICT (id) DO UPDATE SET
                 name=EXCLUDED.name, phase=EXCLUDED.phase, alive=EXCLUDED.alive,
                 scoping_date=EXCLUDED.scoping_date,
                 actual_copilot_date=EXCLUDED.actual_copilot_date,
                 actual_autopilot_date=EXCLUDED.actual_autopilot_date,
                 fde_user_id=EXCLUDED.fde_user_id, sl_user_id=EXCLUDED.sl_user_id,
                 last_edited_time=EXCLUDED.last_edited_time, updated_at=now()""",
            page["id"],
            notion.prop_title(p, "Client Name"),
            notion.prop_select(p, "Phase"),
            (notion.prop_select(p, "Alive?") or "").lower() in ("alive", "yes", "true"),
            _d(notion.prop_date(p, "Scoping Date")),
            _d(notion.prop_date(p, "Actual Copilot")),
            _d(notion.prop_date(p, "Actual Autopilot")),
            notion.prop_person_id(p, "FDE"),
            notion.prop_person_id(p, "SL"),
            notion.prop_created_or_edited(page, "last_edited_time"),
        )
        n += 1
    return n


async def sync_tickets() -> int:
    since = await _sync_cursor("tickets")
    n = 0
    async for page in notion.iter_pages(settings.notion_ticket_db_id, since=since):
        p = page["properties"]
        ticket_id = page["id"]
        new_status = notion.prop_status(p, "Status")

        prev = await db.fetchrow("SELECT status FROM tickets WHERE id = $1", ticket_id)
        old_status = prev["status"] if prev else None

        await db.execute(
            """INSERT INTO tickets (id, auto_number, feedback, status, change_type,
                 priority, phase, pic_user_id, qa_pic_user_id, reported_by_user_id,
                 client_id, reported_date, moved_to_in_progress, moved_to_review,
                 moved_to_done, status_last_updated, due_date, last_edited_time, updated_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18, now())
               ON CONFLICT (id) DO UPDATE SET
                 auto_number=EXCLUDED.auto_number, feedback=EXCLUDED.feedback,
                 status=EXCLUDED.status, change_type=EXCLUDED.change_type,
                 priority=EXCLUDED.priority, phase=EXCLUDED.phase,
                 pic_user_id=EXCLUDED.pic_user_id, qa_pic_user_id=EXCLUDED.qa_pic_user_id,
                 reported_by_user_id=EXCLUDED.reported_by_user_id, client_id=EXCLUDED.client_id,
                 reported_date=EXCLUDED.reported_date,
                 moved_to_in_progress=COALESCE(tickets.moved_to_in_progress, EXCLUDED.moved_to_in_progress),
                 moved_to_review=EXCLUDED.moved_to_review, moved_to_done=EXCLUDED.moved_to_done,
                 status_last_updated=EXCLUDED.status_last_updated, due_date=EXCLUDED.due_date,
                 last_edited_time=EXCLUDED.last_edited_time, updated_at=now()""",
            ticket_id,
            _int(notion.prop_number(p, "ID")),
            notion.prop_title(p, "Feedback"),
            new_status,
            notion.prop_select(p, "Change Type"),
            notion.prop_select(p, "Priority"),
            notion.prop_select(p, "Phase"),
            notion.prop_person_id(p, "PIC"),
            notion.prop_person_id(p, "QA PIC"),
            notion.prop_person_id(p, "Reported By"),
            notion.prop_relation_id(p, "Client Page"),
            notion.prop_date(p, "Reported Date"),
            notion.prop_date(p, "Moved to In Progress"),
            notion.prop_date(p, "Moved to Review"),
            notion.prop_date(p, "Moved to Done"),
            notion.prop_date(p, "Status Last Updated"),
            notion.prop_date(p, "Due Date"),
            notion.prop_created_or_edited(page, "last_edited_time"),
        )

        if new_status and new_status != old_status:
            await _record_transition(ticket_id, old_status, new_status)
        n += 1
    return n


async def _record_transition(ticket_id: str, from_status: str | None, to_status: str) -> None:
    backward = _is_backward(from_status, to_status)
    await db.execute(
        "INSERT INTO ticket_transitions "
        "(ticket_id, from_status, to_status, is_backward, occurred_at, source) "
        "VALUES ($1, $2, $3, $4, now(), 'notion-sync')",
        ticket_id, from_status, to_status, backward,
    )

    if to_status == "Blocked":
        # Open a blocked episode and prompt the SL for the cause (gap #1).
        await db.execute(
            "INSERT INTO blocked_events (ticket_id, entered_at) VALUES ($1, now())",
            ticket_id,
        )
        from . import blocked_prompt  # local import to avoid cycle at import time
        await blocked_prompt.prompt_cause(ticket_id)
    elif from_status == "Blocked":
        # Close the most recent open episode.
        await db.execute(
            "UPDATE blocked_events SET exited_at = now() "
            "WHERE id = (SELECT id FROM blocked_events WHERE ticket_id = $1 "
            "AND exited_at IS NULL ORDER BY entered_at DESC LIMIT 1)",
            ticket_id,
        )


async def run_once() -> dict:
    clients = await sync_clients()
    tickets = await sync_tickets()
    return {"clients": clients, "tickets": tickets, "at": datetime.now(timezone.utc).isoformat()}


def _d(dt):
    return dt.date() if dt else None


def _int(n):
    return int(n) if n is not None else None
