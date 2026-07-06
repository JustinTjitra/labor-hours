"""Ingest endpoints: the Slack /on toggle, a direct interval toggle (for the future
Portal button), and the Notion webhook (near-real-time push alternative to polling)."""
from __future__ import annotations

import re
import secrets as _secrets

from fastapi import APIRouter, Form, HTTPException, Request, Response

from . import db, slack_client
from .config import settings
from .ingest import intervals
from .workers import notion_sync

router = APIRouter(tags=["ingest"])


# --- Slack slash command: /on <ticket-id> ------------------------------------
@router.post("/slack/on")
async def slack_on(
    request: Request,
    text: str = Form(""),
    user_id: str = Form(...),
):
    raw = await request.body()
    ts = request.headers.get("X-Slack-Request-Timestamp", "")
    sig = request.headers.get("X-Slack-Signature", "")
    if not slack_client.verify_signature(ts, sig, raw):
        raise HTTPException(401, "bad slack signature")

    ticket_id = text.strip()
    if not ticket_id:
        return {"response_type": "ephemeral", "text": "Usage: `/on <ticket-id>`"}

    try:
        result = await intervals.toggle(ticket_id, user_id, source="slack")
    except intervals.UnknownTicket:
        return {"response_type": "ephemeral",
                "text": f"Ticket `{ticket_id}` not found (has it synced from Notion yet?)."}

    if result["action"] == "stopped":
        msg = f":pause_button: Stopped work on `{ticket_id}`."
    else:
        parts = [f":arrow_forward: Working on `{ticket_id}`."]
        if result.get("prev_ticket_id"):
            parts.append(f"Auto-stopped `{result['prev_ticket_id']}`.")
        if result.get("moved_to_in_progress"):
            parts.append("Moved it to *In Progress*.")
        msg = " ".join(parts)
    return {"response_type": "ephemeral", "text": msg}


# --- Direct toggle (Portal button, later) ------------------------------------
@router.post("/interval/toggle")
async def interval_toggle(ticket_id: str, person_user_id: str, source: str = "portal"):
    try:
        return await intervals.toggle(ticket_id, person_user_id, source=source)
    except intervals.UnknownTicket as e:
        raise HTTPException(404, str(e))


# --- Notion button: "⏱ Toggle work" button property fires here ---------------
# The interval is attributed to the ticket's PIC (from the synced row), NOT to
# whoever pressed — so the payload only needs to carry the page id.

def _normalize_page_id(raw: str) -> str:
    """Notion page ids appear both dashed and undashed; tickets.id stores dashed."""
    s = raw.strip().lower()
    if re.fullmatch(r"[0-9a-f]{32}", s):
        return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"
    return s


def _extract_page_id(payload: dict) -> str | None:
    """Tolerant unwrap of Notion's button-webhook body. Notion has shipped a few
    payload shapes; accept the common ones plus a bare {ticket_id} for n8n/curl."""
    for path in (("data", "id"), ("page", "id"), ("entity", "id"),
                 ("id",), ("ticket_id",), ("page_id",)):
        node: object = payload
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, str) and node:
            return node
    return None


@router.post("/notion/button/{token}")
@router.post("/notion/button")
async def notion_button(request: Request, token: str = ""):
    if settings.button_webhook_token and not _secrets.compare_digest(
            token, settings.button_webhook_token):
        raise HTTPException(401, "bad webhook token")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(422, "expected a JSON body")

    raw_id = _extract_page_id(payload if isinstance(payload, dict) else {})
    if not raw_id:
        raise HTTPException(422, "no page id found in payload")
    ticket_id = _normalize_page_id(raw_id)

    ticket = await db.fetchrow(
        "SELECT id, pic_user_id FROM tickets WHERE id = $1", ticket_id)
    if ticket is None:
        raise HTTPException(404, f"ticket {ticket_id} not synced yet")
    if not ticket["pic_user_id"]:
        raise HTTPException(422, f"ticket {ticket_id} has no PIC — set one before toggling")

    result = await intervals.toggle(ticket_id, ticket["pic_user_id"], source="notion-button")
    return result


# --- Notion webhook: push alternative to the 2-min poll ----------------------
@router.post("/notion-webhook")
async def notion_webhook(request: Request):
    payload = await request.json()
    # Notion's automation/webhook payload carries the changed page id; the simplest
    # correct handler is to run an incremental sync, which upserts + logs transitions.
    # (A tighter handler could upsert just payload's page — kept simple for the MVP.)
    _ = payload
    result = await notion_sync.run_once()
    return {"synced": result}


# --- health ------------------------------------------------------------------
@router.get("/healthz")
async def healthz():
    await db.fetchrow("SELECT 1 AS ok")
    return Response(status_code=200)
