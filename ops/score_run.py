"""Replay a run's interjection candidates and score them (DR-045).

THIS SCRIPT PRODUCES THE PROJECT'S FIRST EVALUATION SET. DR-045 records the
finding it exists to fix: this project has no labelled evaluation data --
not one example of "utterance in a room, given this corpus: should Jester
have spoken, and was what it said worth hearing?" -- and that absence is
why the fire-rate bar has been deferred since DR-029, why DR-042's
constants had to be asserted rather than derived, and why DR-043 can only
be settled by measurement.

DR-045 rules that the scored spoken run is captured as REUSABLE DATA, not
read once and discarded. That is this file: it reads C3's structured
candidate-lifecycle events out of a run directory, asks the operator two
questions per candidate, and writes a durable JSON file back into the run
directory.

TWO QUESTIONS, AND WHY BOTH:
  1. SHOULD HAVE SPOKEN (yes/no) -- asked about EVERY candidate, including
     ones that were never spoken. A candidate suppressed by budget or
     expired is evidence about DR-042's constants, and it is only evidence
     if it is scored.
  2. WORTH HEARING (yes/no) -- asked ONLY where Jester actually spoke,
     because it is a judgement about the utterance that was produced, and
     there is no utterance for a candidate that never surfaced.

DR-044's review trigger needs one more distinction, so where an operator
answers "not worth hearing" they are offered a REASON: `wrong` or
`unactionable`. DR-044 says explicitly that a reopening in favour of
proposing resolutions is unsupported unless "unactionable" is
distinguishable from "wrong" in the scoring. Optional -- pressing enter
skips it.

WHAT THIS DOES NOT DO. It computes no precision figure and asserts no pass
bar. Per WAYS_OF_WORKING §7 a bar is fixed BEFORE an experiment, and DR-045
sets none for the first run, on the reasoning that the first run is what
establishes the achievable range. It prints counts. Counts are not a bar.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# C3's candidate-lifecycle events, per DR-045's ruling that every stage is
# logged: raised, queued, merged, spoken, suppressed-by-budget, expired.
TERMINAL_EVENTS = {
    "interjection_spoken": "spoken",
    "candidate_suppressed_by_budget": "suppressed_by_budget",
    "candidate_expired": "expired",
    "candidate_dropped_queue_full": "dropped_queue_full",
}


def _load_events(run_dir: Path) -> list[dict]:
    events = []
    for name in ("c3.jsonl", "c5.jsonl", "c2.jsonl"):
        path = run_dir / name
        if not path.exists():
            continue
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    events.sort(key=lambda e: e.get("monotonic_ts", 0.0))
    return events


def collect_candidates(events: list[dict]) -> list[dict]:
    """Reconstruct each candidate's lifecycle from the event stream.

    Keyed on `candidate_id`, which C3 mints when the candidate is raised,
    so a candidate is followed across turns -- a candidate raised on turn 3
    and spoken on turn 7 is ONE row, not two. That is the whole point of a
    reusable evaluation set rather than a per-turn log read.
    """
    candidates: dict[str, dict] = {}

    for event in events:
        name = event.get("event")
        if name == "candidate_raised":
            cid = event.get("candidate_id")
            if not cid:
                continue
            candidates[cid] = {
                "candidate_id": cid,
                "raised_turn_id": event.get("turn_id"),
                "raised_wall_ts": event.get("wall_ts"),
                "raised_monotonic_ts": event.get("monotonic_ts"),
                "utterance": event.get("utterance"),
                "conflicts_with": event.get("conflicts_with"),
                "source": event.get("source"),
                "authority": event.get("authority"),
                "retrieved_chunks": event.get("retrieved_chunks"),
                "unified_corpus": event.get("unified_corpus"),
                "outcome": "queued",
                "spoken_text": None,
                "spoken_with": [],
                "batched": False,
                "outcome_wall_ts": None,
                # A candidate can be suppressed by budget on one
                # opportunity and then EXPIRE before the next, in which
                # case its terminal outcome is "expired" and the budget
                # suppression would vanish from the row. DR-045 needs
                # suppressed-by-budget visible because it is the evidence
                # about DR-042's constants, so it is counted separately
                # rather than overwritten by whatever happened last.
                "suppressed_by_budget_count": 0,
            }
        elif name == "interjection_spoken":
            spoken = event.get("candidates", []) or []
            ids = [c.get("candidate_id") for c in spoken]
            for entry in spoken:
                cid = entry.get("candidate_id")
                if cid not in candidates:
                    continue
                candidates[cid].update(
                    outcome="spoken",
                    spoken_text=event.get("text"),
                    spoken_with=[i for i in ids if i and i != cid],
                    batched=len(ids) > 1,
                    outcome_wall_ts=event.get("wall_ts"),
                    opportunity=event.get("opportunity"),
                )
        elif name in TERMINAL_EVENTS:
            cid = event.get("candidate_id")
            if cid in candidates and candidates[cid]["outcome"] != "spoken":
                if name == "candidate_suppressed_by_budget":
                    candidates[cid]["suppressed_by_budget_count"] += 1
                candidates[cid]["outcome"] = TERMINAL_EVENTS[name]
                candidates[cid]["outcome_wall_ts"] = event.get("wall_ts")

    return sorted(candidates.values(), key=lambda c: c.get("raised_monotonic_ts") or 0.0)


def _run_stats(events: list[dict]) -> dict:
    """Context the scores are meaningless without. A precision figure over
    4 candidates from 20 turns means something different from the same
    figure over 40 -- and the denominator is the thing a later reader will
    most want and least likely be able to reconstruct."""
    counts: dict[str, int] = {}
    for event in events:
        name = event.get("event", "")
        if name in {
            "conflict_check_requested", "no_conflict", "candidate_raised",
            "opportunity_declined", "interjection_spoken",
            "candidate_expired", "candidate_suppressed_by_budget",
            "conflict_check_failed", "turn_done",
        }:
            counts[name] = counts.get(name, 0) + 1
    return counts


class _ScoringInterrupted(Exception):
    """Operator ended the scoring pass early (Ctrl-D / Ctrl-C)."""


def _ask(prompt: str, options: dict[str, str], allow_skip: bool = False) -> str | None:
    keys = "/".join(options)
    suffix = " (enter to skip)" if allow_skip else ""
    while True:
        try:
            raw = input(f"{prompt} [{keys}]{suffix}: ").strip().lower()
        except EOFError:
            # Ctrl-D, or a closed terminal. Raised so the caller can write
            # what has been scored SO FAR: the spoken run is one-shot, and
            # losing a half-finished scoring pass means re-listening to a
            # meeting that cannot be replayed.
            raise _ScoringInterrupted from None
        if not raw and allow_skip:
            return None
        if raw in options:
            return options[raw]
        print(f"  please answer one of: {', '.join(options)}")


def score(candidates: list[dict]) -> tuple[list[dict], bool]:
    """Returns (candidates, completed). On an early exit the candidates
    scored so far keep their marks and the rest are left unscored -- a
    partial evaluation set is worth strictly more than none, and the file
    records which it is."""
    print(f"\n{len(candidates)} candidate(s) to score."
          f"  (Ctrl-D to stop early; what you have scored is kept.)\n" + "=" * 66)
    for i, candidate in enumerate(candidates, 1):
      try:
        print(f"\n[{i}/{len(candidates)}]  outcome: {candidate['outcome'].upper()}")
        print(f"  utterance      : {candidate.get('utterance')}")
        print(f"  conflicts with : {candidate.get('conflicts_with')}")
        print(f"  source         : {candidate.get('source')} "
              f"({candidate.get('authority')})")
        if candidate.get("suppressed_by_budget_count"):
            print(f"  NOTE           : refused by the DR-042 budget on "
                  f"{candidate['suppressed_by_budget_count']} opportunity(ies) "
                  f"before this outcome")
        if candidate["outcome"] == "spoken":
            if candidate["batched"]:
                print(f"  BATCHED with {len(candidate['spoken_with'])} other(s) "
                      f"into one interjection")
            print(f"  SPOKEN AS      : {candidate.get('spoken_text')}")

        candidate["should_have_spoken"] = _ask(
            "  Should Jester have spoken?", {"y": "yes", "n": "no"}
        )

        if candidate["outcome"] == "spoken":
            candidate["worth_hearing"] = _ask(
                "  Was what it said worth hearing?", {"y": "yes", "n": "no"}
            )
            if candidate["worth_hearing"] == "no":
                # DR-044's review trigger depends on this distinction.
                candidate["not_worth_hearing_reason"] = _ask(
                    "    Because it was", {"w": "wrong", "u": "unactionable"},
                    allow_skip=True,
                )
        else:
            # No utterance exists, so the question is not askable.
            candidate["worth_hearing"] = None
      except _ScoringInterrupted:
        print(f"\n\nStopped early at candidate {i} of {len(candidates)}. "
              f"Keeping the {i - 1} already scored.")
        return candidates, False
    return candidates, True


def summarise(candidates: list[dict], stats: dict) -> dict:
    spoken = [c for c in candidates if c["outcome"] == "spoken"]
    return {
        "candidates_total": len(candidates),
        "candidates_spoken": len(spoken),
        "candidates_suppressed_by_budget": sum(
            1 for c in candidates if c["outcome"] == "suppressed_by_budget"),
        "candidates_expired": sum(1 for c in candidates if c["outcome"] == "expired"),
        # Counts candidates the ceiling refused AT LEAST ONCE, whatever
        # became of them afterwards -- a candidate refused and then expired
        # is evidence about DR-042's constants either way.
        "candidates_refused_by_budget_at_least_once": sum(
            1 for c in candidates if c.get("suppressed_by_budget_count")),
        "should_have_spoken_yes": sum(
            1 for c in candidates if c.get("should_have_spoken") == "yes"),
        "should_have_spoken_no": sum(
            1 for c in candidates if c.get("should_have_spoken") == "no"),
        "worth_hearing_yes": sum(1 for c in spoken if c.get("worth_hearing") == "yes"),
        "worth_hearing_no": sum(1 for c in spoken if c.get("worth_hearing") == "no"),
        "not_worth_hearing_wrong": sum(
            1 for c in spoken if c.get("not_worth_hearing_reason") == "wrong"),
        "not_worth_hearing_unactionable": sum(
            1 for c in spoken if c.get("not_worth_hearing_reason") == "unactionable"),
        "run_event_counts": stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "run_dir", nargs="?", default=str(REPO / "logs" / "latest"),
        help="run directory containing c3.jsonl (default: logs/latest)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="list candidates and exit without scoring",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        print(f"No such run directory: {run_dir}", file=sys.stderr)
        return 1

    events = _load_events(run_dir)
    if not events:
        print(f"No structured events found in {run_dir}.", file=sys.stderr)
        return 1

    candidates = collect_candidates(events)
    stats = _run_stats(events)

    print(f"Run: {run_dir}")
    print(f"Events: {len(events)}   Candidates: {len(candidates)}")
    for key in sorted(stats):
        print(f"  {key}: {stats[key]}")

    if not candidates:
        # Explicitly NOT an error. DR-045's review trigger names exactly
        # this: a run yielding too few candidates to read anything from,
        # whose response is a longer run or a conflict-rich agenda -- NOT a
        # looser gate, because loosening the gate to generate evaluation
        # data would corrupt the evaluation.
        print("\nNo candidates were raised in this run. Nothing to score.")
        print("DR-045's review trigger covers this case: the response is a "
              "longer run or a\ndeliberately conflict-rich agenda -- NOT a "
              "looser gate.")
        return 0

    if args.list:
        for candidate in candidates:
            print(json.dumps(candidate, indent=2))
        return 0

    scored, completed = score(candidates)
    summary = summarise(scored, stats)
    summary["scoring_completed"] = completed
    summary["candidates_scored"] = sum(
        1 for c in scored if c.get("should_have_spoken") is not None)

    out = {
        "schema": "jester-1.0/evaluation-set/v1",
        "filed_under": "DR-045",
        "run_dir": str(run_dir),
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "First evaluation set for this project (DR-045). One meeting, "
            "one corpus, one scorer -- too small to support a precision "
            "figure with a confidence interval worth quoting. No pass bar "
            "is asserted: per WAYS_OF_WORKING sec.7 a bar is fixed before an "
            "experiment, and DR-045 sets none for the first run."
        ),
        "summary": summary,
        "candidates": scored,
    }

    out_path = run_dir / "scored_candidates.json"
    out_path.write_text(json.dumps(out, indent=2))

    print("\n" + "=" * 66)
    print(json.dumps(summary, indent=2))
    print(f"\nEvaluation set written to {out_path}")
    print("NOTE: logs/ is gitignored, so this file is machine-local. DR-045 "
          "flags the\nretention question against DR-030's isolation posture "
          "-- it contains verbatim\nmeeting utterances. That is the "
          "operator's call, not this script's.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
