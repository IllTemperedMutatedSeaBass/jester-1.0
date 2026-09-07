"""Per-document tier assignment at ingest, per DR-031: provenance/authority,
not volume or sensitivity. Safe default for anything not clearly a
governance instrument is UNASSIGNED (non-triggering, available for
retrieval once tiered, inert until then) -- never default to TIER1.

This module implements ONE heuristic (filename/path keyword match against
DR-008's own Tier-1 list: board pack, minutes/resolutions, policies, risk
register, articles, delegation-of-authority matrix, material contract
obligations, open regulatory correspondence) because that is what DR-031
explicitly derives the test FROM. It is deliberately conservative: DR-031's
own worked reasoning is that manufacturing false Tier-1 triggers is the
failure DR-008 exists to prevent, so ambiguous cases fall to UNASSIGNED
rather than being guessed into TIER1. Every assignment records the matched
evidence so a human can audit or correct it -- this is NOT a claim that
keyword matching is a durable tiering mechanism; it is the smallest thing
that satisfies "per-document, on provenance, logged" for a first ingest run
of a small (~24 document) corpus. A future session should expect to replace
this with something that reads document content/metadata once the corpus
outgrows a hand-auditable size.

TIER 2 (law/standards) is not assigned by this heuristic at all: the DHI_IN
survey (thread D1) found no legislation or standards text on the volume, so
there is nothing for it to classify into Tier 2a/2b yet. The reject path
(DR-009 / DR-031: ISO/IEC standards text may not be stored in any tier) is
therefore implemented but, on this corpus, expected to fire zero times --
recorded as such rather than silently omitted.
"""
from __future__ import annotations

import re

TIER1 = "tier1"
TIER2A = "tier2a"
UNASSIGNED = "unassigned"
REJECTED = "rejected"

# DR-008's own Tier-1 list, as keyword stems matched case-insensitively
# against the file's path (directory names carry real signal here, e.g.
# "Executive board", "Risk & compliance").
_TIER1_KEYWORDS = {
    "board pack": "board",
    "minutes": "minutes",
    "resolution": "resolutions",
    "policy": "policy",
    "polic": "policy",
    "risk register": "risk register",
    "risk & compliance": "risk & compliance (policy/process-of-record adjacent)",
    "articles": "articles",
    "entity-structure": "entity structure (articles-adjacent)",
    "delegation": "delegation-of-authority",
    "contract": "material contract obligations",
    "regulatory": "open regulatory correspondence",
    "aims-process": "AIMS process map (governance instrument)",
    "management-review": "management review input pack (governance instrument)",
    "executive board": "executive board (governance instrument)",
    "org-chart_ai-governance": "AI governance org chart (governance instrument)",
}

# Reject path: raw ISO/IEC standards text may never be stored, in any tier
# (DR-009, DR-031). Heuristic only -- there is no such text in this corpus
# to validate against, so this is a placeholder discipline, not a tuned
# classifier.
_STANDARDS_TEXT_MARKERS = (
    "iso_iec", "iso-iec", "iso/iec", "standard-text", "standard_text",
)


def classify(relative_path: str, text: str) -> tuple[str, str]:
    """Returns (tier, evidence). `relative_path` is the document's path
    under Jester_IN, forward-slash separated, lowercased for matching."""
    lower_path = relative_path.lower()
    lower_text = (text or "")[:2000].lower()  # cheap: first ~2000 chars only

    for marker in _STANDARDS_TEXT_MARKERS:
        if marker in lower_path or marker in lower_text:
            return REJECTED, f"matched standards-text marker '{marker}' (DR-009)"

    for keyword, evidence in _TIER1_KEYWORDS.items():
        if keyword in lower_path:
            return TIER1, f"path matched Tier-1 keyword '{keyword}' -> {evidence}"

    return UNASSIGNED, "no Tier-1 governance-instrument keyword matched in path; safe default per DR-031"
