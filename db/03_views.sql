-- SQL views — one per metric, shapes kept identical to labor_analytics.db so the
-- existing Chart.js dashboard can bind to them with fetch() instead of embedded data.
--
-- Each view carries BOTH the timestamp-derived PROXY columns (calendar spans, the
-- only thing computable before instrumentation) AND the real active_hours from the
-- intervals stream. active_hours is 0 until the /on toggle starts producing rows.
-- Notion date values may carry a trailing 'Z'; the sync worker normalizes to
-- timestamptz on write, so the views can assume clean timestamps.

-- Active hours per ticket, summed over all (closed + still-open) intervals.
CREATE OR REPLACE VIEW v_ticket_active_hours AS
SELECT ticket_id,
       SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at)) / 3600.0) AS active_hours,
       SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at)) / 3600.0)
         FILTER (WHERE NOT auto_closed) AS active_hours_high_conf
FROM intervals
GROUP BY ticket_id;

-- by_client_type: (client, change_type, tickets, 3x proxy, active_hours)
CREATE OR REPLACE VIEW v_by_client_type AS
SELECT
  c.name                                    AS client,
  COALESCE(t.change_type, 'Untyped')        AS change_type,
  COUNT(*)                                  AS tickets,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_done - t.reported_date)) / 86400.0)       AS proxy_avg_days_reported_to_done,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_done - t.moved_to_in_progress)) / 3600.0) AS proxy_avg_hours_inprogress_to_done,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_in_progress - t.reported_date)) / 86400.0) AS proxy_avg_days_queue_reported_to_start,
  COALESCE(SUM(ah.active_hours), 0)         AS active_hours
FROM tickets t
LEFT JOIN clients c                 ON c.id = t.client_id
LEFT JOIN v_ticket_active_hours ah  ON ah.ticket_id = t.id
GROUP BY c.name, COALESCE(t.change_type, 'Untyped');

-- by_week_type: week of Reported Date x change_type x tickets. Emits the week
-- START DATE + a "DD Mon" label (2026-07-10: replaced ISO week numbers).
-- MUST stay column-identical to the redefinition in 06_flow_views.sql — a
-- shape mismatch makes CREATE OR REPLACE fail on the second boot (Postgres
-- can't rename/drop view columns), which took the Render service down once.
DROP VIEW IF EXISTS v_by_week_type;
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

-- by_fde_type: anonymized PIC x change_type x tickets (mix only, no ranking).
-- Unmapped PICs surface as 'Unassigned' so the mix stays honest.
CREATE OR REPLACE VIEW v_by_fde_type AS
SELECT
  COALESCE(m.label, 'Unassigned')            AS fde,
  COALESCE(t.change_type, 'Untyped')         AS change_type,
  COUNT(*)                                   AS tickets,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_done - t.reported_date)) / 86400.0)       AS proxy_avg_days_reported_to_done,
  AVG(EXTRACT(EPOCH FROM (t.moved_to_done - t.moved_to_in_progress)) / 3600.0) AS proxy_avg_hours_inprogress_to_done,
  COALESCE(SUM(ah.active_hours), 0)          AS active_hours
FROM tickets t
LEFT JOIN fde_map m                 ON m.notion_user_id = t.pic_user_id
LEFT JOIN v_ticket_active_hours ah  ON ah.ticket_id = t.id
GROUP BY COALESCE(m.label, 'Unassigned'), COALESCE(t.change_type, 'Untyped');

-- backlog_client_status: non-Done tickets by client x status
CREATE OR REPLACE VIEW v_backlog_client_status AS
SELECT c.name AS client, t.status AS status, COUNT(*) AS tickets
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
WHERE t.status IS DISTINCT FROM 'Done'
GROUP BY c.name, t.status
ORDER BY c.name, t.status;

-- qa_failed_open: current QA-Failed snapshot (rework signal)
CREATE OR REPLACE VIEW v_qa_failed_open AS
SELECT
  c.name        AS client,
  t.feedback    AS feedback,
  t.change_type AS change_type,
  t.priority    AS priority,
  to_char(t.reported_date, 'YYYY-MM-DD') AS reported
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
WHERE t.status = 'QA Failed';

-- recurrence: reopened tickets (explicit self-relation) + tickets that regressed
-- (a backward transition was logged). Counts today; hours once intervals exist.
CREATE OR REPLACE VIEW v_recurrence AS
SELECT
  c.name       AS client,
  t.feedback   AS detail,
  CASE WHEN t.reopened_from_id IS NOT NULL THEN 're-filed duplicate'
       ELSE 'recurrence' END AS kind,
  COUNT(tr.id) FILTER (WHERE tr.is_backward) AS backward_transitions
FROM tickets t
LEFT JOIN clients c            ON c.id = t.client_id
LEFT JOIN ticket_transitions tr ON tr.ticket_id = t.id
WHERE t.reopened_from_id IS NOT NULL
   OR EXISTS (SELECT 1 FROM ticket_transitions x WHERE x.ticket_id = t.id AND x.is_backward)
GROUP BY c.name, t.feedback, kind;

-- clients: phase dates + computed days scoping->copilot/autopilot
CREATE OR REPLACE VIEW v_clients AS
SELECT
  name, phase, alive, scoping_date, actual_copilot_date, actual_autopilot_date,
  (actual_copilot_date   - scoping_date) AS days_scoping_to_copilot,
  (actual_autopilot_date - scoping_date) AS days_scoping_to_autopilot
FROM clients;

-- who is working right now — open intervals. Powers the SSE panel. New columns
-- (num/status/priority/change_type) are APPENDED so CREATE OR REPLACE stays valid.
CREATE OR REPLACE VIEW v_who_working_now AS
SELECT
  COALESCE(m.label, 'Unmapped') AS person,
  i.ticket_id,
  t.feedback                    AS ticket,
  c.name                        AS client,
  i.started_at,
  EXTRACT(EPOCH FROM (now() - i.started_at)) / 60.0 AS minutes_open,
  i.source,
  t.auto_number                 AS num,
  t.status                      AS status,
  t.priority                    AS priority,
  COALESCE(t.change_type, 'Untyped') AS change_type
FROM intervals i
LEFT JOIN fde_map m ON m.notion_user_id = i.person_user_id
LEFT JOIN tickets t ON t.id = i.ticket_id
LEFT JOIN clients c ON c.id = t.client_id
WHERE i.ended_at IS NULL
ORDER BY i.started_at;

-- recent_intervals: the latest work sessions (open + closed), newest first.
-- The history companion to v_who_working_now — who worked which ticket and when.
CREATE OR REPLACE VIEW v_recent_intervals AS
SELECT
  COALESCE(m.label, 'Unmapped') AS person,
  t.auto_number                 AS num,
  t.feedback                    AS ticket,
  c.name                        AS client,
  i.started_at,
  i.ended_at,
  ROUND(EXTRACT(EPOCH FROM (COALESCE(i.ended_at, now()) - i.started_at)) / 60.0) AS minutes,
  (i.ended_at IS NULL)          AS is_open,
  i.auto_closed,
  i.close_reason,
  i.source
FROM intervals i
LEFT JOIN fde_map m ON m.notion_user_id = i.person_user_id
LEFT JOIN tickets t ON t.id = i.ticket_id
LEFT JOIN clients c ON c.id = t.client_id
ORDER BY i.started_at DESC
LIMIT 15;

-- data_quality: live coverage/quality gauges (mirror of the SQLite data_quality table)
CREATE OR REPLACE VIEW v_data_quality AS
SELECT * FROM (VALUES
  ('total_tickets',                (SELECT COUNT(*)::text FROM tickets)),
  ('status_done',                  (SELECT COUNT(*)::text FROM tickets WHERE status = 'Done')),
  ('open_backlog',                 (SELECT COUNT(*)::text FROM tickets WHERE status IS DISTINCT FROM 'Done')),
  ('status_qa_failed',             (SELECT COUNT(*)::text FROM tickets WHERE status = 'QA Failed')),
  ('has_moved_to_in_progress_ts',  (SELECT COUNT(*)::text FROM tickets WHERE moved_to_in_progress IS NOT NULL)),
  ('untyped_change_type',          (SELECT COUNT(*)::text FROM tickets WHERE change_type IS NULL)),
  ('tickets_with_intervals',       (SELECT COUNT(DISTINCT ticket_id)::text FROM intervals)),
  ('open_intervals_now',           (SELECT COUNT(*)::text FROM intervals WHERE ended_at IS NULL)),
  ('warning', 'Time figures without interval coverage are stage-timestamp PROXIES (calendar spans), not active work hours.')
) AS q(measure, value);
