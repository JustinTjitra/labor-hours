-- ===========================================================================
-- 06_flow_views.sql  (ADDITIVE — flow analytics: aging, cycle time, throughput)
--
-- Views only, no new tables. Unblocked by the full-history import + live sync:
-- reported_date covers ~99% of tickets and moved_to_done ~68% of Done ones, so
-- calendar-span flow metrics are now meaningful. All spans here are PROXIES
-- (wall-clock, not active work time) — label them as such on any surface.
-- Counts and spans only: no dollars, no per-person speed metrics (guardrails).
--
-- This file ALSO redefines the three by-type views from 03_views.sql. Per
-- Harvey (2026-07-09) they surface HUMAN-set Notion types only (AI Fix /
-- PRD Change / Untyped); classifier inferences stay backend-only. See the
-- BY-TYPE VIEWS section below for how to re-enable the inference fallback.
-- ===========================================================================

-- --- THROUGHPUT --------------------------------------------------------------
-- Weekly opened vs closed + net backlog growth. A week can appear with opened=0
-- (only closes) or closed=0, hence the FULL JOIN.
DROP VIEW IF EXISTS v_flow_throughput_weekly;  -- reshaped 2026-07-09 (iso_week -> week_start/label)
CREATE VIEW v_flow_throughput_weekly AS
WITH opened AS (
  SELECT date_trunc('week', reported_date)::date AS week_start, COUNT(*) AS opened
  FROM tickets WHERE reported_date IS NOT NULL GROUP BY 1
),
closed AS (
  SELECT date_trunc('week', moved_to_done)::date AS week_start, COUNT(*) AS closed
  FROM tickets WHERE moved_to_done IS NOT NULL GROUP BY 1
)
SELECT
  COALESCE(o.week_start, c.week_start)                          AS week_start,
  to_char(COALESCE(o.week_start, c.week_start), 'DD Mon')       AS week_label,
  COALESCE(o.opened, 0)                                         AS opened,
  COALESCE(c.closed, 0)                                         AS closed,
  COALESCE(o.opened, 0) - COALESCE(c.closed, 0)                 AS net
FROM opened o
FULL JOIN closed c USING (week_start)
ORDER BY 1;

-- --- BACKLOG AGING -----------------------------------------------------------
-- Open (non-Done) tickets bucketed by age since reported_date, per client.
CREATE OR REPLACE VIEW v_flow_backlog_aging AS
SELECT
  c.name AS client,
  COUNT(*) FILTER (WHERE now() - t.reported_date <  interval '7 days')  AS lt_7d,
  COUNT(*) FILTER (WHERE now() - t.reported_date >= interval '7 days'
                     AND now() - t.reported_date <  interval '30 days') AS d7_30,
  COUNT(*) FILTER (WHERE now() - t.reported_date >= interval '30 days') AS gt_30d,
  COUNT(*)                                                              AS open_tickets,
  ROUND(MAX(EXTRACT(EPOCH FROM (now() - t.reported_date)) / 86400.0))   AS oldest_days
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
WHERE t.status IS DISTINCT FROM 'Done'
  AND t.reported_date IS NOT NULL
  AND c.name IS NOT NULL
GROUP BY c.name
ORDER BY open_tickets DESC;

-- --- CYCLE TIME (calendar-span PROXY) ----------------------------------------
-- Reported -> Done spans for closed tickets that carry both dates. Median + p90,
-- never averages (long tails dominate this data).
CREATE OR REPLACE VIEW v_flow_cycle_time_client AS
SELECT
  c.name AS client,
  COUNT(*) AS done_tickets,
  ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY
        EXTRACT(EPOCH FROM (t.moved_to_done - t.reported_date)) / 86400.0)::numeric, 1) AS median_days,
  ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY
        EXTRACT(EPOCH FROM (t.moved_to_done - t.reported_date)) / 86400.0)::numeric, 1) AS p90_days
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
WHERE t.moved_to_done IS NOT NULL AND t.reported_date IS NOT NULL
  AND t.moved_to_done >= t.reported_date
  AND c.name IS NOT NULL
GROUP BY c.name
HAVING COUNT(*) >= 3          -- a median of 1-2 tickets is noise
ORDER BY median_days DESC;

CREATE OR REPLACE VIEW v_flow_cycle_time_priority AS
SELECT
  COALESCE(t.priority, 'No priority') AS priority,
  COUNT(*) AS done_tickets,
  ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY
        EXTRACT(EPOCH FROM (t.moved_to_done - t.reported_date)) / 86400.0)::numeric, 1) AS median_days,
  ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY
        EXTRACT(EPOCH FROM (t.moved_to_done - t.reported_date)) / 86400.0)::numeric, 1) AS p90_days
FROM tickets t
WHERE t.moved_to_done IS NOT NULL AND t.reported_date IS NOT NULL
  AND t.moved_to_done >= t.reported_date
GROUP BY 1
ORDER BY CASE COALESCE(t.priority, 'No priority')
  WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2
  WHEN 'LOW' THEN 3 ELSE 4 END;

-- --- PRIORITY x AGE ----------------------------------------------------------
-- Oldest still-open CRITICAL/HIGH tickets — the "act on this today" list.
CREATE OR REPLACE VIEW v_flow_priority_age AS
SELECT
  c.name     AS client,
  t.feedback AS feedback,
  t.priority AS priority,
  t.status   AS status,
  ROUND(EXTRACT(EPOCH FROM (now() - t.reported_date)) / 86400.0) AS age_days
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
WHERE t.status IS DISTINCT FROM 'Done'
  AND t.priority IN ('CRITICAL', 'HIGH')
  AND t.reported_date IS NOT NULL
ORDER BY age_days DESC;

-- --- ARRIVAL PATTERN ---------------------------------------------------------
CREATE OR REPLACE VIEW v_flow_arrival_dow AS
SELECT
  to_char(reported_date, 'Dy') AS dow,
  EXTRACT(ISODOW FROM reported_date)::int AS dow_order,
  COUNT(*) AS tickets
FROM tickets
WHERE reported_date IS NOT NULL
GROUP BY 1, 2
ORDER BY 2;

-- --- BY-TYPE VIEWS (human-only types, per Harvey 2026-07-09) ------------------
-- Same names/shapes as 03_views.sql. Inferred categories are NOT surfaced:
-- anything an engineer hasn't typed in Notion displays as 'Untyped'. The
-- classifier still writes change_type_inferences (audit/backend only) — to
-- surface inferences again, restore COALESCE(t.change_type, ci.inferred_type,
-- 'Untyped') with a LEFT JOIN change_type_inferences ci.
CREATE OR REPLACE VIEW v_by_client_type AS
SELECT
  c.name                                                    AS client,
  COALESCE(t.change_type, 'Untyped')      AS change_type,
  COUNT(*)                                                  AS tickets,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_done - t.reported_date)) / 86400.0)       AS proxy_avg_days_reported_to_done,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_done - t.moved_to_in_progress)) / 3600.0) AS proxy_avg_hours_inprogress_to_done,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_in_progress - t.reported_date)) / 86400.0) AS proxy_avg_days_queue_reported_to_start,
  COALESCE(SUM(ah.active_hours), 0)                         AS active_hours
FROM tickets t
LEFT JOIN clients c                  ON c.id = t.client_id
LEFT JOIN v_ticket_active_hours ah   ON ah.ticket_id = t.id
GROUP BY c.name, COALESCE(t.change_type, 'Untyped');

DROP VIEW IF EXISTS v_by_week_type;  -- reshaped 2026-07-09 (iso_week -> week_start/label)
CREATE VIEW v_by_week_type AS
SELECT
  date_trunc('week', t.reported_date)::date                     AS week_start,
  to_char(date_trunc('week', t.reported_date), 'DD Mon')        AS week_label,
  COALESCE(t.change_type, 'Untyped')                            AS change_type,
  COUNT(*)                                                      AS tickets
FROM tickets t
WHERE t.reported_date IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY 1, 3;

CREATE OR REPLACE VIEW v_by_fde_type AS
SELECT
  COALESCE(m.label, 'Unassigned')                       AS fde,
  COALESCE(t.change_type, 'Untyped')  AS change_type,
  COUNT(*)                                              AS tickets,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_done - t.reported_date)) / 86400.0)       AS proxy_avg_days_reported_to_done,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_done - t.moved_to_in_progress)) / 3600.0) AS proxy_avg_hours_inprogress_to_done,
  COALESCE(SUM(ah.active_hours), 0)                     AS active_hours
FROM tickets t
LEFT JOIN fde_map m                  ON m.notion_user_id = t.pic_user_id
LEFT JOIN v_ticket_active_hours ah   ON ah.ticket_id = t.id
GROUP BY COALESCE(m.label, 'Unassigned'), COALESCE(t.change_type, 'Untyped');
