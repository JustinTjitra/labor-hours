-- ===========================================================================
-- 08_daily_views.sql  (ADDITIVE — DAILY granularity for the time-series charts)
--
-- The weekly views (03/06/07) pre-bucket by week, which loses resolution when a
-- user zooms into a short window. These emit one row PER DAY; the dashboard rolls
-- them up client-side to day / week / month depending on the selected range, so
-- narrowing the date filter reveals day-to-day detail. Same measures as the
-- weekly views, just finer grain. Counts only.
-- ===========================================================================

-- Ticket volume by day x change type (human types only, per 2026-07-09 decision).
CREATE OR REPLACE VIEW v_by_day_type AS
SELECT
  t.reported_date::date              AS day,
  COALESCE(t.change_type, 'Untyped') AS change_type,
  COUNT(*)                           AS tickets
FROM tickets t
WHERE t.reported_date IS NOT NULL
GROUP BY 1, 2;

-- Opened vs closed per day (net computed client-side after bucketing).
CREATE OR REPLACE VIEW v_flow_throughput_daily AS
WITH opened AS (
  SELECT reported_date::date AS day, COUNT(*) AS opened
  FROM tickets WHERE reported_date IS NOT NULL GROUP BY 1
),
closed AS (
  SELECT moved_to_done::date AS day, COUNT(*) AS closed
  FROM tickets WHERE moved_to_done IS NOT NULL GROUP BY 1
)
SELECT
  COALESCE(o.day, c.day)  AS day,
  COALESCE(o.opened, 0)   AS opened,
  COALESCE(c.closed, 0)   AS closed
FROM opened o
FULL JOIN closed c USING (day)
ORDER BY 1;

-- Ticket volume by day x client phase (decay-curve proxy source).
CREATE OR REPLACE VIEW v_volume_by_phase_day AS
SELECT
  t.reported_date::date         AS day,
  COALESCE(c.phase, 'No phase') AS phase,
  COUNT(*)                      AS tickets
FROM tickets t
LEFT JOIN clients c ON c.id = t.client_id
WHERE t.reported_date IS NOT NULL
GROUP BY 1, 2;
