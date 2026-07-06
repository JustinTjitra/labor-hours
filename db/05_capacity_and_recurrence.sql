-- ===========================================================================
-- 05_capacity_and_recurrence.sql  (ADDITIVE — Tim's two client metrics)
--
-- Views only. No changes to Justin's tables or views. Runs after 01/02.
-- People are anonymized through his existing fde_map (label = FDE-A, ...).
-- In the LIVE schema each ticket has a single pic_user_id, so no fractional
-- split is needed here (the Python analyzer handles multi-PIC CSV cells).
-- ===========================================================================

-- --- CAPACITY CONCENTRATION -------------------------------------------------
-- Base grain: anonymized FDE x client ticket counts.
CREATE OR REPLACE VIEW v_capacity_fde_client AS
SELECT
  COALESCE(m.label, 'Unassigned') AS fde,
  c.name                          AS client,
  COUNT(*)                        AS tickets
FROM tickets t
LEFT JOIN fde_map m ON m.notion_user_id = t.pic_user_id
LEFT JOIN clients c ON c.id = t.client_id
WHERE t.pic_user_id IS NOT NULL AND c.name IS NOT NULL
GROUP BY 1, 2;

-- Per FDE: how spread is their week. top_client_share + HHI (0=even, 1=all one).
CREATE OR REPLACE VIEW v_capacity_by_fde AS
WITH b AS (
  SELECT fde, client, tickets,
         SUM(tickets) OVER (PARTITION BY fde) AS fde_total
  FROM v_capacity_fde_client
)
SELECT
  fde,
  MAX(fde_total)                                              AS tickets,
  COUNT(*)                                                    AS clients,
  ROUND(MAX(tickets)::numeric / NULLIF(MAX(fde_total), 0), 3) AS top_client_share,
  ROUND(SUM((tickets::numeric / NULLIF(fde_total, 0)) ^ 2), 3) AS hhi
FROM b
GROUP BY fde
ORDER BY tickets DESC;

-- Per client: key-person / bus-factor risk. top_fde_share=1.0 => one person.
CREATE OR REPLACE VIEW v_capacity_by_client AS
WITH b AS (
  SELECT client, fde, tickets,
         SUM(tickets) OVER (PARTITION BY client) AS cli_total
  FROM v_capacity_fde_client
)
SELECT
  client,
  MAX(cli_total)                                             AS tickets,
  COUNT(*)                                                   AS fdes,
  ROUND(MAX(tickets)::numeric / NULLIF(MAX(cli_total), 0), 3) AS top_fde_share,
  ROUND(SUM((tickets::numeric / NULLIF(cli_total, 0)) ^ 2), 3) AS hhi,
  (COUNT(*) = 1)                                             AS single_person
FROM b
GROUP BY client
ORDER BY tickets DESC;

-- --- RECURRENCE / REWORK ----------------------------------------------------
-- SQL covers QA-Failed rate + EXACT-normalized repeats (same title re-filed).
-- The fuzzy near-duplicate version lives in analyze_recurrence.py, because plain
-- SQL cannot do similarity clustering. When Justin's ticket_transitions is
-- available live, prefer counting backward transitions for the true signal.
CREATE OR REPLACE VIEW v_recurrence_by_client AS
WITH normed AS (
  SELECT
    c.name AS client,
    regexp_replace(lower(coalesce(t.feedback, '')), '[^a-z0-9 ]', ' ', 'g') AS norm_feedback,
    t.status
  FROM tickets t
  LEFT JOIN clients c ON c.id = t.client_id
  WHERE c.name IS NOT NULL
),
repeats AS (
  SELECT client, norm_feedback, COUNT(*) AS n
  FROM normed
  WHERE norm_feedback <> ''
  GROUP BY client, norm_feedback
  HAVING COUNT(*) > 1
)
SELECT
  n.client,
  COUNT(*)                                                        AS tickets,
  COUNT(*) FILTER (WHERE n.status = 'QA Failed')                  AS qa_failed,
  COALESCE(SUM(r.n) FILTER (WHERE r.norm_feedback IS NOT NULL), 0) AS in_exact_repeat,
  ROUND(100.0 * COUNT(*) FILTER (WHERE n.status = 'QA Failed')
        / NULLIF(COUNT(*), 0), 1)                                 AS qa_failed_pct
FROM normed n
LEFT JOIN repeats r ON r.client = n.client AND r.norm_feedback = n.norm_feedback
GROUP BY n.client
ORDER BY tickets DESC;
