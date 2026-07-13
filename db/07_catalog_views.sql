-- ===========================================================================
-- 07_catalog_views.sql  (ADDITIVE — catalog items now unblocked by real data)
--
-- Four views for metric-catalog entries that need no new instrumentation:
--   * per-FDE STAGE mix (complement of the existing task-type mix; open tickets,
--     allocation view — never a ranking or a speed metric)
--   * time-to-Autopilot per client (phase dates from Master Clients DB)
--   * weekly volume by client phase — the volume PROXY for the hours-per-phase
--     decay curve until intervals accrue
--   * SL capacity proxy — recent inflow per hot client x median triage span
-- Guardrails as ever: counts and calendar spans only, clearly proxy-labelled.
-- ===========================================================================

-- Per-FDE stage mix: where each person's OPEN tickets currently sit.
CREATE OR REPLACE VIEW v_fde_stage_mix AS
SELECT
  COALESCE(m.label, 'Unassigned') AS fde,
  COALESCE(t.status, 'No status') AS status,
  COUNT(*)                        AS tickets
FROM tickets t
LEFT JOIN fde_map m ON m.notion_user_id = t.pic_user_id
WHERE t.status IS DISTINCT FROM 'Done'
  AND t.pic_user_id IS NOT NULL
GROUP BY 1, 2;

-- Time-to-Autopilot: days from scoping to each phase gate, clients with dates.
CREATE OR REPLACE VIEW v_time_to_autopilot AS
SELECT
  name                        AS client,
  phase,
  scoping_date,
  days_scoping_to_copilot,
  days_scoping_to_autopilot
FROM v_clients
WHERE scoping_date IS NOT NULL
  AND (actual_copilot_date IS NOT NULL OR actual_autopilot_date IS NOT NULL)
ORDER BY scoping_date;

-- Weekly ticket volume by client phase — the PROXY decay curve. CAVEAT: joins
-- the client's CURRENT phase (phase history isn't stored), so a client promoted
-- last week recolors its whole history. Good enough to spot "Stable client
-- still generating Copilot-level volume"; the hours version replaces this
-- once intervals accrue.
DROP VIEW IF EXISTS v_volume_by_phase_week;  -- reshaped 2026-07-09 (iso_week -> week_start/label)
CREATE VIEW v_volume_by_phase_week AS
SELECT
  date_trunc('week', t.reported_date)::date               AS week_start,
  to_char(date_trunc('week', t.reported_date), 'DD Mon')  AS week_label,
  COALESCE(c.phase, 'No phase')                           AS phase,
  COUNT(*)                                                AS tickets
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
WHERE t.reported_date IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY 1, 3;

-- SL capacity, per Service Lead: each SL's book of clients and the triage load
-- flowing into it. The catalog item is "tickets/day per hot client x triage-and-
-- spec time" — inflow and triage span are real; the spec-time multiplier awaits
-- actual timing data (intervals on SL work), so this surfaces the components
-- rather than faking the product. hot_clients = clients averaging >= 2/week
-- over the last 28 days. SLs come from clients.sl_user_id (Master Clients DB);
-- unmapped guest ids display as a short-id label until named in fde_map.
CREATE OR REPLACE VIEW v_sl_capacity_by_sl AS
WITH per_client AS (
  SELECT client_id,
         COUNT(*) FILTER (WHERE reported_date >= now() - interval '28 days') AS n28,
         COUNT(*) FILTER (WHERE status IS DISTINCT FROM 'Done')              AS open_n
  FROM tickets
  WHERE client_id IS NOT NULL
  GROUP BY client_id
),
triage AS (
  SELECT c.sl_user_id,
         COUNT(*) AS triage_samples,
         ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY
             EXTRACT(EPOCH FROM (t.moved_to_in_progress - t.reported_date)) / 86400.0
           )::numeric, 1) AS median_triage_days
  FROM tickets t
  JOIN clients c ON c.id = t.client_id
  WHERE c.sl_user_id IS NOT NULL
    AND t.moved_to_in_progress IS NOT NULL
    AND t.moved_to_in_progress >= t.reported_date
  GROUP BY c.sl_user_id
)
SELECT
  COALESCE(m.label, 'SL ' || left(c.sl_user_id, 8) || '…') AS sl,
  COUNT(c.id)                                              AS clients_covered,
  COUNT(c.id) FILTER (WHERE COALESCE(pc.n28, 0) >= 8)      AS hot_clients,
  ROUND(SUM(COALESCE(pc.n28, 0)) / 28.0, 1)                AS tickets_per_day,
  SUM(COALESCE(pc.open_n, 0))                              AS open_backlog,
  MAX(tr.median_triage_days)                               AS median_triage_days,
  MAX(tr.triage_samples)                                   AS triage_samples
FROM clients c
LEFT JOIN fde_map m   ON m.notion_user_id = c.sl_user_id
LEFT JOIN per_client pc ON pc.client_id = c.id
LEFT JOIN triage tr   ON tr.sl_user_id = c.sl_user_id
WHERE c.sl_user_id IS NOT NULL
GROUP BY 1
ORDER BY tickets_per_day DESC;

-- Hot clients right now (client-level companion): how fast tickets get picked
-- up. tickets_per_week = 28-day inflow / 4; median_triage_days =
-- reported -> moved-to-In-Progress calendar span (only ~18% of tickets carry
-- the stamp — treat as indicative, the column says how many).
CREATE OR REPLACE VIEW v_sl_capacity AS
SELECT
  c.name AS client,
  ROUND(COUNT(*) FILTER (WHERE t.reported_date >= now() - interval '28 days') / 4.0, 1)
    AS tickets_per_week,
  COUNT(*) FILTER (WHERE t.status IS DISTINCT FROM 'Done')       AS open_backlog,
  COUNT(*) FILTER (WHERE t.moved_to_in_progress IS NOT NULL
                     AND t.moved_to_in_progress >= t.reported_date) AS triage_samples,
  ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY
      EXTRACT(EPOCH FROM (t.moved_to_in_progress - t.reported_date)) / 86400.0)
      FILTER (WHERE t.moved_to_in_progress IS NOT NULL
                AND t.moved_to_in_progress >= t.reported_date))::numeric, 1)
    AS median_triage_days
FROM tickets t
JOIN clients c ON c.id = t.client_id
GROUP BY c.name
HAVING COUNT(*) FILTER (WHERE t.reported_date >= now() - interval '28 days') > 0
ORDER BY tickets_per_week DESC;

-- Latest tickets: the 10 most recently created (auto_number is Notion's
-- monotonically increasing ID, so it is creation order even when reported_date
-- is backfilled). Powers the "Latest tickets" strip near the top of the page.
CREATE OR REPLACE VIEW v_recent_tickets AS
SELECT
  t.auto_number                          AS num,
  t.feedback                             AS feedback,
  c.name                                 AS client,
  t.status                               AS status,
  t.priority                             AS priority,
  COALESCE(t.change_type, 'Untyped')     AS change_type,
  COALESCE(m.label, '—')                 AS pic,
  to_char(t.reported_date, 'DD Mon')     AS reported
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
LEFT JOIN fde_map m ON m.notion_user_id = t.pic_user_id
ORDER BY t.auto_number DESC NULLS LAST
LIMIT 10;
