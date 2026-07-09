"""Change Type auto-classifier (instrumentation gap #2: the 41% "Untyped").

`notion_sync` copies the Notion "Change Type" select verbatim, so tickets an
engineer never typed stay NULL forever. Those NULLs starve three metrics that key
off task category:
  * Active hours by task category (org-wide & per client)
  * Per-FDE/SL task-type mix
  * Task-type mix per client

This worker reads a ticket's Feedback title and proposes one of the four
issue-nature buckets from `change_types` (db/02_seed.sql): Tool Issue,
Behavioral Issue, Flow Issue, Data Processing. It NEVER overwrites a human-set value:
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
# "AI Fix"/"PRD Change" are the HUMAN values engineers set in Notion — they stay
# valid but the classifier never proposes them. Inferences use the four
# issue-nature buckets below (taxonomy revised 2026-07-09 per Harvey).
TAXONOMY = [
    "AI Fix",
    "PRD Change",
    "Tool Issue",         # problem with the tool/product itself
    "Behavioral Issue",   # styling/tone not human-agent-like; aggressive nudging
    "Flow Issue",         # lead->sale stages: first contact -> data collection -> checkout
    "Data Processing",    # misinterpreting user meaning / misunderstanding collected data
    "Other",
]

# Weighted keyword rules. Each entry: (category, weight, pattern, why).
# Scoring (not first-match) avoids order bugs — a title matching several buckets
# goes to the highest summed weight, e.g. "wording of payment confirmation" is
# Behavioral (wording 3) over Flow (checkout 2).
#   weight 3 = strong signal, 2 = medium, 1 = weak/supporting.
_RULES: list[tuple[str, int, str, str]] = [
    # --- Tool Issue: the tool/product itself malfunctions ----------------------
    ("Tool Issue", 3, r"\berror(s)?\b", "error"),
    ("Tool Issue", 3, r"\b(bug|crash|broken)\b", "broken tool"),
    ("Tool Issue", 3, r"\bdoesn'?t (save|work|load|sync|send|trigger|exist)\b", "tool malfunction"),
    ("Tool Issue", 3, r"\bapi\b", "API"),
    ("Tool Issue", 2, r"\bfail(s|ed|ing)?\b", "failure"),
    ("Tool Issue", 2, r"\b(tool|webhook|endpoint|integration|portal|dashboard)\b", "tool noun"),
    ("Tool Issue", 2, r"\bnot (working|saving|sending|loading)\b", "not working"),
    ("Tool Issue", 1, r"\b(sheet|calendar|logger|checkpoint)\b", "tool surface"),

    # --- Behavioral Issue: styling/tone, not what a human agent would say ------
    ("Behavioral Issue", 3, r"\b(tone|wording|phras\w*|styling|stylistic)\b", "tone/wording"),
    ("Behavioral Issue", 3, r"\b(too formal|informal|emoji)\w*", "register/emoji"),
    ("Behavioral Issue", 3, r"\b(pushy|aggressive|nudg\w*)", "aggressive nudging"),
    ("Behavioral Issue", 2, r"\b(too long|too short|text wall|overly)\b", "verbosity"),
    ("Behavioral Issue", 2, r"\brepetit\w*|\brepeat(s|ed|ing)?\b|\bredundant\b", "repetition"),
    ("Behavioral Issue", 2, r"\b(unnatural|natural|robotic|human)\b", "doesn't sound human"),
    ("Behavioral Issue", 2, r"\b(greeting|salutation)\b", "greeting style"),
    ("Behavioral Issue", 2, r"\b(contradict\w*|disjointed)\b", "contradictory messaging"),
    ("Behavioral Issue", 1, r"\b(bubble|message|response|reply|say(s|ing)?)\b", "response element"),

    # --- Flow Issue: lead->sale stage handling ---------------------------------
    ("Flow Issue", 3, r"\bescalat\w*", "escalation step"),
    ("Flow Issue", 3, r"\bflow\b", "flow"),
    ("Flow Issue", 2, r"\b(step|stage|sop)\b", "stage/SOP"),
    ("Flow Issue", 2, r"\b(checkout|payment|cart|purchase|invoice)\b", "checkout stage"),
    ("Flow Issue", 2, r"\bbook(ing|ed|s)?\b", "booking stage"),
    ("Flow Issue", 2, r"\bregist(er|ers|ered|ration)\b", "registration stage"),
    ("Flow Issue", 2, r"\b(lead status|lead\b|routing|rerout\w*|handoff)\b", "lead routing"),
    ("Flow Issue", 2, r"\b(should|doesn'?t|didn'?t) ask\b", "data-collection ask"),
    ("Flow Issue", 2, r"\bfollow[- ]?up\b", "follow-up stage"),
    ("Flow Issue", 1, r"\bform\b", "form"),
    ("Flow Issue", 1, r"\bconfirm\w*\b", "confirmation step"),

    # --- Data Processing: misreading the user / mishandling collected data -----
    ("Data Processing", 3, r"\bhallucinat\w*", "hallucinated data"),
    ("Data Processing", 3, r"\b(misunderst|misread|misinterpret)\w*", "misinterpretation"),
    ("Data Processing", 3, r"\bwrong (date|day|time|name|number|info|schedule|price|answer)\b", "wrong data value"),
    ("Data Processing", 2, r"\bconfus\w*", "confusion"),
    ("Data Processing", 2, r"\b(wrong|incorrect|inaccurate|falsely)\b", "incorrect output"),
    ("Data Processing", 2, r"\bassum(es|ed|ing|ption)?\b", "wrong assumption"),
    ("Data Processing", 2, r"\binvent(s|ed|ing)?\b", "fabricated data"),
    ("Data Processing", 2, r"\b(availab\w*|unavailab\w*)\b", "availability data"),
    ("Data Processing", 1, r"\b(date|birthday|format\w*)\b", "date/format handling"),
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

    `has_trace`: kept for signature compatibility. It used to nudge toward the
    human "AI Fix" label, but since the 2026-07-09 taxonomy revision the
    classifier only proposes the four issue-nature buckets, so it is a no-op.
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
