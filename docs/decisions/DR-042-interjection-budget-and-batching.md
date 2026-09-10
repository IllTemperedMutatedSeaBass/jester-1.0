# DR-042 — The interjection budget and the batching rule

- **Status:** Accepted
- **Date:** 2026-09-10
- **Thread:** 1.0.16
- **Supersedes / Superseded by:** —

## Context

C3 has never had a rate limit because C3 has never interjected. It is a stub
(`c3_router.main.decide`) that returns `speak_now` unconditionally and is not
started by `ops/run_d0.sh`. This thread builds the real gate, and
`WAYS_OF_WORKING.md` §7 requires the bar to exist before the build.

The constraint that forces a decision is the product thesis itself. DR-008
states it plainly: "this product's value is knowing when to stay SILENT." A
component that may speak on every turn is not a gate. But the inverse failure
is just as real and is much easier to hit by accident — a system that never
speaks satisfies every frequency ceiling perfectly.

Frozen constraints this must respect: DR-006 (etiquette is the PRIMARY latency
mitigation, hand-up-then-speak, not to be optimised away), DR-008 (silence is
the product), DR-017 (kill switch at 8 s end to end).

## Options considered

Axes: whether the rule is enforceable cheaply and deterministically; whether it
survives a burst of genuinely salient material; whether it reads as socially
competent in a room of humans.

- **Option A — per-utterance decision, no memory.** C3 decides on each candidate
  independently. Cheap and stateless. Cannot express "at most twice per ten
  minutes" at all, and a run of related utterances produces a run of
  interjections. Fails the burst axis outright.
- **Option B — rate ceiling only.** A rolling window caps interjections. Enforceable
  and cheap. But with a decide-and-fire-per-utterance design underneath, three
  salient points arriving close together spend two slots on two of them and drop
  the third — the ceiling is satisfied while the behaviour is still wrong.
- **Option C — rate ceiling plus mandatory batching (CHOSEN).** A ceiling bounds
  frequency, and everything outstanding at the moment of speaking is delivered
  together. Requires a pending queue and a merge step, which is a real structural
  cost, and it is the only option that handles a burst the way a person would.

## Decision

**(a) C3 may interject at most TWICE per rolling ten minutes.** A hard ceiling,
enforced in C3, tested.

**(b) BATCHING IS PART OF THE RULE, NOT AN OPTIMISATION.** If more than one
salient point is outstanding when C3 gets its chance to speak, ALL outstanding
points are delivered in ONE interjection. C3 must not spend two budget slots on
points it could have combined. This is an etiquette principle, and it is stated
as a rule rather than left to an implementer's judgement: a person with three
things to say says them once.

**(c) THE CONSTANTS ARE PROVISIONAL.** Two-per-ten-minutes is fixed so that work
can proceed against a bar, per §7. It is expected to be revised once measured.
It is **asserted, not derived** — see the rationale below, and DR-045 for why no
derivation was available.

## Rationale

The ceiling wins on the axes because it is the only part of this that can be
enforced without a model in the loop. A rolling-window counter is arithmetic; it
cannot be talked out of its answer by an over-agreeable generation, which is
exactly the property a backstop needs.

Batching is ruled as part of the rule because of where it lands in the build. A
decide-and-fire-per-utterance component cannot be made to batch later without
being restructured — batching is a property of the data flow, not a filter on
its output. Ruling it now costs a queue; ruling it after C3 exists costs a
rewrite of C3.

**The constants are not derived and this entry does not pretend otherwise.**
There is no measurement on this project that would yield "twice per ten minutes"
rather than once, or five times. The number is a starting position chosen to be
obviously conservative against DR-008's silence-is-the-product thesis, on the
reasoning that an under-speaking system is a recoverable disappointment and an
over-speaking one gets switched off. That is a judgement about failure
asymmetry, not evidence.

**No kill-switch metric is defined for this decision**, because the metric that
would matter is a precision figure and this thread has no authority to set one
(see below).

## Alternatives considered & rejected

- **Option A (stateless per-utterance)** — rejected: cannot express a rolling
  ceiling, and produces runs of interjections on related material.
- **Option B (ceiling without batching)** — rejected: satisfies the letter of the
  frequency rule while still behaving like an interrupter. Reopening it would
  require accepting that two interjections ninety seconds apart are as good as
  one that covers both, which is the opposite of the etiquette DR-006 makes
  load-bearing.
- **A precision or hit-rate bar alongside the ceiling** — NOT REJECTED, and
  deliberately NOT SET HERE. The operator has not ruled on one. It is carried to
  `BACKLOG.md` with its rationale, which is the sharpest available criticism of
  this very entry: **a frequency ceiling alone is satisfied perfectly by a system
  that never speaks.** DR-042 bounds how often Jester may speak and says nothing
  whatsoever about whether what it says is worth hearing. Both halves are needed
  and only one is filed.

## Consequences / follow-ups

**Build consequence, recorded here and built in this thread's Task 5:** batching
requires a **PENDING CANDIDATE QUEUE** and a **merge step producing one utterance
from N candidates**. This is explicitly NOT a decide-and-fire-per-utterance
design. A candidate is raised, queued, and only merged and spoken when an
opportunity arrives.

Follow-ons this commits later work to:

- A candidate that is queued and never gets an opportunity must expire rather
  than surface minutes late — ruled and built in Task 5(f), not here.
- The merge step is where DR-044's "state the conflict, then stop" form is
  actually rendered, so the two entries are coupled: N structured candidates
  become one spoken sentence-set naming each conflict and its authority.
- The precision bar is an open `BACKLOG.md` item blocking any claim that C3
  works, as distinct from claims that C3 is bounded.

## Review trigger (revisit this decision if…)

- **A scored run shows the ceiling binding on material the operator judges worth
  hearing** — i.e. suppressed-by-budget candidates that scored "should have
  spoken: yes". That is the ceiling being too tight, and the constant moves.
- **A scored run shows two-per-ten-minutes is still too talkative** — flags
  scoring "worth hearing: no" at a rate that annoys. The constant moves the
  other way.
- **The queue is observed to be empty at almost every opportunity**, making the
  batching machinery dead weight — that would mean candidates are rare enough
  that the ceiling never binds, and the honest response is to ask whether the
  gate upstream is too conservative rather than to keep the queue.
- **Standing punch-list item:** the missing precision bar. Until it exists, this
  DR cannot be evaluated as correct or incorrect, only as implemented.
