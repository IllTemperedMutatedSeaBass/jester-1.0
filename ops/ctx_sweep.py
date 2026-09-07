"""TASK 3 (thread 1.0.15) -- measure the num_ctx latency-versus-capacity
trade-off non-interactively, before spending the operator's spoken run.

DR-013 set num_ctx 8192 for LATENCY reasons, not capacity ones, and that
choice has never been re-measured. This sweep measures what a larger window
actually costs.

TWO DIFFERENT PREFILL COSTS ARE MEASURED SEPARATELY, because conflating
them would produce a recommendation built on the wrong number:

  COLD prefill -- the whole prompt evaluated from nothing. This is NOT what
    a turn costs in steady state. It IS what is paid once at session start,
    and again on every cut under a chunked-truncation policy (option (b) in
    the context-management design), so it is measured and reported rather
    than discarded.

  DELTA prefill -- a cached prefix plus one new transcript line plus a
    fresh evidence block appended after it (DR-013(a) ordering). This is
    what every steady-state turn actually pays and it is the number the
    num_ctx recommendation rests on. DR-037/DR-038 measured this on live
    runs at 1.634 ms per evidence token with a 0.388 s intercept; this
    sweep extends it across window sizes and fills.

TRUNCATION PROBE. Ollama does NOT error when a prompt exceeds num_ctx: it
silently truncates, keeping ~5 leading tokens plus a tail, and returns HTTP
200 (verified on this box -- server log `msg="truncating input prompt"
limit=4099 prompt=15720 keep=5`). Every call here therefore reads back
Ollama's own `prompt_eval_count` and flags any call whose count is far
below what was sent, so a silently-truncated measurement can never be
reported as a valid one.

Run with the repo .env sourced. Read-only against the corpus store.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "c2_reason" / "src"))

from c2_reason.config import Config  # noqa: E402
from c2_reason.prompt import STABLE_PREAMBLE  # noqa: E402
from c2_reason.retrieval import (  # noqa: E402
    ChromaRetriever,
    RetrievalRequest,
    format_evidence,
    MODE_MEETING_SPOKEN,
)

NUM_CTX_SETTINGS = (8192, 16384, 32768)
FILLS = (0.25, 0.50, 0.75, 0.95)
NUM_PREDICT = 40  # the pinned Bar B cap (DR-024)

_TURN_OPEN = "<start_of_turn>user\n"
_TURN_CLOSE = "<end_of_turn>\n<start_of_turn>model\n"

# Meeting-shaped filler. Varied so it does not compress into a degenerate
# token pattern that would make prefill unrepresentatively cheap.
_LINES = [
    "human: The programme board reviewed the delivery milestones for this quarter.",
    "human: We agreed the vendor contract needs a further legal review before signing.",
    "human: The risk register still shows the integration dependency as amber.",
    "human: Finance raised a concern about the capital profile in the second half.",
    "human: Operations confirmed the migration window is booked for the tenth.",
    "human: There was disagreement about whether the scope change needs board approval.",
    "human: The audit findings from last cycle have three actions still open.",
    "human: We noted the resourcing gap in the data engineering team.",
]


def _client() -> httpx.Client:
    return httpx.Client(timeout=1800.0)


def _generate(client: httpx.Client, prompt: str, num_ctx: int) -> dict:
    started = time.monotonic()
    response = client.post(
        f"{Config.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": Config.OLLAMA_MODEL,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": NUM_PREDICT,
                "stop": ["<end_of_turn>"],
            },
        },
    )
    response.raise_for_status()
    body = response.json()
    return {
        "prompt_eval_count": body.get("prompt_eval_count", 0),
        "prompt_eval_s": body.get("prompt_eval_duration", 0) / 1e9,
        "eval_count": body.get("eval_count", 0),
        "wall_s": time.monotonic() - started,
    }


def calibrate_chars_per_token(client: httpx.Client) -> float:
    """Measured, not assumed: the repo's chars/4 estimator is for English
    prose generally, and this filler's real ratio is what sizes the fills."""
    body = "\n".join(_LINES * 20)
    prompt = _TURN_OPEN + body + _TURN_CLOSE
    result = _generate(client, prompt, 8192)
    ratio = len(prompt) / result["prompt_eval_count"]
    print(f"  calibration: {len(prompt)} chars -> {result['prompt_eval_count']} "
          f"tokens = {ratio:.2f} chars/token", flush=True)
    return ratio


def build_transcript(target_tokens: int, chars_per_token: float, nonce: str) -> str:
    """`nonce` makes each cold prompt unique so it cannot hit the KV cache
    left by the previous call -- without it, 'cold' would silently measure
    a cache hit and every cold figure would be wrong."""
    target_chars = int(target_tokens * chars_per_token)
    out = [f"human: Session reference {nonce}."]
    i = 0
    length = len(out[0])
    while length < target_chars:
        line = _LINES[i % len(_LINES)]
        out.append(f"{line} (point {i})")
        length += len(out[-1]) + 1
        i += 1
    return "\n".join(out)


def get_evidence() -> str:
    Config.require_retrieval_settings()
    retriever = ChromaRetriever(
        persist_dir=Config.CHROMA_PERSIST_DIR,
        ollama_base_url=Config.OLLAMA_BASE_URL,
        embed_model=Config.EMBED_MODEL,
        embed_model_digest=Config.EMBED_MODEL_DIGEST,
        corpus_id=Config.CORPUS_ID,
    )
    result = retriever.retrieve(
        RetrievalRequest(
            corpus_id=Config.CORPUS_ID,
            mode=MODE_MEETING_SPOKEN,
            query="What did the board resolve about the programme and who approved the spend?",
            top_k=Config.RETRIEVAL_TOP_K,
        )
    )
    return format_evidence(result)


def main() -> None:
    evidence = get_evidence()
    rows = []
    with _client() as client:
        print("Calibrating tokenizer ratio...", flush=True)
        chars_per_token = calibrate_chars_per_token(client)
        evidence_tokens = int(len(evidence) / chars_per_token)
        print(f"  evidence block: {len(evidence)} chars ~= {evidence_tokens} tokens\n",
              flush=True)

        for num_ctx in NUM_CTX_SETTINGS:
            for fill in FILLS:
                target_total = int(num_ctx * fill)
                # Size the transcript so transcript + evidence + overhead
                # lands at the requested fill of the window.
                transcript_tokens = max(200, target_total - evidence_tokens - 120)
                nonce = f"{num_ctx}-{fill}-{time.time():.0f}"
                transcript = build_transcript(transcript_tokens, chars_per_token, nonce)

                # --- COLD: whole prompt from nothing -------------------
                cold_body = STABLE_PREAMBLE + transcript + "\n\n[Evidence]\n" + evidence
                cold_prompt = _TURN_OPEN + cold_body + _TURN_CLOSE
                cold = _generate(client, cold_prompt, num_ctx)

                # --- DELTA: same prefix, one new line + fresh evidence
                # appended AFTER the transcript (DR-013(a)) -------------
                delta_body = (
                    STABLE_PREAMBLE + transcript
                    + "\nhuman: And what did we decide about the escalation path?"
                    + "\n\n[Evidence]\n" + evidence
                )
                delta_prompt = _TURN_OPEN + delta_body + _TURN_CLOSE
                delta = _generate(client, delta_prompt, num_ctx)

                sent_est = int(len(cold_prompt) / chars_per_token)
                truncated = cold["prompt_eval_count"] < sent_est * 0.85
                row = {
                    "num_ctx": num_ctx,
                    "fill": fill,
                    "sent_tokens_est": sent_est,
                    "cold_prompt_eval_count": cold["prompt_eval_count"],
                    "cold_prefill_s": round(cold["prompt_eval_s"], 4),
                    "delta_prompt_eval_count": delta["prompt_eval_count"],
                    "delta_prefill_s": round(delta["prompt_eval_s"], 4),
                    "evidence_tokens": evidence_tokens,
                    "TRUNCATED": truncated,
                }
                rows.append(row)
                flag = "  <-- SILENTLY TRUNCATED" if truncated else ""
                print(
                    f"num_ctx={num_ctx:>6} fill={fill:.0%}  "
                    f"cold: {cold['prompt_eval_count']:>6} tok / {cold['prompt_eval_s']:>7.3f}s   "
                    f"delta: {delta['prompt_eval_count']:>6} tok / {delta['prompt_eval_s']:>6.3f}s{flag}",
                    flush=True,
                )

    out = Path(__file__).resolve().parents[1] / "logs" / "ctx_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
