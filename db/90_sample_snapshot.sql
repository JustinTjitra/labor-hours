--
-- PostgreSQL database dump
--


-- Dumped from database version 16.14 (Homebrew)
-- Dumped by pg_dump version 16.14 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP TABLE IF EXISTS public.snap_recurrence;
DROP TABLE IF EXISTS public.snap_qa_failed_open;
DROP TABLE IF EXISTS public.snap_data_quality;
DROP TABLE IF EXISTS public.snap_clients;
DROP TABLE IF EXISTS public.snap_by_week_type;
DROP TABLE IF EXISTS public.snap_by_fde_type;
DROP TABLE IF EXISTS public.snap_by_client_type;
DROP TABLE IF EXISTS public.snap_backlog;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: snap_backlog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snap_backlog (
    client text,
    status text,
    tickets integer
);


--
-- Name: snap_by_client_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snap_by_client_type (
    client text,
    change_type text,
    tickets integer,
    proxy_avg_days_reported_to_done double precision,
    proxy_avg_hours_inprogress_to_done double precision,
    proxy_avg_days_queue_reported_to_start double precision,
    active_hours double precision DEFAULT 0
);


--
-- Name: snap_by_fde_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snap_by_fde_type (
    fde text,
    change_type text,
    tickets integer,
    proxy_avg_days_reported_to_done double precision,
    proxy_avg_hours_inprogress_to_done double precision,
    active_hours double precision DEFAULT 0
);


--
-- Name: snap_by_week_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snap_by_week_type (
    iso_week text,
    change_type text,
    tickets integer
);


--
-- Name: snap_clients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snap_clients (
    name text,
    phase text,
    alive text,
    scoping_date text,
    actual_copilot_date text,
    actual_autopilot_date text,
    days_scoping_to_copilot double precision,
    days_scoping_to_autopilot double precision
);


--
-- Name: snap_data_quality; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snap_data_quality (
    measure text,
    value text
);


--
-- Name: snap_qa_failed_open; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snap_qa_failed_open (
    client text,
    feedback text,
    change_type text,
    priority text,
    reported text
);


--
-- Name: snap_recurrence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.snap_recurrence (
    client text,
    detail text,
    kind text
);


--
-- Data for Name: snap_backlog; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.snap_backlog VALUES (NULL, 'Not Started', 11);
INSERT INTO public.snap_backlog VALUES ('Samada Resorts', 'QA Failed', 6);
INSERT INTO public.snap_backlog VALUES ('Wise Bahay', 'Not Started', 3);
INSERT INTO public.snap_backlog VALUES ('Digikidz', 'In Progress', 1);
INSERT INTO public.snap_backlog VALUES ('Digikidz', 'Not Started', 1);
INSERT INTO public.snap_backlog VALUES ('Digikidz', 'QA Failed', 2);
INSERT INTO public.snap_backlog VALUES ('Satu Dental', 'In Progress', 1);
INSERT INTO public.snap_backlog VALUES ('Satu Dental', 'REVIEW', 31);
INSERT INTO public.snap_backlog VALUES ('Acepadel', 'Blocked', 1);
INSERT INTO public.snap_backlog VALUES ('Acepadel', 'QA Failed', 1);
INSERT INTO public.snap_backlog VALUES ('EwasteRJ', 'Not Started', 7);
INSERT INTO public.snap_backlog VALUES ('EwasteRJ', 'QA Failed', 2);
INSERT INTO public.snap_backlog VALUES ('EwasteRJ', 'REVIEW', 2);
INSERT INTO public.snap_backlog VALUES ('Meimei', 'REVIEW', 7);
INSERT INTO public.snap_backlog VALUES ('CoLearn', 'In Progress', 2);
INSERT INTO public.snap_backlog VALUES ('CoLearn', 'REVIEW', 2);
INSERT INTO public.snap_backlog VALUES ('Garuda', 'Blocked', 1);
INSERT INTO public.snap_backlog VALUES ('Garuda', 'In Progress', 1);
INSERT INTO public.snap_backlog VALUES ('Garuda', 'Not Started', 1);
INSERT INTO public.snap_backlog VALUES ('Garuda', 'REVIEW', 6);
INSERT INTO public.snap_backlog VALUES ('Alethea', 'Blocked', 1);
INSERT INTO public.snap_backlog VALUES ('Alethea', 'REVIEW', 4);
INSERT INTO public.snap_backlog VALUES ('Covena Sales', 'Not Started', 1);
INSERT INTO public.snap_backlog VALUES ('Covena Sales', 'REVIEW', 9);
INSERT INTO public.snap_backlog VALUES ('Zenith Education', 'Not Started', 5);
INSERT INTO public.snap_backlog VALUES ('PUTIH Dental', 'In Progress', 2);
INSERT INTO public.snap_backlog VALUES ('Reflecto', 'Not Started', 6);
INSERT INTO public.snap_backlog VALUES ('Hamdan Tour', 'REVIEW', 6);
INSERT INTO public.snap_backlog VALUES ('Ona Indonesia', 'Not Started', 4);
INSERT INTO public.snap_backlog VALUES ('Ona Indonesia', 'QA Failed', 3);
INSERT INTO public.snap_backlog VALUES ('Ona Indonesia', 'REVIEW', 4);


--
-- Data for Name: snap_by_client_type; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.snap_by_client_type VALUES (NULL, 'AI Fix', 7, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES (NULL, 'Untyped', 7, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Samada Resorts', 'AI Fix', 14, 1.82, 28.2, 0.7, 0);
INSERT INTO public.snap_by_client_type VALUES ('Samada Resorts', 'PRD Change', 1, 13.63, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Samada Resorts', 'Untyped', 15, 9.65, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Wise Bahay', 'Untyped', 3, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Digikidz', 'AI Fix', 17, 8.78, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Digikidz', 'PRD Change', 10, 6.31, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Digikidz', 'Untyped', 9, 12.05, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Newtonshow', 'Untyped', 13, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Satu Dental', 'Untyped', 55, 3.19, 62.9, 0.57, 0);
INSERT INTO public.snap_by_client_type VALUES ('Acepadel', 'AI Fix', 17, 11.28, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Acepadel', 'PRD Change', 9, 16.98, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Acepadel', 'Untyped', 4, 4.79, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('EwasteRJ', 'AI Fix', 15, 6.48, 3.5, 0.36, 0);
INSERT INTO public.snap_by_client_type VALUES ('EwasteRJ', 'PRD Change', 10, 7.01, 35.1, 1.6, 0);
INSERT INTO public.snap_by_client_type VALUES ('EwasteRJ', 'Untyped', 36, 10.91, 116.3, 4.67, 0);
INSERT INTO public.snap_by_client_type VALUES ('Meimei', 'AI Fix', 5, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Meimei', 'PRD Change', 1, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Meimei', 'Untyped', 7, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('ALVA', 'AI Fix', 2, 0.82, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('ALVA', 'PRD Change', 2, 4.39, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('ALVA', 'Untyped', 8, 0.32, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('CoLearn', 'AI Fix', 87, 1.75, 44.6, 0.3, 0);
INSERT INTO public.snap_by_client_type VALUES ('CoLearn', 'Untyped', 5, 4.98, 4.1, 0.19, 0);
INSERT INTO public.snap_by_client_type VALUES ('AECC Indo', 'PRD Change', 1, 0.49, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Garuda', 'AI Fix', 43, 3.33, 46.5, 0.5, 0);
INSERT INTO public.snap_by_client_type VALUES ('Garuda', 'PRD Change', 6, 1.15, 36.3, 0.31, 0);
INSERT INTO public.snap_by_client_type VALUES ('Garuda', 'Untyped', 23, 9.35, 283.6, 9.04, 0);
INSERT INTO public.snap_by_client_type VALUES ('AECC Nepal', 'AI Fix', 3, 0.46, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('AECC Nepal', 'Untyped', 6, 3.34, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Alethea', 'AI Fix', 35, 5.02, 113.2, 2.31, 0);
INSERT INTO public.snap_by_client_type VALUES ('Alethea', 'PRD Change', 27, 7.28, 120.9, 0.41, 0);
INSERT INTO public.snap_by_client_type VALUES ('Alethea', 'Untyped', 21, 10.79, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Covena Sales', 'AI Fix', 18, 3.54, 76.4, 0.79, 0);
INSERT INTO public.snap_by_client_type VALUES ('Covena Sales', 'PRD Change', 6, 3.52, 81.8, 1.35, 0);
INSERT INTO public.snap_by_client_type VALUES ('Covena Sales', 'Untyped', 12, 4.23, 90, 0.58, 0);
INSERT INTO public.snap_by_client_type VALUES ('Zenith Education', 'Untyped', 5, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('PUTIH Dental', 'AI Fix', 7, 7.13, 220, 0.15, 0);
INSERT INTO public.snap_by_client_type VALUES ('PUTIH Dental', 'PRD Change', 1, 0.17, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('PUTIH Dental', 'Untyped', 2, 6.98, 158.1, 0.4, 0);
INSERT INTO public.snap_by_client_type VALUES ('Reflecto', 'Untyped', 6, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Hamdan Tour', 'Untyped', 14, 6.13, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Ona Indonesia', 'AI Fix', 8, NULL, NULL, 0.29, 0);
INSERT INTO public.snap_by_client_type VALUES ('Ona Indonesia', 'PRD Change', 1, NULL, NULL, NULL, 0);
INSERT INTO public.snap_by_client_type VALUES ('Ona Indonesia', 'Untyped', 2, NULL, NULL, 0.28, 0);


--
-- Data for Name: snap_by_fde_type; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.snap_by_fde_type VALUES ('Unassigned', 'AI Fix', 7, NULL, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('Unassigned', 'Untyped', 11, 44.34, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-A', 'AI Fix', 93, 2.98, 109.7, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-A', 'PRD Change', 12, 4.48, 35.5, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-A', 'Untyped', 64, 9.6, 158.1, 0);
INSERT INTO public.snap_by_fde_type VALUES ('SL-Harvey', 'AI Fix', 1, NULL, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('SL-Harvey', 'PRD Change', 1, 0.49, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('SL-Harvey', 'Untyped', 5, NULL, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-F', 'Untyped', 2, NULL, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-B', 'AI Fix', 83, 6.19, 79.2, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-B', 'PRD Change', 47, 8.92, 120.9, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-B', 'Untyped', 61, 7.42, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-C', 'AI Fix', 19, 5.99, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-C', 'PRD Change', 8, 7.77, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-C', 'Untyped', 43, 11.24, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-D', 'AI Fix', 61, 2.12, 44, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-D', 'PRD Change', 1, NULL, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-D', 'Untyped', 5, 1.57, 33.5, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-E+A shared', 'AI Fix', 3, 2.66, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-E+A shared', 'PRD Change', 1, 0.17, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-E+A shared', 'Untyped', 1, NULL, NULL, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-E', 'AI Fix', 11, 2.8, 76.4, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-E', 'PRD Change', 5, 3.52, 81.8, 0);
INSERT INTO public.snap_by_fde_type VALUES ('FDE-E', 'Untyped', 61, 4.29, 95.7, 0);


--
-- Data for Name: snap_by_week_type; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.snap_by_week_type VALUES ('2026-17', 'Untyped', 17);
INSERT INTO public.snap_by_week_type VALUES ('2026-18', 'Untyped', 57);
INSERT INTO public.snap_by_week_type VALUES ('2026-19', 'PRD Change', 1);
INSERT INTO public.snap_by_week_type VALUES ('2026-19', 'Untyped', 65);
INSERT INTO public.snap_by_week_type VALUES ('2026-20', 'AI Fix', 40);
INSERT INTO public.snap_by_week_type VALUES ('2026-20', 'PRD Change', 28);
INSERT INTO public.snap_by_week_type VALUES ('2026-20', 'Untyped', 24);
INSERT INTO public.snap_by_week_type VALUES ('2026-21', 'AI Fix', 32);
INSERT INTO public.snap_by_week_type VALUES ('2026-21', 'PRD Change', 14);
INSERT INTO public.snap_by_week_type VALUES ('2026-21', 'Untyped', 7);
INSERT INTO public.snap_by_week_type VALUES ('2026-22', 'AI Fix', 24);
INSERT INTO public.snap_by_week_type VALUES ('2026-22', 'PRD Change', 10);
INSERT INTO public.snap_by_week_type VALUES ('2026-22', 'Untyped', 2);
INSERT INTO public.snap_by_week_type VALUES ('2026-23', 'AI Fix', 40);
INSERT INTO public.snap_by_week_type VALUES ('2026-23', 'PRD Change', 15);
INSERT INTO public.snap_by_week_type VALUES ('2026-23', 'Untyped', 17);
INSERT INTO public.snap_by_week_type VALUES ('2026-24', 'AI Fix', 35);
INSERT INTO public.snap_by_week_type VALUES ('2026-24', 'PRD Change', 4);
INSERT INTO public.snap_by_week_type VALUES ('2026-24', 'Untyped', 20);
INSERT INTO public.snap_by_week_type VALUES ('2026-25', 'AI Fix', 61);
INSERT INTO public.snap_by_week_type VALUES ('2026-25', 'PRD Change', 2);
INSERT INTO public.snap_by_week_type VALUES ('2026-25', 'Untyped', 16);
INSERT INTO public.snap_by_week_type VALUES ('2026-26', 'AI Fix', 46);
INSERT INTO public.snap_by_week_type VALUES ('2026-26', 'PRD Change', 1);
INSERT INTO public.snap_by_week_type VALUES ('2026-26', 'Untyped', 25);


--
-- Data for Name: snap_clients; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.snap_clients VALUES ('Acepadel', 'Autopilot', 'Alive', '2026-04-01', '2026-04-15', '2026-05-12', 14, 41);
INSERT INTO public.snap_clients VALUES ('AECC Indo', 'Stable', 'Alive', '2025-09-17', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('AECC Nepal', 'Autopilot', 'Alive', '2026-03-01', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('AIBP', 'Development', 'Alive', '2025-10-01', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Alethea', 'Autopilot', 'Alive', '2026-04-28', '2026-05-11', NULL, 13, NULL);
INSERT INTO public.snap_clients VALUES ('ALVA', 'Autopilot', 'Alive', '2025-03-12', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Belajarlagi', NULL, 'Alive', '2025-11-01', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Bigmo', 'Development', 'Alive', '2026-02-17', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Cak Investment Club', 'Stable', 'Dead', '2026-01-30', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('CoLearn', 'Autopilot', 'Alive', '2025-05-22', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Covena Sales', 'Autopilot', 'Alive', NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Digikidz', 'Autopilot', 'Alive', '2025-12-10', NULL, '2026-05-07', NULL, 148);
INSERT INTO public.snap_clients VALUES ('EwasteRJ', 'Autopilot', 'Alive', '2026-05-05', '2026-05-12', NULL, 7, NULL);
INSERT INTO public.snap_clients VALUES ('Gaji', 'Autopilot', 'Alive', '2026-04-29', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Garuda', 'Autopilot', 'Alive', '2025-09-30', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Hamdan Tour', 'Development', 'Alive', '2026-06-19', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Indah Keramik', 'Development', 'Alive', '2026-06-22', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Light', 'Autopilot', 'Alive', '2026-04-02', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Meimei', 'Stable', 'Alive', '2026-05-01', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Newtonshow', 'Development', 'Dead', '2026-03-17', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Ona Indonesia', 'Development', 'Alive', '2026-06-24', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Pupul', 'Development', 'Alive', '2025-11-12', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('PUTIH Dental', 'Development', 'Alive', '2026-06-12', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Reflecto', 'Copilot', 'Alive', '2026-06-19', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Samada Resorts', 'Autopilot', 'Alive', '2026-05-08', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Satu Dental', 'Development', 'Alive', '2026-03-09', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('SKitchen', 'Not started', 'Alive', '2026-07-02', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Stella Lunardy', 'Development', 'Alive', '2026-06-29', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Tokoparts', 'Stable', 'Alive', '2025-01-08', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Wise Bahay', 'Development', 'Alive', '2026-04-16', NULL, NULL, NULL, NULL);
INSERT INTO public.snap_clients VALUES ('Zenith Education', 'Development', 'Alive', NULL, NULL, NULL, NULL, NULL);


--
-- Data for Name: snap_data_quality; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.snap_data_quality VALUES ('total_tickets', '606');
INSERT INTO public.snap_data_quality VALUES ('status_done', '467');
INSERT INTO public.snap_data_quality VALUES ('status_review', '73');
INSERT INTO public.snap_data_quality VALUES ('status_not_started', '39');
INSERT INTO public.snap_data_quality VALUES ('status_qa_failed', '14');
INSERT INTO public.snap_data_quality VALUES ('status_in_progress', '7');
INSERT INTO public.snap_data_quality VALUES ('status_blocked', '3');
INSERT INTO public.snap_data_quality VALUES ('status_null', '3');
INSERT INTO public.snap_data_quality VALUES ('has_moved_to_in_progress_ts', '107 (17.7%)');
INSERT INTO public.snap_data_quality VALUES ('has_moved_to_review_ts', '183 (30.2%)');
INSERT INTO public.snap_data_quality VALUES ('has_moved_to_done_ts', '315 (52.0%)');
INSERT INTO public.snap_data_quality VALUES ('untyped_change_type', '250 (41.3%)');
INSERT INTO public.snap_data_quality VALUES ('pull_date', '2026-07-03');
INSERT INTO public.snap_data_quality VALUES ('warning', 'All hour/day figures are stage-timestamp PROXIES (calendar spans), not active work hours. Active hours require Phase 0 start/stop intervals.');
INSERT INTO public.snap_data_quality VALUES ('open_backlog', '134');
INSERT INTO public.snap_data_quality VALUES ('tickets_with_intervals', '0');
INSERT INTO public.snap_data_quality VALUES ('open_intervals_now', '0');


--
-- Data for Name: snap_qa_failed_open; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.snap_qa_failed_open VALUES ('Acepadel', 'Should read image which says Karawaci already', 'AI Fix', 'LOW', '2026-05-19');
INSERT INTO public.snap_qa_failed_open VALUES ('Digikidz', 'Wrong Schedule to Offer', 'AI Fix', 'CRITICAL', '2026-06-02');
INSERT INTO public.snap_qa_failed_open VALUES ('Digikidz', 'Wrong Date, 8th June is Monday not Sunday', 'AI Fix', 'CRITICAL', '2026-06-02');
INSERT INTO public.snap_qa_failed_open VALUES ('EwasteRJ', 'Implement to validate L, W & H separately', 'PRD Change', 'HIGH', '2026-06-04');
INSERT INTO public.snap_qa_failed_open VALUES ('EwasteRJ', 'Revamp flow', NULL, 'MEDIUM', '2026-06-15');
INSERT INTO public.snap_qa_failed_open VALUES ('Samada Resorts', 'Add to KB: handuk & sprei diganti how often untuk bulanan', NULL, 'MEDIUM', '2026-06-15');
INSERT INTO public.snap_qa_failed_open VALUES ('Samada Resorts', 'Add to KB: gaada bunkbed', NULL, 'MEDIUM', '2026-06-15');
INSERT INTO public.snap_qa_failed_open VALUES ('Samada Resorts', 'Bisa book coworking, arahkan juga ke cafe', NULL, 'MEDIUM', '2026-06-29');
INSERT INTO public.snap_qa_failed_open VALUES ('Samada Resorts', 'Canggu Bali not Ubud', 'AI Fix', 'CRITICAL', '2026-06-29');
INSERT INTO public.snap_qa_failed_open VALUES ('Samada Resorts', 'Template dari simulasi chat tidak applied disini, why?', 'AI Fix', 'CRITICAL', '2026-06-29');
INSERT INTO public.snap_qa_failed_open VALUES ('Ona Indonesia', 'Change agent name to Min Na', 'AI Fix', 'MEDIUM', '2026-07-01');
INSERT INTO public.snap_qa_failed_open VALUES ('Samada Resorts', 'Language issue again', 'AI Fix', 'MEDIUM', '2026-07-01');
INSERT INTO public.snap_qa_failed_open VALUES ('Ona Indonesia', 'Do not expose jarak gudang terdekat to user', 'AI Fix', 'CRITICAL', '2026-07-02');
INSERT INTO public.snap_qa_failed_open VALUES ('Ona Indonesia', 'Refer to self as Min Na instead of Aku', NULL, 'LOW', '2026-07-02');


--
-- Data for Name: snap_recurrence; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.snap_recurrence VALUES ('Garuda', 'main menu / main info re-sent complaint filed 3x: #522 (Jun 2), ''shouldnt send main info again'' (Jun 19), ''should not send menu again'' (Jun 27)', 'recurrence');
INSERT INTO public.snap_recurrence VALUES ('Satu Dental', '''hallucinated booking'' filed May 10 (REVIEW) and re-filed May 11 (Done)', 're-filed duplicate');
INSERT INTO public.snap_recurrence VALUES ('Samada Resorts', '''Language issue again'' currently QA Failed - redo of a redo', 'recurrence');
INSERT INTO public.snap_recurrence VALUES ('CoLearn', '''image caption'' x2 and ''wrong generalQnA query'' x2 filed same day (Jun 21)', 'possible double-filing');
INSERT INTO public.snap_recurrence VALUES ('Alethea', '5x identical ''Fix-AI - Alethea'' tickets, Not Started, no client relation', 'hygiene noise');


--
-- PostgreSQL database dump complete
--


