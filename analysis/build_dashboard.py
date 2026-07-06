"""Build a self-contained HTML dashboard for capacity concentration + recurrence.

Reads the ticket CSV, computes both metrics, and writes a single HTML file with
the data baked in and Chart.js from CDN. No server, no API: double-click to view.

    python build_dashboard.py --csv tickets.csv --out dashboard.html
    python build_dashboard.py --csv tickets.csv --real-names          # names instead of FDE-A/B/C

Sections: KPIs, per-FDE allocation donuts, key-person risk, recurrence by problem
area, and the list of recurring concept groups. Recurrence is CONCEPT-based: two
tickets count as the same issue if they share an underlying concept (escalation,
scheduling, payment, ...), so differently-worded repeats of the same problem are
caught. This measures recurring problem AREAS, not the identical bug re-filed;
member examples are shown so groups can be audited.

Styled to match Justin's dashboard palette but a separate file that touches none
of his code.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict

# --- concept map, mined from the real feedback corpus -----------------------
# specific concepts are dedupe-worthy; 'tone_wording' is broad, tagged but never
# the sole basis for a recurrence group.
_CONCEPTS = [
    ("escalation",       r"escalat"),
    ("payment/checkout", r"payment|checkout|\bcart\b|purchase"),
    ("main_info",        r"main\s?info|send.*info|info.*send"),
    ("phone",            r"phone|\bnumber\b|contact"),
    ("scheduling",       r"schedul|availab|\bdate\b|pickup|departure|reschedul"),
    ("booking",          r"booking"),
    ("naming",           r"\bname|naming"),
    ("child_grade",      r"child|grade|student"),
    ("image",            r"image|caption"),
    ("brochure",         r"brochure|catalog"),
    ("pricing",          r"\bpric|\bcost|cheap|expensive"),
    ("hallucination",    r"hallucinat|invent|fabricat"),
    ("lead_status",      r"lead\b|lead status"),
    ("flow_sop",         r"\bflow\b|\bsop\b|order of|\bstep"),
    ("routing_qna",      r"generalqna|general qna|routing|\bquery\b|reroute"),
    ("greeting",         r"greet|salutation"),
    ("confirmation",     r"confirm"),
    ("language",         r"language|translat|english|bahasa"),
    ("form",             r"\bform\b|fill"),
    ("tone_wording",     r"wording|styling|tone|phrasing|\bsay\b|message|response|bubble"),
]
_BROAD = {"tone_wording"}
_COMP = [(c, re.compile(p)) for c, p in _CONCEPTS]
SPECIFIC = {c for c, _ in _CONCEPTS} - _BROAD


def concept_tags(fb):
    s = (fb or "").lower()
    return {c for c, rx in _COMP if rx.search(s)}


def clean_client(v):
    v = (v or "").strip()
    return v.split(" (http")[0].strip() if v else ""


def split_pics(v):
    v = (v or "").strip()
    return [p.strip() for p in v.split(",") if p.strip()] if v else []


def hhi(shares):
    return round(sum(s * s for s in shares), 3)


# Per-task-type effort weights. Priority is intentionally NOT used here — it is
# urgency, not effort. These are placeholders (all 1.0) until the FDE interview
# gives real "how long does each task type take" weights; then map concept ->
# weight here and the index sharpens with zero other changes.
TASK_EFFORT: dict[str, float] = {}   # e.g. {"scoping": 2.5, "tone_wording": 0.7}


def cost_to_serve(rows):
    """Effort-weighted per-client index. Effort = ticket volume inflated by REWORK
    only: each ticket is 1 point, +0.5 if it sits in a recurring concept group,
    +0.5 if QA-failed (redoing work costs more). Priority is excluded on purpose
    (urgency != effort). crit_high_share is still reported, but as a SEPARATE
    urgency signal, never folded into effort. No hours, no dollars."""
    byc = defaultdict(list)
    for r in rows:
        cl = clean_client(r.get("Client Page"))
        if cl:
            byc[cl].append(r)
    out = []
    for cl, items in byc.items():
        groups = defaultdict(list)
        for r in items:
            for c in (concept_tags(r.get("Feedback") or "") & SPECIFIC):
                groups[c].append(id(r))
        recur = {i for _, m in groups.items() if len(m) >= 2 for i in m}
        tickets, effort, crit_high, qaf = len(items), 0.0, 0, 0
        for r in items:
            pr = (r.get("Priority") or "").strip().upper()
            tags = concept_tags(r.get("Feedback") or "")
            tw = max((TASK_EFFORT.get(t, 1.0) for t in tags), default=1.0)
            is_qa = (r.get("Status") or "").strip() == "QA Failed"
            if pr in ("CRITICAL", "HIGH"):
                crit_high += 1
            if is_qa:
                qaf += 1
            effort += tw * (1 + 0.5 * (id(r) in recur) + 0.5 * is_qa)
        out.append({
            "client": cl, "tickets": tickets, "effort": round(effort, 1),
            "eff_per_ticket": round(effort / tickets, 2) if tickets else 0,
            "crit_high_share": round(crit_high / tickets, 2) if tickets else 0,
            "qa_failed": qaf,
        })
    out.sort(key=lambda x: -x["effort"])
    return out


def load(csv_path):
    rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
    for r in rows:
        if "﻿Feedback" in r:
            r["Feedback"] = r.pop("﻿Feedback")
    return rows


def compute(rows, anonymize=True):
    pair, pic_tot, cli_tot = defaultdict(float), defaultdict(float), defaultdict(float)
    by_client_fb, qaf, cli_all = defaultdict(list), defaultdict(int), defaultdict(int)
    for r in rows:
        cl = clean_client(r.get("Client Page"))
        if not cl:
            continue
        cli_all[cl] += 1
        if (r.get("Status") or "").strip() == "QA Failed":
            qaf[cl] += 1
        fb = (r.get("Feedback") or "").strip()
        if fb:
            by_client_fb[cl].append(fb)
        ps = split_pics(r.get("PIC"))
        if ps:
            w = 1.0 / len(ps)
            for p in ps:
                pair[(p, cl)] += w
                pic_tot[p] += w
                cli_tot[cl] += w

    order = sorted(pic_tot, key=lambda p: -pic_tot[p])
    label = ({p: f"FDE-{chr(65 + i)}" for i, p in enumerate(order)} if anonymize
             else {p: p for p in order})

    by_fde = []
    for p in order:
        tot = pic_tot[p]
        cls = {c: pair[(p, c)] for c in cli_tot if pair.get((p, c), 0) > 0}
        top = max(cls.items(), key=lambda kv: kv[1])
        by_fde.append({
            "fde": label[p], "tickets": round(tot, 1), "clients": len(cls),
            "top_client": top[0], "top_share": round(top[1] / tot, 3),
            "hhi": hhi([v / tot for v in cls.values()]),
            "breakdown": {c: round(v, 1) for c, v in sorted(cls.items(), key=lambda kv: -kv[1])},
        })

    by_client = []
    for cl in sorted(cli_tot, key=lambda c: -cli_tot[c]):
        tot = cli_tot[cl]
        fs = {label[p]: pair[(p, cl)] for p in pic_tot if pair.get((p, cl), 0) > 0}
        top = max(fs.items(), key=lambda kv: kv[1])
        by_client.append({
            "client": cl, "tickets": round(tot, 1), "fdes": len(fs),
            "top_fde": top[0], "top_share": round(top[1] / tot, 3),
            "hhi": hhi([v / tot for v in fs.values()]), "single_person": len(fs) == 1,
            "breakdown": {f: round(v, 1) for f, v in sorted(fs.items(), key=lambda kv: -kv[1])},
        })

    # concept-based recurrence
    recurrence, groups_out = [], []
    for cl in sorted(cli_all, key=lambda c: -cli_all[c]):
        groups = defaultdict(list)
        for fb in by_client_fb[cl]:
            for c in (concept_tags(fb) & SPECIFIC):
                groups[c].append(fb)
        recur = set()
        for c, mem in groups.items():
            if len(mem) >= 2:
                recur.update(mem)
                examples = list(dict.fromkeys(m[:44] for m in mem))[:3]
                groups_out.append({"size": len(mem), "client": cl, "concept": c,
                                   "examples": examples})
        n = cli_all[cl]
        recurrence.append({
            "client": cl, "tickets": n, "in_recur": len(recur),
            "rate": round(len(recur) / n, 3) if n else 0, "qa_failed": qaf[cl],
        })
    groups_out.sort(key=lambda g: -g["size"])

    return {
        "by_fde": by_fde, "by_client": by_client,
        "recurrence": recurrence, "groups": groups_out[:24],
        "cost_to_serve": cost_to_serve(rows),
        "totals": {
            "tickets": sum(cli_all.values()), "clients": len(cli_all),
            "fdes": len(order),
            "single_person_clients": sum(1 for c in by_client if c["single_person"]),
        },
    }


_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Capacity & Recurrence — Labor Hours</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
:root{--bg:#0f1117;--card:#181b24;--txt:#e6e9f0;--mut:#8b93a7;--ok:#4cc38a;--warn:#f0b429;--bad:#e5534b;--blue:#7ba3f5;--purp:#a371f7}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:24px}
h1{font-size:22px;margin-bottom:4px}h2{font-size:15px;margin:0 0 12px}
.sub{color:var(--mut);margin-bottom:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.kpi{background:var(--card);border-radius:10px;padding:14px}
.kpi .v{font-size:26px;font-weight:700}.kpi .l{color:var(--mut);font-size:12px}
.kpi.alert .v{color:var(--bad)}
.card{background:var(--card);border-radius:12px;padding:16px;margin-bottom:16px}
.donutgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.donutcell{background:#0f1117;border:1px solid #23283570;border-radius:10px;padding:12px}
.dn-title{font-size:14px;font-weight:600}.dn-sub{color:var(--mut);font-size:11px;margin-bottom:6px}
.donutcell canvas{max-height:230px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{color:var(--mut);text-align:left;padding:6px 8px;border-bottom:1px solid #2a2f3e;font-weight:600}
td{padding:6px 8px;border-bottom:1px solid #23283573;vertical-align:top}
.chip{display:inline-block;border-radius:10px;padding:1px 8px;font-size:11px;font-weight:600}
.c-bad{background:#3a1512;color:var(--bad)}.c-warn{background:#3a2b10;color:var(--warn)}.c-ok{background:#11341f;color:var(--ok)}
.tag{display:inline-block;background:#1c2333;color:var(--blue);border-radius:6px;padding:1px 7px;font-size:12px}
.note{color:var(--mut);font-size:12px;margin-top:8px}
@media(max-width:900px){}
</style></head><body>
<h1>Capacity &amp; Recurrence</h1>
<div class="sub">Client allocation and rework signal from the ticket snapshot. Counts only.</div>
<div class="kpis" id="kpis"></div>

<div class="card"><h2>Cost-to-serve index — effort-weighted, not raw ticket count</h2>
  <div style="position:relative;height:560px"><canvas id="cCost"></canvas></div>
  <div class="note">Each ticket is one unit of work, plus up to 50% for rework (recurring or QA-failed). Priority is excluded on purpose — it's urgency, not effort. Real per-task-type effort weights slot in after the FDE interview. Hover for intensity per ticket.</div></div>

<div class="card"><h2>Where each FDE's week goes — client allocation</h2>
  <div class="donutgrid" id="donuts"></div>
  <div class="note">Each donut is one person's ticket mix. Dominated by one color = concentrated on a single client (HHI shown per person).</div></div>

<div class="card"><h2>Key-person risk — top FDE's share of each client's tickets</h2>
  <div style="position:relative;height:640px"><canvas id="cRisk"></canvas></div>
  <div class="note">Red = one person carries 100% of the client. If they're out, the client has no one with context.</div></div>

<div class="card"><h2>Recurrence — share of a client's tickets in a recurring problem area</h2>
  <div style="position:relative;height:560px"><canvas id="cRec"></canvas></div>
  <div class="note">Concept-based: same underlying issue re-ticketed even when worded differently. Hover for QA-failed count. This is problem-area recurrence, not one identical bug re-filed.</div></div>

<div class="card"><h2>Recurring problem groups — where unfixed work piles up</h2>
  <table><thead><tr><th>Count</th><th>Client</th><th>Problem area</th><th>Examples</th></tr></thead><tbody id="groups"></tbody></table></div>

<script>
const DATA = __DATA__;
const C={ok:"#4cc38a",warn:"#f0b429",bad:"#e5534b",blue:"#7ba3f5",purp:"#a371f7",mut:"#565e72"};
const palette=[C.blue,C.ok,C.warn,C.purp,"#e07b53","#53c9c9","#c953a0","#8a8a8a","#5d78c9"];
Chart.defaults.color="#8b93a7";Chart.defaults.borderColor="#23283573";

const t=DATA.totals;
document.getElementById("kpis").innerHTML=[
  ["Tickets",t.tickets,""],["Clients",t.clients,""],["FDEs",t.fdes,""],
  ["Single-person clients",t.single_person_clients,"alert"]
].map(([l,v,c])=>`<div class="kpi ${c}"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");

const cts=DATA.cost_to_serve.filter(c=>c.tickets>=5);
new Chart(cCost,{type:"bar",data:{labels:cts.map(c=>c.client),
  datasets:[{data:cts.map(c=>c.effort),
    backgroundColor:cts.map(c=>c.eff_per_ticket>=1.5?C.bad:c.eff_per_ticket>=1.25?C.warn:C.blue),borderRadius:4}]},
  options:{indexAxis:"y",maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>`${c.raw} effort pts · ${cts[c.dataIndex].tickets} tickets · ${cts[c.dataIndex].eff_per_ticket}/ticket · ${Math.round(cts[c.dataIndex].crit_high_share*100)}% crit+high`}}},
    scales:{x:{title:{display:true,text:"effort points (cost to serve)"}}}}});

const dg=document.getElementById("donuts");
DATA.by_fde.forEach((f,idx)=>{
  const cell=document.createElement("div");cell.className="donutcell";
  cell.innerHTML=`<div class="dn-title">${f.fde}</div><div class="dn-sub">${f.tickets} tickets · ${f.clients} clients · HHI ${f.hhi}</div><canvas id="dn${idx}"></canvas>`;
  dg.appendChild(cell);
  const cl=Object.keys(f.breakdown),vals=Object.values(f.breakdown);
  new Chart(cell.querySelector("canvas"),{type:"doughnut",
    data:{labels:cl,datasets:[{data:vals,backgroundColor:cl.map((_,i)=>palette[i%palette.length]),borderWidth:2,borderColor:"#0f1117"}]},
    options:{cutout:"55%",plugins:{legend:{position:"bottom",labels:{boxWidth:10,font:{size:10},padding:6}},
      tooltip:{callbacks:{label:c=>`${c.label}: ${c.raw} (${Math.round(100*c.raw/f.tickets)}%)`}}}}});
});

const risk=DATA.by_client.filter(c=>c.tickets>=5);
new Chart(cRisk,{type:"bar",data:{labels:risk.map(c=>c.client),
  datasets:[{data:risk.map(c=>Math.round(c.top_share*100)),
    backgroundColor:risk.map(c=>c.single_person?C.bad:c.top_share>=0.8?C.warn:C.blue),borderRadius:4}]},
  options:{indexAxis:"y",maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>`${c.raw}% carried by ${risk[c.dataIndex].top_fde} (${risk[c.dataIndex].fdes} FDE${risk[c.dataIndex].fdes>1?'s':''})`}}},
    scales:{x:{max:100,title:{display:true,text:"% by top FDE"}}}}});

const rec=DATA.recurrence.filter(r=>r.tickets>=5);
new Chart(cRec,{type:"bar",data:{labels:rec.map(r=>r.client),
  datasets:[{data:rec.map(r=>Math.round(r.rate*100)),
    backgroundColor:rec.map(r=>r.rate>=0.4?C.bad:r.rate>=0.2?C.warn:C.blue),borderRadius:4}]},
  options:{indexAxis:"y",maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>`${c.raw}% in recurring areas · ${rec[c.dataIndex].in_recur}/${rec[c.dataIndex].tickets} tickets · ${rec[c.dataIndex].qa_failed} QA-failed`}}},
    scales:{x:{title:{display:true,text:"% of tickets in a recurring problem area"}}}}});

document.getElementById("groups").innerHTML=DATA.groups.map(g=>
  `<tr><td><span class="chip ${g.size>=8?'c-bad':g.size>=4?'c-warn':'c-ok'}">x${g.size}</span></td><td>${g.client}</td><td><span class="tag">${g.concept}</span></td><td style="color:#8b93a7">${g.examples.map(e=>e.replace(/</g,'&lt;')).join(" · ")}</td></tr>`).join("");
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default="tickets.csv")
    ap.add_argument("--out", default="capacity_recurrence_dashboard.html")
    ap.add_argument("--real-names", action="store_true",
                    help="label people by real name instead of FDE-A/B/C")
    args = ap.parse_args()
    data = compute(load(args.csv), anonymize=not args.real_names)
    html = _HTML.replace("__DATA__", json.dumps(data))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {args.out}  ({len(html)} bytes)")
    print(f"  {data['totals']['tickets']} tickets, {data['totals']['clients']} clients, "
          f"{data['totals']['single_person_clients']} single-person clients")


if __name__ == "__main__":
    main()
