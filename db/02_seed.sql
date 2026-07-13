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

-- Change Type taxonomy (revised 2026-07-09, Harvey). AI Fix / PRD Change are the
-- human values engineers set in Notion; the four issue-nature buckets are what
-- the classifier proposes for untyped tickets:
--   Tool Issue       — problem with the tool/product itself
--   Behavioral Issue — styling/tone not human-agent-like; aggressive nudging
--   Flow Issue       — lead->sale stages: first contact -> data collection -> checkout
--   Data Processing  — misinterpreting user meaning / misunderstanding collected data
-- The old expanded categories (Client Comms, Testing/QA, Scoping/Spec Creation,
-- Monitoring/Confirmation, Training) are retired; their DELETE lives in db/04
-- because it must run after change_type_inferences exists.
INSERT INTO change_types (name, sort_order) VALUES
  ('AI Fix', 10),
  ('PRD Change', 20),
  ('Tool Issue', 30),
  ('Behavioral Issue', 40),
  ('Flow Issue', 50),
  ('Data Processing', 60),
  ('Other', 90)
ON CONFLICT (name) DO UPDATE SET sort_order = EXCLUDED.sort_order;

-- The metric catalog — the analytics spec + live coverage. Statuses refreshed
-- 2026-07-10 to reflect what has shipped; the block below the divider is the
-- analytics added since the original 22-metric spec (all live on the dashboard).
TRUNCATE metric_catalog;
INSERT INTO metric_catalog (scope, metric, status, where_in_db, needs) VALUES
 ('Dashboard','Active hours by task category (org-wide & per client)','PROXY','v_by_client_type.active_hours','Interval logging (button adoption) - column is live and fills as intervals accrue'),
 ('Dashboard','Active vs queue/wait hours by stage, split by blocked-by cause','PARTIAL PROXY','v_by_client_type queue proxy','Blocked-by cause (Slack prompt) + intervals'),
 ('Dashboard','Per-FDE/SL task-type and stage mix','COMPUTED (type + stage)','v_by_fde_type + v_fde_stage_mix','Hours-weighted mix needs intervals'),
 ('Dashboard','SL capacity view (tickets/day per hot client x triage-and-spec time)','PARTIAL (inflow + triage live)','v_sl_capacity_by_sl + v_sl_capacity','Spec-time multiplier needs interval logging on SL work'),
 ('Dashboard','Before/after weekly timeline with ship dates','PARTIAL (timeline live, real dates)','v_by_week_type + features','Populate the features table at ship time'),
 ('Client','Active hours per ticket, per client, trended','PROXY','v_by_client_type','Interval logging (button adoption)'),
 ('Client','Task-type mix per client','COMPUTED (human types)','v_by_client_type','Inferred buckets kept backend-only by product decision'),
 ('Client','Queue/wait vs active ratio per client by blocked-by cause','PROXY (queue only)','v_by_client_type queue proxy','Blocked-by cause + intervals'),
 ('Client','Reopen/recurrence hours per client','PARTIAL (counts live)','v_recurrence + capacity-recurrence','Hours need intervals (backward-transition logging now live)'),
 ('Client','Hours-per-phase decay curve','PARTIAL (volume proxy live)','v_volume_by_phase_week','Hours need intervals; phase history not stored (current-phase caveat)'),
 ('Client','Active hours per 1,000 conversations','BLOCKED','conversations_daily','Conversation volume export from Portal/Eden Flow'),
 ('Client','Unticketed-work share, sampled','BLOCKED','-','Micro View sampled recording calibration'),
 ('Client','Capacity concentration (share of FDE/SL week per client)','COMPUTED (ticket share)','capacity-recurrence (HHI, key-person risk, donuts)','Hours-weighted version needs intervals'),
 ('Client','Time-to-Autopilot vs cohort','COMPUTED','v_time_to_autopilot','More clients with actual phase dates in Master Clients DB'),
 ('Feature','Before/after active hours in targeted category','BLOCKED','v_by_week_type scaffold','Ship dates + intervals'),
 ('Feature','Ticket-volume delta pre/post (fallback)','READY once ship dates exist','v_by_week_type','Feature ship-date table only - usable today'),
 ('Feature','Reopen/recurrence rate before/after','PARTIAL','v_recurrence','Ship dates (backward-transition logging now live)'),
 ('Feature','Deploy-wait time before/after','BLOCKED','-','Deploy-wait sub-status or interval type'),
 ('Feature','Tickets per 1,000 conversations before/after','BLOCKED','-','Conversation volume + ship dates'),
 ('Feature','Time-to-Autopilot cohort comparison','COMPUTED','v_time_to_autopilot','More clients with actual phase dates'),
 ('Feature','Cross-agent fix propagation rate','BLOCKED','-','Agent Fixer link between triaged ticket and propagated fixes'),
 ('Feature','False-positive/rework rate for QA features','BLOCKED','-','Product/tool tag on tickets (tag Watchtower-caused cleanup)'),
 -- ---- Added since the original spec (live on the dashboard) --------------------
 ('Flow','Ticket flow - opened vs closed per week (net backlog growth)','COMPUTED','v_flow_throughput_weekly','-'),
 ('Flow','Backlog aging by client (age buckets)','COMPUTED','v_flow_backlog_aging','-'),
 ('Flow','Cycle time reported->done, per client & priority','PROXY (calendar span)','v_flow_cycle_time_client / v_flow_cycle_time_priority','Active-time version needs intervals'),
 ('Flow','Oldest open CRITICAL/HIGH tickets','COMPUTED','v_flow_priority_age','-'),
 ('Flow','Ticket arrivals by day of week','COMPUTED','v_flow_arrival_dow','-'),
 ('Dashboard','Ticket share per client','COMPUTED','v_by_client_type (client-side aggregate)','-'),
 ('Dashboard','Latest tickets feed (10 most recent)','COMPUTED','v_recent_tickets','-'),
 ('Dashboard','Who is working now - live intervals + per-second timers','COMPUTED','v_who_working_now (SSE)','Button adoption for real coverage'),
 ('Dashboard','Cost-to-serve index (effort-weighted per client)','COMPUTED','capacity-recurrence endpoint','Real per-task effort weights (FDE interview) sharpen it'),
 ('Dashboard','Change-type classifier coverage','COMPUTED','v_change_type_coverage','-');
