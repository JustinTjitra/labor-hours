"""FastAPI app: metrics JSON, ingest endpoints, the who's-working-now SSE stream,
and the static dashboard.

Freshness tiers:
  * /metrics/*        -> poll every 60s from the dashboard (near-real-time tier).
  * /stream/working   -> SSE, the only live-push surface ("who's working now").
"""
from __future__ import annotations

import asyncio
import base64
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .capacity import router as capacity_router
from .config import settings
from .metrics import router as metrics_router
from .routes_ingest import router as ingest_router

_STATIC = Path(__file__).resolve().parent.parent / "dashboard"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.get_pool()          # warm the pool
    yield
    await db.close_pool()


app = FastAPI(title="Labor Hours MVP", version="0.1.0", lifespan=lifespan)


# Routes that carry their own auth and must stay reachable by external services
# that can't send Basic auth: the Notion button (path token) and the Slack slash
# command (request signature). /healthz is the load-balancer probe.
_BASIC_AUTH_EXEMPT_PREFIXES = ("/healthz", "/notion/button", "/slack/on")


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    """Gate every route behind HTTP Basic when a password is configured, except
    webhook endpoints with their own auth. Open in local dev (no password)."""
    exempt = request.url.path.startswith(_BASIC_AUTH_EXEMPT_PREFIXES)
    if settings.dashboard_password and not exempt:
        ok = False
        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(header[6:]).decode().partition(":")
                ok = (secrets.compare_digest(user, settings.dashboard_user)
                      and secrets.compare_digest(pw, settings.dashboard_password))
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="labor-hours"'})
    return await call_next(request)


# capacity_router first: its static /metrics/capacity-recurrence path must win over
# the metrics_router /metrics/{slug} catch-all (FastAPI matches in registration order).
app.include_router(capacity_router)
app.include_router(metrics_router)
app.include_router(ingest_router)


@app.get("/stream/working")
async def stream_working():
    """Server-Sent Events: the anonymized open-interval panel, pushed every 5s."""
    async def gen():
        while True:
            rows = await db.fetch("SELECT * FROM v_who_working_now")
            yield f"data: {json.dumps(rows, default=str)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(gen(), media_type="text/event-stream")


# Serve the dashboard (the existing Chart.js HTML, rewired to fetch() the API).
if _STATIC.exists():
    app.mount("/dashboard", StaticFiles(directory=str(_STATIC), html=True), name="dashboard")


@app.get("/")
async def root():
    index = _STATIC / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"service": "labor-hours-mvp", "dashboard": "/dashboard", "metrics": "/metrics"}
