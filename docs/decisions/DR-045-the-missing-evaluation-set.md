# DR-045 — The missing evaluation set

- **Status:** Accepted
- **Date:** 2026-09-10
- **Thread:** 1.0.16
- **Supersedes / Superseded by:** —

## Context

This entry records a gap as a first-class finding rather than as a caveat
attached to other entries, because it has now silently shaped four threads of
decisions and is the reason three of this thread's own rulings had to be
asserted instead of derived.

**THIS PROJECT HAS NO LABELLED EVALUATION DATA.** Not one example of the form:
*utterance in a room, given this corpus — should Jester have spoken, and was what
it said worth hearing?*

What exists is not that, and the difference matters:

- DR-034's ingest run verified retrieval against 5 representative queries and
  recorded explicitly that this "is a searchability sanity check, not a quality
  evaluation; no fire-rate or precision figure is claimed."
- DR-038's Bar B run measured latency end to end. Latency is not quality.
- DR-008's 4-of-6 figure is the closest thing to an evaluation this project has,
  and it is **borrowed from 2.x**, measured against a different corpus, a
  different task (record classification), and a different mechanism.

## Options considered

Axes: whether the gap gets recorded where future readers will hit it; whether
recording it produces data or only an acknowledgement.

- **Option A — note the gap in `BACKLOG.md` and move on.** Cheapest. It has
  effectively been the standing position since DR-029 and the result is that the
  gap keeps being rediscovered and re-deferred.
- **Option B — build a synthetic evaluation set now.** Write utterances and label
  them by hand against the DHI corpus. Produces data without a spoken run, but
  the labels would be written by the same reasoning that wrote the gate, which is
  the classic way to build an evaluation that confirms whatever it was built
  beside.
- **Option C — file the gap as a DR and make the first real run produce the data
  (CHOSEN).** Records the finding as load-bearing, and rules that the scored
  spoken run is captured as reusable data rather than read once.

## Decision

**The gap is recorded as a first-class finding:** this project has no labelled
evaluation data, and that absence is the root cause of a pattern that has been
visible for four threads:

- **It is why the fire-rate bar has been deferred since DR-029.** DR-029 named the
  relocated noise control precisely — "criteria SPECIFICITY and COUNT" — said it
  was testable by "a fire-rate measurement of the criteria set against a
  transcript corpus," and then fixed no bar, correctly citing §7's
  bar-before-experiment rule. The bar could not be fixed because there was
  nothing to fix it against.
- **It is why DR-042's constants had to be asserted rather than derived.**
  Two-per-ten-minutes is a judgement about failure asymmetry. Nothing available
  would have produced a number.
- **It is why DR-043 can only be settled by measurement.** DR-043 removes a
  measured control and replaces it with an argued one, and says so. The argument
  cannot be resolved by more argument.

**Recorded plainly: no comparison — partitioned vs unified, model size, gate
design — is decidable without it.** Every such comparison on this project today
would be settled by whoever argues most persuasively, which is not a method.

**RULING: the scored spoken run at this thread's Task 7 is the FIRST EVALUATION
SET, and must be captured as REUSABLE DATA, not just read once and discarded.**

Concretely, that means: every candidate's full lifecycle is logged structurally
(raised, queued, merged, spoken, suppressed-by-budget, expired) with the
utterance, the retrieved source and timestamps; a replay CLI lets the operator
mark each candidate for *should have spoken* and, where spoken, *was it worth
hearing*; and the marks are written to a durable scored file under the run
directory. That file is the evaluation set.

## Rationale

The distinguishing property of a labelled set is that it can **disagree with the
person holding it**. A sanity check cannot — DR-034's five queries returned
relevant chunks and would have returned relevant chunks under almost any
configuration, which is why DR-034 was right to claim nothing from them.

Option C is chosen over Option B because of who writes the labels and when. A
synthetic set written this thread would be authored by the same reasoning that
authored DR-043's gate, and would confirm it. A run scored by the operator after
hearing what Jester actually said in a real room is authored by someone who
experienced the failure mode directly, and the labels are attached to utterances
nobody chose in advance.

The cost of Option C is honestly small and worth naming: one run's candidates is
a **tiny** set, drawn from a single meeting on a single corpus, scored by a
single person. It will not support a precision figure with any confidence
interval worth quoting. What it will support is the first evidence that exists at
all, and — because it is captured as data rather than as an impression — the
first thing a second run can be compared against.

**This entry sets no pass bar.** Per §7 a bar is fixed before the experiment, and
this thread has no basis on which to fix one; DR-042's review trigger and
DR-043's review trigger are the qualitative conditions this run is read against.
Setting a numeric precision bar is the open `BACKLOG.md` item DR-042 already
carries, and it should be fixed **before the second scored run**, using the first
run to establish what the achievable range even is.

## Alternatives considered & rejected

- **Option A (backlog note only)** — rejected as the status quo that produced the
  problem. The gap has been carried informally since DR-029 and its consequences
  were absorbed one at a time instead of being read together.
- **Option B (synthetic set now)** — rejected on authorship: labels written beside
  the gate confirm the gate. "Rejected for now" rather than outright — a
  synthetic set built by someone who did NOT write the gate, or built from real
  meeting transcripts after the fact, is a reasonable later step and would scale
  past what a single run can give.

## Consequences / follow-ups

- Task 6 of this thread builds the structured candidate logging and the replay
  scoring CLI. The scored file lands under the run directory.
- The scored file is the artefact DR-043's review trigger is evaluated against.
  Without it, DR-043 cannot be confirmed or refuted and would stand unexamined.
- **`logs/` is gitignored**, so the scored file is machine-local by default. Any
  decision to retain evaluation data across machines must be read against DR-030's
  isolation posture, since the file contains verbatim meeting utterances. Flagged,
  not resolved here — this is the same governance tension DR-041 raised for
  option (d), and it is the operator's call.
- The precision bar remains open in `BACKLOG.md` and should be fixed before the
  SECOND scored run, not the first.

## Review trigger (revisit this decision if…)

- **The first scored run yields too few candidates to read anything from** — likely
  if the reasoning gate is conservative and DR-042's ceiling binds. The response
  is a longer run or a deliberately conflict-rich agenda, not a looser gate,
  because loosening the gate to generate evaluation data would corrupt the
  evaluation.
- **Scoring proves unreliable** — the operator cannot consistently answer "should
  have spoken" for a given candidate. That would mean the question is
  underspecified and needs sharpening before more runs are scored against it.
- **A real labelled corpus becomes available** from another source, at which point
  a single run's marks stop being the best evidence available and this entry's
  ruling is superseded rather than extended.
