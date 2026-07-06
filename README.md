# Labor Hours MVP — Covena AI

Near-real-time active-time tracking + analytics for FDEs / SLs. Notion stays the
ticket system of record; this is the separate metrics store (Postgres) that serves a
custom Chart.js dashboard.

**Hard rules (from the design):** hours / volume / counts only — *never* dollars.
No per-person rankings or leaderboards — per-FDE/SL views are task-type/stage **mix**
only, and identities are anonymized (FDE-A…F). Intervals are the real-time layer and
are **never routed through Notion**.

## Architecture

```
Slack /on cmd · Portal ▶ button ──► FastAPI ingest ──► Postgres
Notion ticket DB + Clients DB    ──► sync worker (2-min incremental) ──►  tables: intervals, tickets,
Features table                                                            ticket_transitions, blocked_events,
Portal/Eden Flow convo counts    ──► hourly job ──►                       clients, features, conversations_daily
                                        ▼
                            SQL views — one per metric (db/03_views.sql)
                                        ▼
                            FastAPI /metrics/* JSON ──► Chart.js dashboard (60s refresh;
                            SSE only for the "who's working now" panel)
```

## Layout

| Path | What |
|------|------|
| `db/01_schema.sql` | Tables — the raw event streams the views aggregate. |
| `db/02_seed.sql` | FDE anonymization map, expanded Change Type taxonomy, the 22-metric catalog. |
| `db/03_views.sql` | One view per metric, **shapes identical to `labor_analytics.db`**. |
| `app/ingest/intervals.py` | The `/on` toggle logic (one open interval/person, auto-stop, In-Progress nudge). |
| `app/workers/notion_sync.py` | 2-min incremental Notion → Postgres; appends `ticket_transitions`; opens `blocked_events`. |
| `app/workers/auto_closer.py` | Idle / EOD-Jakarta / status-left interval closers (flag `auto_closed`). |
| `app/workers/microview.py` | 1-in-5 sampler over auto-closed intervals (Gemini step stubbed). |
| `app/metrics.py` | `GET /metrics/<slug>` straight off the views. |
| `app/routes_ingest.py` | `POST /slack/on`, `POST /interval/toggle`, `POST /notion-webhook`. |
| `app/main.py` | App wiring + `GET /stream/working` (SSE) + static dashboard. |
| `dashboard/index.html` | The Chart.js dashboard, rewired to `fetch()` the API. |

## Run it (local)

```bash
cp .env.example .env          # add NOTION_TOKEN / SLACK_* to pull real data
docker compose up --build     # db seeds 01→02→03 on first init; api :8000; worker syncs
open http://localhost:8000/   # dashboard (empty until the worker syncs / intervals accrue)
```

Without Docker: point `DATABASE_URL` at any Postgres, then

```bash
pip install -r requirements.txt
python scripts/init_db.py                       # apply schema + seed + views
uvicorn app.main:app --reload                   # API + dashboard
python -m app.worker                            # sync + cron jobs (separate process)
```

`/metrics` lists every endpoint. `/metrics/catalog` returns the 22-metric spec with
each metric's status (COMPUTED / PROXY / PARTIAL / READY / BLOCKED) and what it needs.

## Status of the metrics (why most start as PROXY/BLOCKED)

The prototype pull found only 17.7% In-Progress-timestamp coverage and 41% untyped
Change Type, so calendar-span proxies are all that's computable pre-instrumentation.
`active_hours` fills in as the `/on` toggle produces intervals. `db/02_seed.sql`'s
`metric_catalog` is the authoritative list of what each metric still needs — it maps
1:1 to the six instrumentation gaps.

## Notion write-back (built, OFF by default)

Start-press status nudges and per-ticket "Active Hours" rollups queue in the
`notion_outbox` table (`app/workers/notion_writeback.py`). While
`NOTION_WRITE_ENABLED=false` (the default) **nothing is ever sent to Notion** — the
flush job only reports queue depth. To enable later: create the "Active Hours"
number property on the ticket DB, set `NOTION_WRITE_ENABLED=true` + `NOTION_TOKEN`,
and the backlog drains in small 429-safe batches. Raw intervals never go to Notion.

## What's stubbed (needs real credentials / decisions)

- **Notion property names** in `notion_sync.py` — verified against the live schema
  (2026-07-05): names match; Status is a `select` whose review option is `👀 REVIEW`.
- **Slack blocked-by reply handler** — prompt is sent; the reply→`blocked_events.cause`
  writer (Events API) is a later step.
- **Portal/Eden Flow conversation export** — `conversations.py::fetch_counts`.
- **Micro View capture + Gemini File API** — `microview.py` selects candidates only.
- **Employee Database join** — FDE guest IDs → real names / Slack IDs.

## Open decisions owed by Harvey

- Owner for Features-table entry at ship time.
- Consent framing rollout to the team.
- Sensitive-client list (`clients.sensitive`) for Micro View exclusion.
