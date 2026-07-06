"""Change Type auto-classifier (instrumentation gap #2: the 41% "Untyped").

`notion_sync` copies the Notion "Change Type" select verbatim, so tickets an
engineer never typed stay NULL forever. Those NULLs starve three metrics that key
off task category:
  * Active hours by task category (org-wide & per client)
  * Per-FDE/SL task-type mix
  * Task-type mix per client

This worker reads a ticket's Feedback title and proposes one of the 8 taxonomy
types from `change_types` (db/02_seed.sql). It NEVER overwrites a human-set value:
it only scans tickets where `change_type IS NULL`, and it writes to its own table
(`change_type_inferences`, db/04). The `v_change_type_effective` view then serves
COALESCE(human, inferred) so a real engineer label always wins.

Design mirrors the other leaf workers (conversations.py, microview.py): a pure,
testable core (`classify`) plus a thin DB `run_once`. The rule scorer is stdlib
only, so it is unit-testable with zero DB and zero credentials. An optional LLM
escalation for low-confidence cases is stubbed the same way microview stubs Gemini.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

# NOTE: `db` is imported lazily inside run_once() (see below) so that the pure
# classifier core imports with zero dependencies and stays unit-testable in
# isolation. Only the DB path needs the repo's asyncpg pool.

# The authoritative taxonomy (must match change_types in db/02_seed.sql).
TAXONOMY = [
    "AI Fix",
    "PRD Change",
    "Client Comms",
    "Testing/QA",
    "Scoping/Spec Creation",
    "Monitoring/Confirmation",
    "Training",
    "Other",
]

# Weighted keyword rules. Each entry: (category, weight, pattern, why).
# Scoring (not first-match) avoids order bugs, e.g. "Fix English in payment
# confirmation" must score AI Fix on "fix", NOT Monitoring on "confirmation" —
# so Monitoring intentionally does not match the bare noun "confirmation".
#   weight 3 = strong signal, 2 = medium, 1 = weak/supporting.
_RULES: list[tuple[str, int, str, str]] = [
    # --- AI Fix: the agent's behaviour/output is wrong and needs correcting ---
    ("AI Fix", 3, r"\bfix(es|ed|ing)?\b", "'fix' verb"),
    ("AI Fix", 3, r"\bhallucinat", "hallucination"),
    ("AI Fix", 3, r"\binvent(s|ing|ed)?\b", "inventing content"),
    ("AI Fix", 3, r"\berror(s)?\b", "error"),
    ("AI Fix", 3, r"\b(wrong|incorrect|broken|bug)\b", "wrong/broken"),
    ("AI Fix", 2, r"\b(too long|too short|overall too)\b", "output length"),
    ("AI Fix", 2, r"\brepetit|repeat(s|ing|ed)?\b", "repetition"),
    ("AI Fix", 2, r"\b(hallucinating|inventing) (phone|name|price|schedule)", "fabricated field"),
    ("AI Fix", 2, r"\b(pushy|tone|wording|phrasing|language)\b", "tone/wording"),
    ("AI Fix", 2, r"\b(should( not)? escalate|mis-?escalat)", "escalation behaviour"),
    ("AI Fix", 2, r"\b(pricing|price)\b", "pricing output"),
    ("AI Fix", 1, r"\b(greeting|salutation|cta|response|output|reply|prompt\d*)\b", "response element"),
    ("AI Fix", 1, r"\bconsistent\b", "consistency"),

    # --- PRD Change: new/changed product requirement, tool, or integration ----
    ("PRD Change", 3, r"\bintegrat", "integration"),
    ("PRD Change", 3, r"\bimplement", "implement"),
    ("PRD Change", 2, r"\b(build|develop|create)\b", "build/create"),
    ("PRD Change", 2, r"\bregister\b", "register"),
    ("PRD Change", 2, r"\b(tool|feature|webhook|endpoint)\b", "tool/feature noun"),
    ("PRD Change", 2, r"\bnew (tool|feature|flow|page|button|integration)\b", "new capability"),
    ("PRD Change", 2, r"\b(set ?up|enable)\b", "setup/enable"),
    ("PRD Change", 1, r"\badd (a |an |the )?\w+", "add capability"),

    # --- Client Comms: outbound communication to/for the client ---------------
    ("Client Comms", 2, r"\bbrochure\b", "brochure"),
    ("Client Comms", 2, r"\b(email|message|reach out|follow[- ]?up)\b.*\bclient\b", "contact client"),
    ("Client Comms", 2, r"\bsend .*(to (the )?client|brochure|artifact)\b", "send to client"),
    ("Client Comms", 1, r"\b(comms|communicat)\w*", "comms"),

    # --- Testing / QA ---------------------------------------------------------
    ("Testing/QA", 3, r"\bqa\b", "QA"),
    ("Testing/QA", 3, r"\btest(s|ing|ed)?\b", "testing"),
    ("Testing/QA", 2, r"\b(regression|retest|reproduc)", "regression/reproduce"),
    ("Testing/QA", 2, r"\bverify that\b", "verification"),

    # --- Scoping / Spec Creation ----------------------------------------------
    ("Scoping/Spec Creation", 3, r"\bscop(e|ing)\b", "scoping"),
    ("Scoping/Spec Creation", 2, r"\b(spec|specification|requirements?)\b", "spec/requirements"),
    ("Scoping/Spec Creation", 2, r"\bprd creation\b", "PRD creation"),

    # --- Monitoring / Confirmation (verbs only — never the noun 'confirmation')
    ("Monitoring/Confirmation", 3, r"\bmonitor(s|ing|ed)?\b", "monitoring"),
    ("Monitoring/Confirmation", 3, r"\bwatchtower\b", "Watchtower"),
    ("Monitoring/Confirmation", 2, r"\b(keep an eye|sanity check|reconfirm)\b", "ongoing check"),

    # --- Training -------------------------------------------------------------
    ("Training", 3, r"\btrain(s|ing|ed)?\b", "training"),
    ("Training", 2, r"\bonboard", "onboarding"),
    ("Training", 2, r"\b(sop|write .*guide|document how|teach)\b", "docs/teaching"),
]

_COMPILED = [(cat, w, re.compile(pat, re.IGNORECASE), why) for cat, w, pat, why in _RULES]


@dataclass
class Classification:
    category: str | None            # a TAXONOMY entry, or None if unclassifiable
    confidence: str                 # high | medium | low
    score: int                      # winning category's summed weight
    matched: list[str] = field(default_factory=list)  # human-readable rule hits

    @property
    def rule(self) -> str:
        return "; ".join(self.matched) if self.matched else "no-signal"


def classify(feedback: str | None, has_trace: bool = False) -> Classification:
    """Score `feedback` against the rule set and return the best taxonomy match.

    `has_trace`: pass True when the ticket has a Langsmith trace URL. A trace means
    an agent run was inspected, which nudges toward AI Fix. It defaults False
    because notion_sync does not currently sync that column (see README).
    """
    text = (feedback or "").strip()
    if not text:
        return Classification(None, "low", 0, [])

    scores: dict[str, int] = {c: 0 for c in TAXONOMY}
    hits: dict[str, list[str]] = {c: [] for c in TAXONOMY}
    for cat, weight, rx, why in _COMPILED:
        if rx.search(text):
            scores[cat] += weight
            hits[cat].append(why)

    if has_trace:
        scores["AI Fix"] += 1
        hits["AI Fix"].append("has Langsmith trace")

    best = max(TAXONOMY, key=lambda c: scores[c])
    top = scores[best]
    if top == 0:
        # Nothing matched: propose "Other" but flag it low so a human reviews.
        return Classification("Other", "low", 0, [])

    confidence = "high" if top >= 3 else "medium" if top == 2 else "low"
    return Classification(best, confidence, top, hits[best])


# ---------------------------------------------------------------------------
# DB layer — scans untyped tickets, records proposals. Never touches tickets.
# ---------------------------------------------------------------------------
async def run_once(min_confidence: str = "low") -> dict:
    """Classify every untyped ticket and upsert proposals into
    change_type_inferences. `min_confidence` gates what gets written
    ('low' writes everything; 'medium'/'high' hold back weak guesses)."""
    from .. import db  # lazy: keeps the classifier core dependency-free

    order = {"low": 0, "medium": 1, "high": 2}
    floor = order[min_confidence]

    rows = await db.fetch(
        "SELECT id, feedback FROM tickets "
        "WHERE change_type IS NULL AND feedback IS NOT NULL AND feedback <> ''"
    )
    written = 0
    for r in rows:
        result = classify(r["feedback"])
        if result.category is None or order[result.confidence] < floor:
            continue
        await db.execute(
            "INSERT INTO change_type_inferences "
            "(ticket_id, inferred_type, confidence, method, matched_rule) "
            "VALUES ($1, $2, $3, 'rules', $4) "
            "ON CONFLICT (ticket_id) DO UPDATE SET "
            "  inferred_type = EXCLUDED.inferred_type, "
            "  confidence    = EXCLUDED.confidence, "
            "  method        = EXCLUDED.method, "
            "  matched_rule  = EXCLUDED.matched_rule, "
            "  created_at    = now()",
            r["id"], result.category, result.confidence, result.rule,
        )
        written += 1
    return {
        "scanned": len(rows),
        "inferred": written,
        "at": datetime.now(timezone.utc).isoformat(),
    }


async def classify_llm(feedback: str) -> Classification:  # pragma: no cover
    """STUB — later escalation for low-confidence cases. Wire an LLM call here
    (same pattern as microview's Gemini step). Until then, run_once uses rules
    only. Kept so the escalation seam is obvious to the next person."""
    raise NotImplementedError("LLM escalation not wired yet; rules-only for now.")
