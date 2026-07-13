"""/metrics/* — JSON straight off the SQL views. Same shapes as labor_analytics.db,
so the Chart.js dashboard binds with fetch() instead of embedded data.

HARD RULE: hours / volume / counts only. No view here exposes a dollar figure, and
per-person endpoints are MIX-only (v_by_fde_type) — never raw time-to-close or an
efficiency ratio, and never a leaderboard.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from . import db

router = APIRouter(prefix="/metrics", tags=["metrics"])

# endpoint slug -> view name. Whitelist only; never interpolate user input into SQL.
_VIEWS = {
    "by-client-type": "v_by_client_type",
    "by-week-type": "v_by_week_type",
    "by-fde-type": "v_by_fde_type",
    "backlog": "v_backlog_client_status",
    "qa-failed-open": "v_qa_failed_open",
    "recurrence": "v_recurrence",
    "clients": "v_clients",
    "data-quality": "v_data_quality",
    "catalog": "metric_catalog",
    # flow analytics (db/06) — calendar-span proxies, counts only
    "throughput": "v_flow_throughput_weekly",
    "backlog-aging": "v_flow_backlog_aging",
    "cycle-time": "v_flow_cycle_time_client",
    "cycle-time-priority": "v_flow_cycle_time_priority",
    "priority-age": "v_flow_priority_age",
    "arrival-dow": "v_flow_arrival_dow",
    # change-type classifier coverage (db/04, Kennard)
    "change-type-coverage": "v_change_type_coverage",
    # catalog items unblocked by real data (db/07) — proxies labelled as such
    "fde-stage-mix": "v_fde_stage_mix",
    "time-to-autopilot": "v_time_to_autopilot",
    "volume-by-phase": "v_volume_by_phase_week",
    "sl-capacity": "v_sl_capacity",
    "sl-capacity-by-sl": "v_sl_capacity_by_sl",
    "recent-tickets": "v_recent_tickets",
}


@router.get("/{slug}")
async def get_metric(slug: str):
    view = _VIEWS.get(slug)
    if view is None:
        raise HTTPException(404, f"unknown metric '{slug}'. known: {sorted(_VIEWS)}")
    # Demo/"for now" mode: if a snapshot table (snap_<slug>) has been loaded — e.g.
    # from labor_analytics.db's real 606-ticket aggregates — serve it instead of the
    # live view. Drop the snap_ tables to fall back to the live architecture. The
    # relation name is derived from the whitelisted slug, never from user input.
    snap = "snap_" + slug.replace("-", "_")
    hit = await db.fetchrow("SELECT to_regclass($1) AS r", f"public.{snap}")
    relation = snap if hit and hit["r"] else view
    return await db.fetch(f"SELECT * FROM {relation}")


@router.get("")
async def list_metrics():
    return {"metrics": sorted(_VIEWS), "catalog": await db.fetch("SELECT * FROM metric_catalog")}
