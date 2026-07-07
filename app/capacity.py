"""/metrics/capacity-recurrence — Kennard's capacity + recurrence analytics, served
LIVE off the Postgres ticket store instead of a baked CSV.

Kennard's original `analysis/build_dashboard.py` computes four things that plain SQL
can't (concept-based recurrence clustering, effort-weighted cost-to-serve, per-FDE
allocation donuts, key-person risk). Rather than re-implement — and drift from — that
logic in SQL, we pull the live ticket rows into the exact dict shape his `compute()`
expects and call it unchanged. The concept map, effort weights, and recurrence rules
therefore stay single-sourced in his file: edit there, both surfaces update.

Names: rows are labelled through `fde_map` (real names this session, per the handoff),
so this defaults to real names. `?anon=1` falls back to FDE-A/B/C for a shareable view.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter, Query

from . import db

router = APIRouter(prefix="/metrics", tags=["capacity"])

# Load Kennard's analyzer by file path — `analysis/` is a scripts dir, not a package.
# Importing the module (pure stdlib, no side effects at import) keeps the concept map
# and compute() as the single source of truth for both the static and live dashboards.
_BD_PATH = Path(__file__).resolve().parent.parent / "analysis" / "build_dashboard.py"
_spec = importlib.util.spec_from_file_location("kennard_build_dashboard", _BD_PATH)
build_dashboard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_dashboard)

# Map live ticket columns -> the CSV header names compute()/cost_to_serve() read.
# One row per ticket; PIC is the resolved fde_map label (blank if unmapped/unassigned),
# which compute() treats exactly like the CSV's single-name PIC cell.
_ROWS_SQL = """
SELECT
  COALESCE(c.name, '')     AS "Client Page",
  COALESCE(m.label, '')    AS "PIC",
  COALESCE(t.feedback, '') AS "Feedback",
  COALESCE(t.status, '')   AS "Status",
  COALESCE(t.priority, '') AS "Priority"
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
LEFT JOIN fde_map m ON m.notion_user_id = t.pic_user_id
"""


@router.get("/capacity-recurrence")
async def capacity_recurrence(anon: bool = Query(False, description="anonymize FDE names")):
    """Full DATA payload for Kennard's dashboard, computed from the live ticket store.

    Same JSON shape his baked HTML used (by_fde / by_client / recurrence / groups /
    cost_to_serve / totals) so the page binds with a fetch() and nothing else changes.
    """
    rows = await db.fetch(_ROWS_SQL)
    # Drop the empty-string Client Page the same way an empty CSV cell would be dropped;
    # compute() already guards on falsy client, but this keeps `totals` honest.
    return build_dashboard.compute(rows, anonymize=anon)
