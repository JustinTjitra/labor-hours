-- Seed data: anonymization map, expanded taxonomy, and the 22-metric catalog.
-- Idempotent (safe to re-run).

-- PIC identity map (real names from the ticket DB), keyed by the stable Notion
-- user id. FDE-E / FDE-F names not yet confirmed. Guest IDs don't resolve via the
-- Notion API, so names are set here manually.
INSERT INTO fde_map (label, notion_user_id) VALUES
  ('Evan',             '0a9ee3e0-b8e5-49c5-bd0c-b0b91397fc4f'),
  ('Michael Immanuel', '830c99df-acb0-4dca-917a-530cdaa8367e'),
  ('Keanan Wongso',    '96cbc429-3a75-494e-af79-fe01c707c493'),
  ('Leroy Marshal',    'a639357d-95ad-4ba2-a820-d826cc5516dd'),
  ('FDE-E',            'e97253fd-d267-4384-a705-f723bc214f30'),
  ('FDE-F',            '4d4b61c0-705b-49b9-be19-438fc4ce5557'),
  ('SL-Harvey',        '1088aecb-decc-4952-973b-8196537f169a')
ON CONFLICT (notion_user_id) DO UPDATE SET label = EXCLUDED.label;

-- Expanded Change Type taxonomy (build-order step 1). AI Fix / PRD Change already
-- exist in Notion; the rest are the additions that replace 41% "Untyped".
INSERT INTO change_types (name, sort_order) VALUES
  ('AI Fix', 10),
  ('PRD Change', 20),
  ('Client Comms', 30),
  ('Testing/QA', 40),
  ('Scoping/Spec Creation', 50),
  ('Monitoring/Confirmation', 60),
  ('Training', 70),
  ('Other', 80)
ON CONFLICT (name) DO UPDATE SET sort_order = EXCLUDED.sort_order;

-- The 22-metric catalog — authoritative spec for which views to build and what
-- each still needs. Mirrors metric_catalog in labor_analytics.db verbatim.
TRUNCATE metric_catalog;
INSERT INTO metric_catalog (scope, metric, status, where_in_db, needs) VALUES
 ('Dashboard','Active hours by task category (org-wide & per client)','PROXY','v_by_client_type','Phase 0 interval logging; expanded taxonomy (41% untyped today)'),
 ('Dashboard','Active vs queue/wait hours by stage, split by blocked-by cause','PARTIAL PROXY','v_by_client_type.proxy_avg_days_queue (queue proxy only, 17.7% coverage)','Blocked-by field + blocked-episode timestamps'),
 ('Dashboard','Per-FDE/SL task-type and stage mix','COMPUTED (mix by type)','v_by_fde_type','Expanded taxonomy for real mix; stage mix needs full transition timestamps'),
 ('Dashboard','SL capacity view (tickets/day per hot client x triage-and-spec time)','PARTIAL','v_by_client_type + v_backlog_client_status (volume side only)','Triage/spec time needs interval logging on SL work; Capacity Planning join'),
 ('Dashboard','Before/after weekly timeline with ship dates','PARTIAL','v_by_week_type + features (timeline exists)','Feature ship-date source of truth (features table) - populate at ship time'),
 ('Client','Active hours per ticket, per client, trended','PROXY','v_by_client_type','Phase 0 intervals'),
 ('Client','Task-type mix per client','COMPUTED (2 types + untyped)','v_by_client_type','Expanded taxonomy - currently only AI Fix / PRD Change'),
 ('Client','Queue/wait vs active ratio per client by blocked-by cause','PROXY (queue only)','v_by_client_type.proxy_avg_days_queue','Blocked-by field'),
 ('Client','Reopen/recurrence hours per client','PARTIAL (counts, not hours)','v_qa_failed_open + v_recurrence','Backward-transition logging + reopened-from relation + intervals'),
 ('Client','Hours-per-phase decay curve','BLOCKED (volume-per-phase possible)','v_clients (phase dates)','Phase-tag hygiene on tickets (most Phase fields empty) + intervals'),
 ('Client','Active hours per 1,000 conversations','BLOCKED','conversations_daily','Conversation volume export from Portal/Eden Flow'),
 ('Client','Unticketed-work share, sampled','BLOCKED','-','Micro View sampled recording'),
 ('Client','Capacity concentration (share of FDE/SL week per client)','PARTIAL','v_by_fde_type x v_by_client_type (ticket share only)','Capacity Planning join + intervals'),
 ('Client','Time-to-Autopilot vs cohort','COMPUTED (sparse)','v_clients.days_scoping_to_autopilot (only 2 clients have full dates)','Phase-date hygiene in Master Clients DB'),
 ('Feature','Before/after active hours in targeted category','BLOCKED','v_by_week_type is the scaffold','Ship dates + intervals + taxonomy'),
 ('Feature','Ticket-volume delta pre/post (fallback)','READY once ship dates exist','v_by_week_type','Feature ship-date table only - usable today'),
 ('Feature','Reopen/recurrence rate before/after','PARTIAL','v_qa_failed_open (current snapshot)','Backward-transition logging + ship dates'),
 ('Feature','Deploy-wait time before/after','BLOCKED','-','Deploy-wait sub-status or interval type'),
 ('Feature','Tickets per 1,000 conversations before/after','BLOCKED','-','Conversation volume + ship dates'),
 ('Feature','Time-to-Autopilot cohort comparison','COMPUTED (sparse)','v_clients','Phase-date hygiene; more clients with actual dates'),
 ('Feature','Cross-agent fix propagation rate','BLOCKED','-','Agent Fixer link between triaged ticket and propagated fixes'),
 ('Feature','False-positive/rework rate for QA features','BLOCKED','-','Product/tool tag on tickets (tag Watchtower-caused cleanup)');
