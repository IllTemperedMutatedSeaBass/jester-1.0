# DR-043 — The tier partition is removed as a trigger control

- **Status:** Accepted
- **Date:** 2026-09-10
- **Thread:** 1.0.16
- **Supersedes / Superseded by:** Narrows DR-008's trigger-authority partition;
  amends DR-035's intent gate. Neither entry is edited — both stand as filed and
  this entry records what changes.

## Context

DR-008 split the corpus in two and gave trigger authority to one side of the
split: "TIER 1 — THE COMPANY… THIS IS THE ONLY TRIGGER SOURCE. C3 fires off
Tier 1," against "TIER 2 — LAW AND STANDARDS… Queried ONLY after Tier 1 has
flagged a candidate, to confirm and cite. NEVER a trigger source on its own."

That ruling has shaped everything since. DR-029 added a third trigger path
(Tier 2b derived criteria) while explicitly preserving DR-008's prohibition on
retrieval-as-trigger over bulk text. DR-031 made tier a per-document
provenance judgement with a non-triggering safe default. DR-034 ingested 46
documents and tiered 5 as TIER1 and 41 as UNASSIGNED. DR-035 wired retrieval
into C2 as three named paths over four collections and gated the unassigned
path on `intent == "question_answering"` so that a trigger caller could not
reach it.

This thread builds C3 — the component that actually fires. That forces the
question DR-008 has been answering by proxy for eight threads: is the tier
partition a fact about the domain, or a control on a mechanism?

Frozen constraints in play: DR-009 (standards text never ships), DR-030
(isolation posture), DR-031 (provenance, non-triggering safe default),
DR-033 (embedding pin), DR-042 (rate ceiling and batching).

## Options considered

Axes: fidelity to DR-008's measured evidence; whether the product's central
finding is reachable; where the noise control lands and whether it is
enforceable; cost to unwind.

- **Option A — keep the partition as filed.** Trigger authority stays with Tier 1.
  Maximally faithful to the one measurement this project has. Forbids the
  cross-document finding described below, and on this box confines the trigger
  path to 5 of 46 documents.
- **Option B — keep the partition and re-tier the corpus.** Promote documents out
  of UNASSIGNED until Tier 1 is big enough to be useful. Cheaper politically, but
  it treats a 41-of-46 skew as a labelling error when the skew is partly real,
  and it does not touch the structural problem: a conflict BETWEEN a Tier 1
  instrument and a Tier 2 obligation is still unreachable, whatever the ratio.
- **Option C — remove the partition as a trigger control, keep it as metadata
  (CHOSEN).** One corpus for trigger evaluation; licensing, authority and
  provenance survive as properties of chunks rather than as gates on them; the
  noise control relocates to a reasoning gate plus DR-042's ceiling.

## Decision

**(a) THE PARTITION WAS A NOISE CONTROL FOR A MECHANISM, NOT A FACT ABOUT THE
DOMAIN.** DR-008's evidence was specific and is not disputed: similarity search
over a large, generic, lexically-overlapping corpus always returns a
nearest-neighbour chunk, which flipped 4 of 6 correctly-Absent records to
false-positive Partial in 2.x. That is a finding about **RETRIEVAL-AS-TRIGGER** —
a cosine threshold standing in for a judgement. It was never evidence that
company documents and standards documents are different KINDS of thing.

**(b) THE PARTITION FORBIDS THE PRODUCT'S CENTRAL FINDING.** Where the value is
logical connectivity — a delegated-authority matrix says one thing, a regulatory
obligation says another, and the plan forming in the room sits in the gap — the
insight **LIVES IN THE JOIN BETWEEN DOCUMENTS**. Tier 1 alone cannot see it;
Tier 2 is forbidden to raise it. The architecture excludes the finding it exists
to produce.

**(c) RULING: retrieval for trigger evaluation runs over ONE corpus.** The tier
partition is removed as a control on **TRIGGER AUTHORITY**.

**(d) WHAT SURVIVES, AS METADATA ON EVERY CHUNK, NOT AS A GATE:**

- **LICENSING. DR-009 stands entirely.** Standards text is never shipped; chunks
  carry a licence flag and licence-restricted text must not be reproduced in
  spoken output. This is unaffected by (c). **See the honesty note below — the
  licence flag does not exist in the store today.**
- **AUTHORITY.** A company policy binds; a standard is advisory. This is a
  property Jester **STATES WHEN IT SPEAKS**, not a gate on whether it may notice.
  Every flag must name what it conflicts with and the authority weight of that
  source.
- **PROVENANCE**, per DR-031, retained on every chunk.

**(e) THE NOISE CONTROL IS RELOCATED, NOT DELETED.** It moves from "which
documents may fire" to (i) a **REASONING GATE** deciding whether a contradiction
is worth raising, and (ii) DR-042's rate ceiling as a hard backstop.

**(f) DR-035'S INTENT GATE IS A CONSEQUENCE OF THIS RULING, NOT A SEPARATE
DECISION.** DR-035 restricted the unassigned collection to
`intent="question_answering"` and asserts the refusal of a trigger caller by
test. That gate exists ONLY to enforce the partition (c) removes; leaving it in
place would be an inconsistency, not a safeguard. It is amended so a
trigger-side caller may read the unified corpus. The existing test is
**REWRITTEN to assert the new rule, not deleted.**

A **NEW intent name, `conflict_check`**, is used rather than reusing
`question_answering`. **This is a PREFERENCE, not a necessity.** Its reason:
DR-045's scoring must distinguish "a human asked and Jester answered" from
"Jester decided on its own to look." Reusing the existing intent would work
mechanically and would make those two cases indistinguishable in the logs that
become the evaluation set.

**(g) THE 41-OF-46 UNASSIGNED SKEW (DR-034) LARGELY DISSOLVES AS A C3 BLOCKER**
under (c) — there is no longer a tier the trigger path is confined to.
Re-tiering becomes ordinary backlog work. **This is not a claim that the skew is
harmless.** Its remaining value is licence and authority labelling, which (d)
still needs and which (d) currently cannot deliver.

## Rationale

The argument turns on what DR-008 actually measured. It measured a mechanism
failing: cosine similarity used as a proxy for "is there something here." It did
not, and could not, measure whether standards documents are categorically
unsuited to noticing things. DR-029 had already read DR-008 this way — it
narrowed the prohibition to "retrieval-as-trigger over bulk text" and allowed a
second trigger path on the reasoning that "DR-008's failure mode — a
nearest-neighbour chunk always exists in a large generic corpus — does not apply
to evaluating an utterance against a small, fixed set of discrete propositions."
This entry extends the same reading one step further, to a reasoning gate over a
unified corpus.

(b) is the part that makes this urgent rather than tidy. The product's pitch is
that Jester notices what a room is about to get wrong. The highest-value form of
that is not "the board resolved the opposite in March" alone — DR-008 correctly
ranks that above commodity legislation — it is the case where an internal
instrument and an external obligation disagree and the room is walking into the
gap. That finding is a join. A partition that puts the two halves of a join on
opposite sides of a trigger boundary cannot produce it.

**THIS IS AN ARGUMENT, NOT A MEASUREMENT — recorded honestly.** DR-008's false
positives were **measured**: 4 of 6 records flipped. This swap's adequacy is
**not measured**. A reasoning gate and a rate ceiling are asserted to be
sufficient replacements for a structural partition, on reasoning, with no
evidence. **DR-045's scored run is the first evidence either way.** A reader who
concludes that this entry trades a control that was measured for two that are
not has read it correctly; the counter-argument is only that the measured
control forbids the product, and that is not itself evidence that the
replacement works.

**HONESTY NOTE ON (d) — THE LICENCE FLAG DOES NOT EXIST IN THE STORE TODAY.**
Verified against `c2_reason/src/c2_reason/ingest/run.py`, the metadata written on
every chunk at ingest is exactly: `source_path`, `tier`, `tier_evidence`,
`chunk_index`, `embedding_model`, `embedding_model_digest`. **There is no licence
field and no authority field.** (d) therefore describes the required end state,
not the built state. What is built in this thread is authority weight **DERIVED
FROM `tier` AT READ TIME** (tier1 → binding; tier2a/tier2b → advisory;
unassigned → unlabelled), which is honest because tier is a provenance
judgement per DR-031 and authority is what provenance was always standing in
for. A real per-chunk licence flag requires a **re-ingest** and is carried to
`BACKLOG.md`. On this box the exposure is currently nil by accident rather than
by design — DR-034 tiered zero documents into 2a/2b, so there is no standards
text in the store to leak — and that is a fact about this corpus, not a control.

**On (g), stated plainly:** removing the partition as a trigger control removes
the skew's power to block C3. It does not make the 41 UNASSIGNED documents
labelled. They remain unlabelled for exactly the properties (d) needs, which is
why re-tiering is demoted rather than closed.

## Alternatives considered & rejected

- **Option A (keep the partition as filed)** — rejected because of (b). It is the
  more evidentially conservative choice and this entry does not pretend
  otherwise. What it cannot do is produce the cross-document finding the product
  exists to produce. Reopened by the review trigger below.
- **Option B (keep the partition, re-tier to fix the ratio)** — rejected because it
  addresses a symptom. Even with a perfectly tiered corpus, a Tier-1-instrument
  vs Tier-2-obligation conflict remains structurally unreachable. It is also the
  more expensive option: re-tiering 46 documents by hand buys a ratio, not a
  capability.
- **Reusing `question_answering` for the trigger path** — rejected as a preference
  under (f), not as a necessity. It would work; it would blind DR-045's scoring
  to the distinction between answering and volunteering.
- **Deleting DR-035's gating test** — rejected. A removed assertion leaves no
  record that the rule changed. The test is rewritten to assert the new rule in
  both directions: `conflict_check` is accepted, and an unknown intent still
  fails loudly.

## Consequences / follow-ups

- `retrieval.py` gains `INTENT_CONFLICT_CHECK` and a unified-corpus path that
  queries all four collections and keeps results per-path (so authority
  labelling survives) while placing no tier-based restriction on which may
  contribute a candidate. The `question_answering` path is unchanged.
- DR-035's `test_unassigned_path_is_gated_on_question_answering_intent` is
  rewritten, not deleted.
- The reasoning gate at (e)(i) is C2's `conflict_check` prompt, built in this
  thread's Task 5. Its known failure mode is over-agreeable invention and it is
  prompted to prefer no-conflict for that reason.
- **Per-chunk licence flag and authority field require a re-ingest** —
  `BACKLOG.md`.
- Re-tiering demoted from C3 blocker to ordinary backlog work, retaining its
  licence/authority-labelling value — `BACKLOG.md`.
- DR-029's Tier 2b criteria path is untouched by this entry. It remains a
  separate, non-retrieval trigger path and is not built here.

## Review trigger (revisit this decision if…)

**THE NAMED CONDITION THAT REOPENS THIS: a scored run in which flags are
dominated by spurious cross-document "conflicts" of the kind DR-008 measured.**
Concretely — candidates whose "conflict" is a lexical or topical adjacency
between two documents with no actual logical incompatibility, scored "should
have spoken: no" at a rate comparable to DR-008's 4-of-6. **If that happens,
this ruling is wrong and DR-008's instinct was right**, and the partition
returns as a trigger control rather than being patched with a stricter
threshold.

Also reopen if:

- The reasoning gate proves to be the over-agreeable failure it is prompted
  against — i.e. it almost never returns no-conflict — since (e)'s relocation
  then rests on a control that does not exist and only DR-042's ceiling is
  holding, which silence satisfies trivially.
- A licence-restricted chunk reaches spoken output. That is a DR-009 breach and
  (d) becomes urgent rather than backlog.
