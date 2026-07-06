# Capacity concentration + Recurrence

Two client metrics from the MVP Dashboard list, built off the static ticket
export so they don't wait on Justin's active-hours button (which is a new feature
the SWEs haven't started using, so it's empty by design). Both run on reliable,
auto-captured fields, and both add new files only, so they don't collide with
Justin's work.

## What each one answers, in plain terms

**Capacity concentration** — who is carrying what. Two angles:
- Per FDE: is their week spread across clients, or dominated by one? A high number
  means they are a single point of failure for that client.
- Per client: is one person the only one who knows it? A client at 100% one-person
  is a bus-factor risk. If that person is out, the client is stuck.

**Recurrence / rework** — which clients keep re-filing the same problem. A client
with lots of repeats costs more than its ticket count suggests, because the same
issue keeps coming back. Found two ways: near-duplicate feedback titles within a
client (so "Language issue" and "Language issue again" count as the same recurring
problem), plus the current QA-Failed count.

Both use HHI (Herfindahl index) to score concentration: sum of squared shares,
from ~0 (evenly spread) to 1.0 (everything on one). Over 0.5 is heavy.

## What the current export says

Capacity: most FDEs are reasonably spread (HHI ~0.26 to 0.37), but one is heavily
tied to a single client (83% on CoLearn). Seven clients are carried 100% by a
single person (Alethea, Garuda, Acepadel, Samada Resorts, Meimei, ALVA, Ona
Indonesia), and Digikidz is 97% on one person. That is the key-person risk the
metric is meant to surface.

Recurrence is modest but real: Garuda and CoLearn have the most repeats (~8 to 11%
of tickets), and the clusters name actual recurring problems, e.g. Garuda's
"should escalate" filed four times. QA-Failed is currently low across the board.

## Run it

```bash
python analyze_capacity_concentration.py --csv tickets.csv
python analyze_capacity_concentration.py --csv tickets.csv --show-names   # private map
python analyze_recurrence.py --csv tickets.csv
```

`tickets.csv` is the Notion "Markdown & CSV" export of the ticket database.

## Cost-to-serve index + over/undercharge

The headline metric: how expensive is each client to serve, weighted by severity
and rework rather than raw ticket count. Each ticket earns
`severity_weight x rework_multiplier` effort points (Critical 3x, High 2x, Low
0.5x; recurring or QA-failed adds up to 50%). Summed per client.

Why it matters: CoLearn has the most tickets (95) but ranks only third in effort,
because 99% of its tickets are low-severity. Alethea does fewer tickets but tops
the index on severity. Raw counts mislead; this doesn't.

```bash
python analyze_cost_to_serve.py --csv tickets.csv                       # index only
python analyze_cost_to_serve.py --csv tickets.csv --write-price-template prices.csv
python analyze_cost_to_serve.py --csv tickets.csv --prices prices.csv   # over/undercharge
```

Over/undercharge compares each client's share of total effort against its share
of total revenue. Effort share well above revenue share = undercharged. Dollars
stay in this CLI, never on the shared dashboard (the design forbids dollars there).
Fill `prices_template.csv` with monthly prices and pass it via `--prices`.

## Files (all new, all additive)

| File | What |
|------|------|
| `analyze_capacity_concentration.py` | FDE-vs-client allocation + key-person risk, from the CSV. People anonymized. |
| `analyze_recurrence.py` | Near-duplicate repeat clusters per client + QA-Failed. |
| `analyze_cost_to_serve.py` | Effort-weighted cost-to-serve index + over/undercharge overlay. |
| `build_dashboard.py` | Regenerates the self-contained HTML dashboard (cost-to-serve, donuts, key-person risk, recurrence). `--real-names` for names. |
| `prices_template.csv` | Blank client price list to fill for the over/undercharge overlay. |
| `db/05_capacity_and_recurrence.sql` | Matching SQL views for the repo (`v_capacity_by_fde`, `v_capacity_by_client`, `v_recurrence_by_client`). |

## Notes for wiring into Justin's repo

- Anonymization uses his existing `fde_map`. PICs not in the map show as
  "Unassigned" until the Employee Database join is populated.
- The live `tickets.pic_user_id` holds a single person, so the SQL needs no
  fractional split. The Python handles multi-PIC CSV cells by giving 1/k credit.
- Recurrence in SQL covers QA-Failed + exact-normalized repeats. The fuzzy
  near-duplicate clustering stays in Python (plain SQL can't do similarity). When
  the live `ticket_transitions` log is available, counting backward transitions is
  the stronger recurrence signal and should replace the string proxy.
- To expose on the API, add the view names to the `_VIEWS` whitelist in
  `app/metrics.py` (one line each); to chart them, add cards to the dashboard.
