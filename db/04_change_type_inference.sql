-- ===========================================================================
-- 04_change_type_inference.sql  (ADDITIVE — Tim's change-type classifier)
--
-- Owns ONE new table + ONE new view. Touches none of Justin's tables or views.
-- Runs after 02_seed.sql (FK below references change_types) and after 01_schema
-- (FK references tickets). apply_all_sql.py / init_db.py apply files in name
-- order, so 04 lands last. Safe to re-run (IF NOT EXISTS / OR REPLACE).
-- ===========================================================================

-- Proposed Change Type for tickets an engineer left untyped. One row per ticket.
-- method: 'rules' (keyword scorer) | 'llm' (future escalation) | 'human' (if ever
-- promoted). inferred_type is constrained to the real taxonomy via the FK.
CREATE TABLE IF NOT EXISTS change_type_inferences (
  ticket_id     TEXT PRIMARY KEY REFERENCES tickets(id),
  inferred_type TEXT NOT NULL REFERENCES change_types(name),
  confidence    TEXT NOT NULL DEFAULT 'low',   -- high | medium | low
  method        TEXT NOT NULL DEFAULT 'rules',  -- rules | llm | human
  matched_rule  TEXT,                           -- why (audit trail for review)
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cti_type_idx ON change_type_inferences (inferred_type);
CREATE INDEX IF NOT EXISTS cti_conf_idx ON change_type_inferences (confidence);

-- Effective Change Type: a human-set Notion value ALWAYS wins; the inference only
-- fills the gap. Downstream views/metrics can read effective_type here without
-- caring whether a human or the classifier supplied it. `source` lets the
-- dashboard shade inferred rows (e.g. show them lighter / with an asterisk).
CREATE OR REPLACE VIEW v_change_type_effective AS
SELECT
  t.id                                        AS ticket_id,
  COALESCE(t.change_type, ci.inferred_type)   AS effective_type,
  CASE
    WHEN t.change_type IS NOT NULL THEN 'human'
    WHEN ci.inferred_type IS NOT NULL THEN 'inferred'
    ELSE 'untyped'
  END                                         AS source,
  ci.confidence                               AS inferred_confidence
FROM tickets t
LEFT JOIN change_type_inferences ci ON ci.ticket_id = t.id;

-- Coverage readout: how much of the untyped backlog the classifier now fills,
-- and at what confidence. Handy for a one-line "are we still starved?" check.
CREATE OR REPLACE VIEW v_change_type_coverage AS
SELECT
  count(*)                                                          AS tickets,
  count(*) FILTER (WHERE source = 'human')                         AS human_typed,
  count(*) FILTER (WHERE source = 'inferred')                      AS inferred,
  count(*) FILTER (WHERE source = 'untyped')                       AS still_untyped,
  round(100.0 * count(*) FILTER (WHERE source <> 'untyped')
        / NULLIF(count(*), 0), 1)                                  AS pct_typed
FROM v_change_type_effective;
