-- Labor Hours MVP — Postgres schema
-- Mirrors the analytic shapes prototyped in labor_analytics.db (SQLite) but stores
-- the raw event streams the views aggregate from. Notion remains the ticket system
-- of record; this store is the separate metrics layer.
--
-- Design invariants (from session_handoff_mvp.md — do not violate):
--   * Hours/volume/count metrics only. NEVER store or expose dollar figures.
--   * intervals are the real-time active-time layer and are NEVER routed through Notion.
--   * Story Points are dead; active-time intervals replace them.
--   * ticket_transitions append every status change (reopens are first-class events,
--     dates are never overwritten).

-- ---------------------------------------------------------------------------
-- clients — mirror of Master Clients DB (near-real-time sync target)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clients (
  id                     TEXT PRIMARY KEY,           -- Notion page id
  name                   TEXT NOT NULL,
  phase                  TEXT,                        -- Not started/Development/Copilot/Autopilot/Stable
  alive                  BOOLEAN,
  scoping_date           DATE,
  actual_copilot_date    DATE,
  actual_autopilot_date  DATE,
  fde_user_id            TEXT,                        -- Notion person id (anonymized on output)
  sl_user_id             TEXT,
  sensitive              BOOLEAN NOT NULL DEFAULT FALSE, -- excluded from Micro View sampling by default
  last_edited_time       TIMESTAMPTZ,                 -- incremental-sync cursor
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- tickets — mirror of Client Feedback Master DB (source of record stays Notion)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tickets (
  id                    TEXT PRIMARY KEY,             -- Notion page id
  auto_number           INTEGER,                      -- Notion auto-increment ID
  feedback              TEXT,                         -- title
  status                TEXT,                         -- Not Started/In Progress/Blocked/REVIEW/QA Failed/Done
  change_type           TEXT,                         -- AI Fix / PRD Change / expanded taxonomy / NULL(=Untyped)
  priority              TEXT,
  phase                 TEXT,
  pic_user_id           TEXT,                         -- person responsible (PIC)
  qa_pic_user_id        TEXT,
  reported_by_user_id   TEXT,
  client_id             TEXT REFERENCES clients(id),
  reported_date         TIMESTAMPTZ,
  moved_to_in_progress  TIMESTAMPTZ,
  moved_to_review       TIMESTAMPTZ,
  moved_to_done         TIMESTAMPTZ,
  status_last_updated   TIMESTAMPTZ,
  due_date              TIMESTAMPTZ,
  reopened_from_id      TEXT REFERENCES tickets(id),  -- gap #3: "reopened from" self-relation
  last_edited_time      TIMESTAMPTZ,                  -- incremental-sync cursor
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tickets_client_idx ON tickets(client_id);
CREATE INDEX IF NOT EXISTS tickets_status_idx ON tickets(status);
CREATE INDEX IF NOT EXISTS tickets_last_edited_idx ON tickets(last_edited_time);

-- ---------------------------------------------------------------------------
-- ticket_transitions — every status change, appended (gap #3)
-- Makes reopens (Done->In Progress, ->QA Failed) first-class instead of
-- silently overwriting the moved_to_* date columns.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket_transitions (
  id            BIGSERIAL PRIMARY KEY,
  ticket_id     TEXT NOT NULL REFERENCES tickets(id),
  from_status   TEXT,
  to_status     TEXT NOT NULL,
  is_backward   BOOLEAN NOT NULL DEFAULT FALSE,       -- regression (reopen / QA fail)
  actor_user_id TEXT,
  occurred_at   TIMESTAMPTZ NOT NULL,
  source        TEXT NOT NULL DEFAULT 'notion-sync',  -- notion-sync | notion-webhook | interval-toggle
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS transitions_ticket_idx ON ticket_transitions(ticket_id, occurred_at);

-- ---------------------------------------------------------------------------
-- intervals — REAL-TIME active-time capture. Never routed through Notion.
-- Single toggle model: one open interval per person; starting ticket B
-- auto-stops ticket A. auto_closed rows are lower-confidence and are the
-- targets for Micro View sampling.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intervals (
  id             BIGSERIAL PRIMARY KEY,
  ticket_id      TEXT NOT NULL REFERENCES tickets(id),
  person_user_id TEXT NOT NULL,
  started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at       TIMESTAMPTZ,
  auto_closed    BOOLEAN NOT NULL DEFAULT FALSE,
  close_reason   TEXT,                                -- toggle | switch | idle | eod | status_left
  source         TEXT NOT NULL DEFAULT 'slack',       -- slack | portal | emoji
  confidence     TEXT NOT NULL DEFAULT 'high',        -- high | low (auto_closed)
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (ended_at IS NULL OR ended_at >= started_at)
);
-- Enforce "one open interval per person" at the DB level.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_interval_per_person
  ON intervals (person_user_id) WHERE ended_at IS NULL;
CREATE INDEX IF NOT EXISTS intervals_ticket_idx ON intervals(ticket_id);

-- ---------------------------------------------------------------------------
-- blocked_events — per-episode blocked-by tracking (gap #1)
-- cause is SL-owned, prompted via Slack bot on a Blocked transition.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blocked_events (
  id          BIGSERIAL PRIMARY KEY,
  ticket_id   TEXT NOT NULL REFERENCES tickets(id),
  cause       TEXT,
  entered_at  TIMESTAMPTZ NOT NULL,
  exited_at   TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS blocked_ticket_idx ON blocked_events(ticket_id);

-- ---------------------------------------------------------------------------
-- features — ship dates for before/after feature metrics (gap #2)
-- Needs an owner at ship time (open decision owed by Harvey).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS features (
  id                BIGSERIAL PRIMARY KEY,
  name              TEXT NOT NULL,
  product           TEXT,
  targeted_category TEXT,                             -- task category the feature should reduce
  ship_date         DATE NOT NULL,
  owner_user_id     TEXT,
  notion_page_id    TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- conversations_daily — client conversation volume from Portal/Eden Flow (gap #5)
-- Daily/weekly counts only.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations_daily (
  client_id     TEXT NOT NULL REFERENCES clients(id),
  day           DATE NOT NULL,
  conversations INTEGER NOT NULL,
  source        TEXT NOT NULL DEFAULT 'portal',
  PRIMARY KEY (client_id, day)
);

-- ---------------------------------------------------------------------------
-- fde_map — anonymization mapping (no per-person leaderboards in outputs)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fde_map (
  label          TEXT PRIMARY KEY,   -- FDE-A .. FDE-F, SL-Harvey
  notion_user_id TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- change_types — expanded taxonomy reference (build-order step 1)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS change_types (
  name       TEXT PRIMARY KEY,
  sort_order INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- notion_outbox — queued Notion write-backs. Intervals NEVER wait on Notion;
-- anything that should eventually reach Notion is enqueued here and flushed by
-- the worker on its own cadence (429-safe, retryable). While the master switch
-- NOTION_WRITE_ENABLED is false (the default), rows accumulate as 'pending' and
-- NOTHING is ever sent.
-- kinds: status_nudge (start-press moved ticket to In Progress)
--        active_hours_rollup (summary number for a read-only Notion property)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notion_outbox (
  id          BIGSERIAL PRIMARY KEY,
  ticket_id   TEXT NOT NULL REFERENCES tickets(id),
  kind        TEXT NOT NULL,                        -- status_nudge | active_hours_rollup
  payload     JSONB NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending',      -- pending | sent | error
  attempts    INTEGER NOT NULL DEFAULT 0,
  last_error  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at     TIMESTAMPTZ
);
-- Coalesce: at most one pending row per (ticket, kind); re-enqueues update payload.
CREATE UNIQUE INDEX IF NOT EXISTS outbox_pending_once
  ON notion_outbox (ticket_id, kind) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS outbox_status_idx ON notion_outbox (status, created_at);

-- ---------------------------------------------------------------------------
-- metric_catalog — the authoritative 22-metric spec (seeded static)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metric_catalog (
  scope       TEXT,
  metric      TEXT,
  status      TEXT,
  where_in_db TEXT,
  needs       TEXT
);
