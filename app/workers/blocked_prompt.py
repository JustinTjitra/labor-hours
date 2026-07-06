"""Blocked-by prompt (gap #1). On a Blocked transition, ask the SL to name the
cause so blocked_events.cause can be filled. Blocked-by discipline is SL-owned,
enforced at triage."""
from __future__ import annotations

from .. import db, slack_client

# TODO: route to the ticket's SL DM once the Employee Database maps user ids to
# Slack ids. Until then, post to a triage channel configured out-of-band.
_TRIAGE_CHANNEL = "#labor-hours-triage"


async def prompt_cause(ticket_id: str) -> None:
    ticket = await db.fetchrow(
        "SELECT t.feedback, c.name AS client FROM tickets t "
        "LEFT JOIN clients c ON c.id = t.client_id WHERE t.id = $1",
        ticket_id,
    )
    if not ticket:
        return
    text = (
        f":no_entry: *Ticket blocked* — {ticket['client'] or 'unknown client'}: "
        f"{ticket['feedback']}\nSL: what's the blocked-by cause? "
        f"Reply to record it against this episode."
    )
    await slack_client.post_message(_TRIAGE_CHANNEL, text)
    # The reply handler (Slack Events API, wired in a later step) writes the cause:
    #   UPDATE blocked_events SET cause = $1 WHERE ticket_id = $2 AND exited_at IS NULL
