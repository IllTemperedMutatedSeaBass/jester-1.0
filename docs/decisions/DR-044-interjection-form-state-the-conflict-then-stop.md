# DR-044 — Interjection form: state the conflict, then stop

- **Status:** Accepted
- **Date:** 2026-09-10
- **Thread:** 1.0.16
- **Supersedes / Superseded by:** —

## Context

DR-043 removes the tier partition as a trigger control and relocates the noise
control to a reasoning gate plus DR-042's ceiling. DR-042 fixes how OFTEN Jester
may speak and rules that outstanding points are batched into one utterance.
Neither says what an interjection CONTAINS.

That is not a cosmetic gap. The content of an interjection determines where
confabulation risk sits, whether the output is checkable, and how annoying the
product is to sit next to — and it determines what the merge step in Task 5(d)
actually renders.

Frozen constraints in play: DR-042 (one utterance from N candidates), DR-043(d)
(every flag must name what it conflicts with and the authority weight of that
source), DR-009 (licence-restricted text must not be reproduced in spoken
output), DR-017 (8 s kill switch).

## Options considered

Axes: checkability of the output; where confabulation risk concentrates; cost in
tokens and latency; tolerability in a room.

- **Option A — state the conflict and stop (CHOSEN).** Name what was said, what it
  conflicts with, and the authority of that source. No resolution offered.
- **Option B — state the conflict and propose a resolution.** More immediately
  useful when right. Requires the model to generate a recommendation that has no
  source in the corpus, which is precisely where an instruction-tuned model
  invents.
- **Option C — state the conflict and offer to elaborate.** A middle path. Rejected
  as a distinct option because the offer is redundant: a human who wants more can
  simply ask, and the offer itself consumes part of a budgeted utterance.

## Decision

**When Jester interjects it STATES THE CONFLICT AND STOPS.** It names what was
said, what it conflicts with, and the authority of that source. It does **NOT**
propose a resolution.

A resolution may be given only if a human then **ASKS** — which is the existing
question-answering path (`intent="question_answering"`, DR-035) and **requires no
new mechanism**.

## Rationale

**Stating a conflict requires a citation and is checkable.** The claim "the plan
just described conflicts with the delegated-authority matrix, which is binding
company policy" has a referent in the corpus; a human can check it in seconds and
Jester is straightforwardly right or wrong. That is a good property for a
component whose entire credibility rests on being worth listening to.

**Proposing a fix invites the model to invent one, and confabulation risk
concentrates there.** The conflict is retrieved; the resolution is not. Asking a
model to recommend what a board should do about a governance conflict is asking
it to generate content with no source, on a topic where a confident wrong answer
is expensive. DR-043(e) already relocates the project's noise control onto a
reasoning gate whose named failure mode is over-agreeable invention — extending
that same model's remit to recommendations compounds the exposure rather than
containing it.

**This is also the cheaper and more honest half, and the harder half to annoy
with.** Cheaper: a stated conflict is short, which matters directly against
DR-017's 8 s kill switch and against DR-036's context arithmetic. More honest: it
claims exactly what the system can support and no more. Harder to annoy with: an
observation invites a response, a recommendation demands one, and a component
that recommends twice in ten minutes is a participant in the meeting rather than
an instrument in it.

The asymmetry that settles it: when Jester is right, the resolution is usually
obvious to the humans anyway; when Jester is wrong, a proposed resolution turns a
recoverable false positive into an argument.

## Alternatives considered & rejected

- **Option B (propose a resolution)** — rejected on confabulation concentration.
  Reopened if the reasoning gate turns out to be reliably calibrated AND the
  operator judges bare conflict statements insufficiently actionable in a real
  meeting — but the first condition must hold before the second is even asked.
- **Option C (offer to elaborate)** — rejected as redundant. The
  question-answering path already exists and a human can use it unprompted; the
  offer spends budget to advertise a capability the room already has.

## Consequences / follow-ups

- The merge step (DR-042(b), Task 5(d)) renders N structured candidates as N
  conflict statements in one utterance, each naming the source and its authority
  weight. It never renders a recommendation.
- Candidates are therefore **structured records**, not prose — they carry
  `utterance`, `conflicts_with`, `source` and `authority` as separate fields, so
  the merge step composes a sentence rather than concatenating model output.
- **BUILD CONSEQUENCE — the C4 text filter.** `c4_speech/text_filter.py` strips
  emoji, asterisked stage directions, parenthetical narration and Gemma control
  markers, but **does NOT strip bracketed citations**. This was flagged as a risk
  in thread 1.0.14 and recorded in DR-038 as an open `BACKLOG.md` item: that run
  happened to emit no `[source #N]` markers, which DR-038 called "one clean run,
  not a fix." **This ruling makes cited flags routine rather than rare** —
  `retrieval.format_evidence` renders every chunk as `[<source_path> #<index>]`
  and DR-044 requires the source to be named aloud. **The filter is fixed in this
  session** (Task 3), not deferred.
- The two halves must be read together: the bracket marker is stripped from
  spoken text, AND the source reaches speech as **prose** via the candidate's
  `source`/`authority` fields. Stripping brackets without the structured fields
  would remove the citation this entry exists to require. That coupling is the
  reason the filter fix and the candidate structure land in the same thread.

## Review trigger (revisit this decision if…)

- **A scored run shows conflict statements scoring "worth hearing: no" primarily
  because they are unactionable** — as distinct from wrong. That is the specific
  evidence that would favour Option B, and it must be distinguishable in the
  scoring from "wrong", or the reopening is unsupported.
- **The question-answering follow-up path is never used after an interjection.**
  If humans never ask, the assumption that asking is the natural next move is
  wrong, and the resolution has to arrive some other way.
- **A licence-restricted source is named aloud** — DR-009 breach; the naming rule
  in DR-043(d) needs a licence check in front of it before it renders.
