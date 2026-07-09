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
CREATE OR REPLACE VIEW v_volume_by_phase_week AS
SELECT
  to_char(t.reported_date, 'IYYY-IW') AS iso_week,
  COALESCE(c.phase, 'No phase')       AS phase,
  COUNT(*)                            AS tickets
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
WHERE t.reported_date IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2;

-- SL capacity proxy: which clients are hot right now and how fast tickets get
-- picked up. tickets_per_week = 28-day inflow / 4; median_triage_days =
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
