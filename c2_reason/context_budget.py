"""TASK 3 (thread 1.0.14) -- what retrieval actually costs against DR-013's
num_ctx 8192, measured rather than asserted.

DR-013(b) left transcript truncation UNDECIDED and called it a design
question, not a tuning detail. This script does NOT decide it. It produces
the evidence a decision needs:

  1. How many tokens a typical retrieval adds, measured against the live
     store with realistic board-meeting questions (not filler).
  2. How close a realistic session comes to the 8192 limit, using the REAL
     transcript-growth rate measured from this repo's own prior 20-turn
     spoken run (logs/run_*/c2.jsonl `prompt_eval_count`), not a guess.
  3. What the failure looks like when it overflows -- traced through the
     actual call path, not inferred.

Run with the repo .env sourced. Read-only against the store.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from c2_reason.config import Config  # noqa: E402
from c2_reason.prompt import (  # noqa: E402
    STABLE_PREAMBLE,
    PromptBuilder,
    estimate_tokens,
)
from c2_reason.retrieval import (  # noqa: E402
    ChromaRetriever,
    RetrievalRequest,
    format_evidence,
    MODE_MEETING_SPOKEN,
)

# Realistic board-meeting questions against the actual DHI corpus. Chosen
# to span both populated collections (tier1 and unassigned) rather than to
# flatter the figure -- a question that retrieves nothing costs nothing and
# would understate the budget.
QUESTIONS = [
    "What did the board resolve about the ERP upgrade programme?",
    "Who holds delegated authority for capital spend?",
    "What is the entity structure of the DHI Group?",
    "What does the AI management system process map cover?",
    "Which risks are open on the risk register?",
    "What came out of the AI planning workshop?",
    "What is the status of the PMO programme this quarter?",
    "What AI awareness training has been delivered to staff?",
    "What were the lessons learned from the last programme?",
    "What are the commercial objectives for this year?",
]


def measure_evidence_tokens(config: Config, top_k: int) -> dict:
    retriever = ChromaRetriever(
        persist_dir=config.CHROMA_PERSIST_DIR,
        ollama_base_url=config.OLLAMA_BASE_URL,
        embed_model=config.EMBED_MODEL,
        embed_model_digest=config.EMBED_MODEL_DIGEST,
        corpus_id=config.CORPUS_ID,
    )
    per_question = []
    for question in QUESTIONS:
        result = retriever.retrieve(
            RetrievalRequest(
                corpus_id=config.CORPUS_ID,
                mode=MODE_MEETING_SPOKEN,
                query=question,
                top_k=top_k,
            )
        )
        evidence = format_evidence(result)
        per_question.append(
            {
                "question": question,
                "chunks": result.total_chunks,
                "by_path": result.counts(),
                "evidence_chars": len(evidence),
                "evidence_tokens_est": estimate_tokens(evidence),
                "embed_s": round(result.embed_s, 4),
                "query_s": round(result.query_s, 4),
            }
        )
    token_values = [q["evidence_tokens_est"] for q in per_question]
    return {
        "top_k": top_k,
        "per_question": per_question,
        "evidence_tokens_median": statistics.median(token_values),
        "evidence_tokens_max": max(token_values),
        "evidence_tokens_min": min(token_values),
        "embed_s_median": statistics.median(q["embed_s"] for q in per_question),
        "query_s_median": statistics.median(q["query_s"] for q in per_question),
    }


def measured_transcript_growth() -> dict:
    """Transcript growth per turn, taken from this repo's own prior spoken
    runs rather than assumed. `prompt_eval_count` in those logs is the FULL
    prompt token count (it grows monotonically turn over turn), so the
    per-turn increment is the transcript growth rate."""
    repo_root = Path(__file__).resolve().parents[1]
    runs = {}
    for log_dir in sorted((repo_root / "logs").glob("run_*")) + [
        repo_root / "logs_1.0.10_backup"
    ]:
        c2_log = log_dir / "c2.jsonl"
        if not c2_log.exists():
            continue
        counts = []
        for line in c2_log.read_text().splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") == "prefill_done" and record.get("prompt_eval_count"):
                counts.append(record["prompt_eval_count"])
        if len(counts) < 2:
            continue
        deltas = [b - a for a, b in zip(counts, counts[1:])]
        runs[log_dir.name] = {
            "turns": len(counts),
            "first_prompt_tokens": counts[0],
            "last_prompt_tokens": counts[-1],
            "tokens_per_turn_median": statistics.median(deltas),
            "tokens_per_turn_max": max(deltas),
        }
    return runs


def budget(evidence_tokens: int, tokens_per_turn: float, first_prompt: int) -> dict:
    """Turns until the prompt reaches num_ctx.

    THE KEY STRUCTURAL POINT, and it is not the one this task's framing
    anticipated: retrieved evidence is rebuilt fresh every turn and is NOT
    accumulated into the transcript (see prompt.PromptBuilder and
    tests/test_prompt_ordering.py::test_evidence_is_never_accumulated...).
    So retrieval adds a roughly CONSTANT offset to the prompt, not a
    growing one. It brings the overflow point closer by a fixed amount; it
    does not make the transcript grow faster.
    """
    headroom = Config.NUM_CTX - evidence_tokens - first_prompt
    return {
        "num_ctx": Config.NUM_CTX,
        "evidence_tokens_per_turn": evidence_tokens,
        "transcript_tokens_per_turn": tokens_per_turn,
        "turns_to_overflow": int(headroom / tokens_per_turn) if tokens_per_turn else None,
        "turns_to_overflow_without_retrieval": int(
            (Config.NUM_CTX - first_prompt) / tokens_per_turn
        )
        if tokens_per_turn
        else None,
    }


# Conversational speech runs ~130-160 words/minute; at this repo's own
# chars/4 estimator that is ~170-210 tokens of transcript per minute of
# meeting. 190 is the midpoint and is the figure used below. This is a
# STATED ASSUMPTION, not a measurement -- the Bar B calibration turns are
# short prompted utterances (9-14 tokens/turn measured above) and are NOT
# representative of continuous meeting speech, so projecting a real
# meeting from them would understate the pressure by an order of
# magnitude. Flagged as the one un-measured input in this report.
_MEETING_TOKENS_PER_MINUTE = 190


def real_meeting_projection(evidence_median: int, evidence_max: int) -> dict:
    """DR-013(b) says 'a real meeting overflows it in 30-45 minutes'. This
    puts a number on what retrieval does to that window."""
    def minutes(evidence_tokens: int) -> float:
        headroom = Config.NUM_CTX - evidence_tokens - estimate_tokens(STABLE_PREAMBLE)
        return round(headroom / _MEETING_TOKENS_PER_MINUTE, 1)

    without = minutes(0)
    return {
        "assumption_tokens_per_minute": _MEETING_TOKENS_PER_MINUTE,
        "assumption_is_measured": False,
        "minutes_to_overflow_without_retrieval": without,
        "minutes_to_overflow_at_median_evidence": minutes(evidence_median),
        "minutes_to_overflow_at_max_evidence": minutes(evidence_max),
        "minutes_lost_to_retrieval_at_median": round(
            without - minutes(evidence_median), 1
        ),
        "dr013b_stated_window_minutes": "30-45",
    }


def main() -> None:
    top_k = int(sys.argv[1]) if len(sys.argv) > 1 else Config.RETRIEVAL_TOP_K
    Config.require_retrieval_settings()

    evidence = measure_evidence_tokens(Config, top_k)
    growth = measured_transcript_growth()

    rates = [r["tokens_per_turn_median"] for r in growth.values()]
    median_rate = statistics.median(rates) if rates else 16.0

    report = {
        "evidence": evidence,
        "measured_transcript_growth": growth,
        "budget_at_median_evidence": budget(
            int(evidence["evidence_tokens_median"]), median_rate, 116
        ),
        "budget_at_max_evidence": budget(
            int(evidence["evidence_tokens_max"]), median_rate, 116
        ),
        "real_meeting_projection": real_meeting_projection(
            int(evidence["evidence_tokens_median"]),
            int(evidence["evidence_tokens_max"]),
        ),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
