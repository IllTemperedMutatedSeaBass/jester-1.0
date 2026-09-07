"""C2 HTTP surface: stable-prefix-plus-append reasoning over Ollama.

POST /respond takes the rolling transcript for a turn and returns the
capped completion. Prefill and generate are logged as separate stage
boundaries using Ollama's own prompt_eval_duration / eval_duration, which
is Bar B's "C2 prefill" / "C2 generate" decomposition (DR-017).

RETRIEVAL STAGE BOUNDARY (thread 1.0.14) -- read before moving anything in
`respond()`. Bar B computes `c2_prefill_s` as
`prefill_done_monotonic_ts - prefill_start.monotonic_ts`, and
`prefill_done_monotonic_ts` is `call_start + prompt_eval_duration`. That
stage therefore absorbs EVERYTHING between the `prefill_start` log line
and the Ollama call. If retrieval runs after `prefill_start`, its cost
lands silently inside `c2_prefill_s` and the new retrieval stage reads as
zero -- no error, just a wrong decomposition. So `retrieval_start` is the
first statement in the handler and `prefill_start` is logged only AFTER
`retrieval_done`. `bar_b_harness._PARTITION_STAGES` carries `retrieval_s`
as a full partition member; `partition_gap_median_s` is the check that
this re-anchoring is right, and it is verified on the smoke run rather
than assumed.

Both retrieval events are emitted on EVERY turn, including when retrieval
is disabled or returns nothing, because `decompose_turn` drops any turn
missing a required event -- conditional logging would silently bias the
sample toward turns that happened to retrieve.
"""
import time

from fastapi import FastAPI
from pydantic import BaseModel

from .config import Config
from .logging_util import log_event
from .ollama_client import generate
from .prompt import (
    PREAMBLE_LEAK_SIGNATURE,
    PromptBuilder,
    PromptOverflowError,
    estimate_tokens,
)
from .retrieval import (
    ChromaRetriever,
    NullRetriever,
    RetrievalRequest,
    format_evidence,
    INTENT_QUESTION_ANSWERING,
    MODE_MEETING_SPOKEN,
)


FALLBACK_ON_LEAK = "Sorry, could you say that again?"


def _strip_leaked_preamble(text: str) -> tuple[str, bool]:
    """DR-027: detect the model echoing STABLE_PREAMBLE instead of
    replying (reproduced live, thread 1.0.11 -- see prompt.py's
    docstring). Returns (cleaned_text, leak_detected). A leak always
    starts with PREAMBLE_LEAK_SIGNATURE (possibly cap-truncated partway
    through), so on detection the whole response is replaced with a short
    fixed fallback rather than trying to salvage a partial tail -- there
    is no genuine reply content in a response that IS the echoed
    instructions, and returning empty text risks an edge case in
    zero-length TTS input downstream at C4."""
    normalized = " ".join(text.lower().split())
    if normalized.startswith(PREAMBLE_LEAK_SIGNATURE):
        return FALLBACK_ON_LEAK, True
    return text, False

config = Config()
app = FastAPI()

# One PromptBuilder per process: the stable prefix (preamble + rolling
# transcript) accumulates across turns so G1's prefix reuse is exercised
# call over call, not rebuilt from scratch each turn.
prompt_builder = PromptBuilder(
    num_ctx=config.NUM_CTX,
    guard_margin_tokens=config.CONTEXT_GUARD_MARGIN_TOKENS,
)


def _build_retriever():
    """One retriever per process. Constructed at import so a bad store
    path or a digest mismatch (DR-033's silent-corruption failure mode)
    kills C2 at startup rather than on turn 7 of a spoken run."""
    if not config.RETRIEVAL_ENABLED:
        return NullRetriever()
    config.require_retrieval_settings()
    return ChromaRetriever(
        persist_dir=config.CHROMA_PERSIST_DIR,
        ollama_base_url=config.OLLAMA_BASE_URL,
        embed_model=config.EMBED_MODEL,
        embed_model_digest=config.EMBED_MODEL_DIGEST,
        corpus_id=config.CORPUS_ID,
    )


retriever = _build_retriever()


class RespondRequest(BaseModel):
    turn_id: str
    speaker: str
    text: str
    # DR-032's two shared-shape fields, defaulted to the single live D0
    # values. `retrieval.ChromaRetriever._validate` rejects a mismatch
    # against C2's configured corpus/mode rather than answering from the
    # wrong corpus quietly.
    corpus_id: str | None = None
    mode: str = MODE_MEETING_SPOKEN
    intent: str = INTENT_QUESTION_ANSWERING
    # Explicit query override. A chat caller (DR-032's second caller) has
    # no rolling transcript, so the query cannot be assumed to be "the
    # last transcript line" -- it is a field. When absent, this turn's own
    # text is the query, which is what the 1.x spoken caller wants.
    query: str | None = None
    # Caller-supplied evidence, retained from D0. When retrieval is on,
    # C2 retrieves its own and this stays None.
    evidence: str | None = None


class RespondResponse(BaseModel):
    turn_id: str
    text: str
    max_tokens: int
    model: str
    model_digest: str
    retrieved_chunks: int = 0
    evidence_tokens_est: int = 0
    # DR-039's overflow guard. "ok" on a normal turn; "context_exhausted"
    # when the guard fired. C5 branches on this rather than on an
    # exception, which is the whole point: an overflow must degrade one
    # turn, never terminate the run.
    status: str = "ok"


STATUS_OK = "ok"
STATUS_CONTEXT_EXHAUSTED = "context_exhausted"

# Spoken ONCE, on the first overflow only. See DR-039 for the argument:
# repeating this every turn would be worse than silence (once the window
# is exhausted the transcript only grows, so EVERY subsequent turn
# overflows), but saying nothing at all is ambiguous in a product whose
# entire thesis is that silence is meaningful (DR-008).
CONTEXT_EXHAUSTED_NOTICE = (
    "I've reached the limit of what I can keep track of, so I'll stop "
    "commenting from here. Carry on without me."
)


class _OverflowState:
    """Process-level, matching `prompt_builder`'s own process-level scope
    -- one C2 process serves one meeting at D0. Deliberately NOT
    per-request: a flag that reset each turn would make Jester announce
    its own failure twenty times in a row."""

    announced = False


@app.post("/respond", response_model=RespondResponse)
def respond(req: RespondRequest) -> RespondResponse:
    turn_id = req.turn_id

    # --- RETRIEVAL STAGE (must close before prefill_start; see module
    # docstring for why moving this is a silent measurement error) ------
    log_event("C2", "retrieval_start", turn_id)
    retrieval_result = retriever.retrieve(
        RetrievalRequest(
            corpus_id=req.corpus_id or config.CORPUS_ID,
            mode=req.mode,
            query=(req.query or req.text),
            intent=req.intent,
            top_k=config.RETRIEVAL_TOP_K,
        )
    )
    retrieved_evidence = format_evidence(retrieval_result)
    # A caller-supplied `evidence` string still wins, so the D0 path is
    # unchanged when retrieval is off; it is not merged with retrieved
    # evidence, which would make the appended region ambiguous.
    evidence = req.evidence if req.evidence else (retrieved_evidence or None)
    evidence_tokens_est = estimate_tokens(evidence or "")
    log_event(
        "C2",
        "retrieval_done",
        turn_id,
        retrieval_enabled=config.RETRIEVAL_ENABLED,
        chunks_by_path=retrieval_result.counts(),
        chunks_total=retrieval_result.total_chunks,
        tier2_consulted=retrieval_result.tier2_consulted,
        embed_s=retrieval_result.embed_s,
        query_s=retrieval_result.query_s,
        evidence_chars=len(evidence or ""),
        evidence_tokens_est=evidence_tokens_est,
        embed_model=config.EMBED_MODEL,
        embed_model_digest=config.EMBED_MODEL_DIGEST,
    )

    log_event("C2", "prefill_start", turn_id)

    # The transcript line is appended even on an overflow turn: the
    # transcript is the meeting's record, and dropping lines here would be
    # a truncation policy by the back door (DR-013(b) reserves that to the
    # operator). What the guard refuses to do is CALL THE MODEL.
    prompt_builder.append_transcript_line(req.speaker, req.text)
    try:
        prompt = prompt_builder.build(evidence=evidence)
    except PromptOverflowError as exc:
        first_time = not _OverflowState.announced
        _OverflowState.announced = True
        log_event(
            "C2",
            "context_exhausted",
            turn_id,
            error=str(exc),
            first_occurrence=first_time,
            spoken_notice=first_time,
            num_ctx=config.NUM_CTX,
            guard_margin_tokens=prompt_builder.guard_margin_tokens,
        )
        # A controlled, successful HTTP response -- NOT a 500. A 500 here
        # is what terminated the whole run before DR-039.
        return RespondResponse(
            turn_id=turn_id,
            text=CONTEXT_EXHAUSTED_NOTICE if first_time else "",
            max_tokens=config.MAX_TOKENS,
            model=config.OLLAMA_MODEL,
            model_digest=config.OLLAMA_MODEL_DIGEST,
            retrieved_chunks=retrieval_result.total_chunks,
            evidence_tokens_est=evidence_tokens_est,
            status=STATUS_CONTEXT_EXHAUSTED,
        )

    call_start = time.monotonic()
    result = generate(config, prompt)
    call_end = time.monotonic()

    # DR-039 backstop. The guard above works off a chars-per-token
    # ESTIMATE, not a tokenizer, so it can be wrong on unusual text.
    # Ollama's own prompt_eval_count is ground truth for what it actually
    # evaluated: if that comes back far below what we sent, Ollama
    # truncated silently despite the guard and the reply is built on a
    # mutilated prompt. That must be visible in the logs, because nothing
    # else about the response would reveal it -- it returns HTTP 200 and
    # reads as a normal answer.
    prompt_tokens_est = estimate_tokens(prompt)
    actual_prompt_tokens = result.get("prompt_eval_count", 0)
    if actual_prompt_tokens and actual_prompt_tokens < prompt_tokens_est * 0.85:
        log_event(
            "C2",
            "silent_truncation_detected",
            turn_id,
            prompt_tokens_est=prompt_tokens_est,
            prompt_eval_count=actual_prompt_tokens,
            num_ctx=config.NUM_CTX,
            note="Ollama truncated the prompt despite the DR-039 guard; "
                 "the cached prefix is destroyed and transcript was "
                 "discarded. The guard margin or the token estimator "
                 "needs revisiting.",
        )

    prompt_eval_duration_s = result.get("prompt_eval_duration", 0) / 1e9
    eval_duration_s = result.get("eval_duration", 0) / 1e9
    prefill_done_ts = call_start + prompt_eval_duration_s
    generate_done_ts = call_end

    log_event(
        "C2",
        "prefill_done",
        turn_id,
        prefill_done_monotonic_ts=prefill_done_ts,
        prompt_eval_count=result.get("prompt_eval_count"),
        # Logged next to Ollama's own exact prompt_eval_count so the
        # evidence-attributable share of prefill is IN THE DATA rather
        # than argued after the fact: prompt_eval_count is the tokens
        # actually prefilled this turn (delta, on a cache hit), and
        # evidence_tokens_est is the estimated share of it that is
        # retrieved evidence. That is the retrieval cost that dominates
        # T_ttfa -- the embed+query stage above is the smaller half.
        evidence_tokens_est=evidence_tokens_est,
        prompt_chars=len(prompt),
        prompt_tokens_est=estimate_tokens(prompt),
        model=config.OLLAMA_MODEL,
        model_digest=config.OLLAMA_MODEL_DIGEST,
    )
    log_event(
        "C2",
        "generate_done",
        turn_id,
        generate_done_monotonic_ts=generate_done_ts,
        eval_count=result.get("eval_count"),
        eval_duration_s=eval_duration_s,
        max_tokens_cap=config.MAX_TOKENS,
        model=config.OLLAMA_MODEL,
        model_digest=config.OLLAMA_MODEL_DIGEST,
    )

    reply_text, leak_detected = _strip_leaked_preamble(result["response"])
    if leak_detected:
        log_event(
            "C2",
            "preamble_leak_detected",
            turn_id,
            raw_eval_count=result.get("eval_count"),
            cap_hit=result.get("eval_count") == config.MAX_TOKENS,
        )

    return RespondResponse(
        turn_id=turn_id,
        text=reply_text,
        max_tokens=config.MAX_TOKENS,
        model=config.OLLAMA_MODEL,
        model_digest=config.OLLAMA_MODEL_DIGEST,
        retrieved_chunks=retrieval_result.total_chunks,
        evidence_tokens_est=evidence_tokens_est,
    )


def run():
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    run()
