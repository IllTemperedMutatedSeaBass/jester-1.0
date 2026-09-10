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
from .conflict import build_conflict_prompt, parse_conflict_reply
from .retrieval import (
    ChromaRetriever,
    NullRetriever,
    RetrievalRequest,
    format_evidence,
    INTENT_CONFLICT_CHECK,
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


class ConflictCheckRequest(BaseModel):
    turn_id: str
    # The line to check -- the utterance that just completed.
    utterance: str
    # Recent transcript for context. C3 sends a bounded window, not the
    # whole meeting: see the endpoint docstring.
    transcript: str = ""
    corpus_id: str | None = None
    mode: str = MODE_MEETING_SPOKEN


class ConflictCheckResponse(BaseModel):
    turn_id: str
    conflict: bool
    # Present only when conflict is True. Structured, never prose --
    # DR-044's citation must reach speech as prose composed by C3's merge
    # step, not as a pre-formatted string carrying a bracket marker.
    utterance: str | None = None
    conflicts_with: str | None = None
    source: str | None = None
    authority: str | None = None
    tier: str | None = None
    retrieved_chunks: int = 0
    unified_corpus: bool = False
    rejected_reason: str = ""
    model: str = ""
    model_digest: str = ""


@app.post("/conflict_check", response_model=ConflictCheckResponse)
def conflict_check(req: ConflictCheckRequest) -> ConflictCheckResponse:
    """DR-043(e)(i)'s reasoning gate. Called by C3, never by C5 directly.

    DELIBERATELY SEPARATE FROM `/respond`, for two reasons that are easy to
    undo by accident:

      1. `prompt_builder` IS PROCESS-LEVEL AND ACCUMULATING. `/respond`
         appends every turn to it so G1's prefix reuse is exercised call
         over call. If this endpoint appended to it too, the meeting
         transcript would gain lines nobody said, and every Bar B figure
         measured against that prefix would be measuring a different
         prompt. This handler builds a STANDALONE prompt and touches
         `prompt_builder` not at all.

      2. `/respond`'s stage-boundary logging is Bar B's decomposition and
         is anchored precisely (see the module docstring -- moving
         retrieval relative to `prefill_start` silently mis-attributes its
         cost). Adding a second code path through the same handler would
         put non-Bar-B turns into the same event stream. This endpoint
         emits its OWN event names, so `decompose_turn` cannot pick them
         up and the Bar B sample stays exactly the turns C5 drove.

    SAME MODEL AS `/respond`, deliberately (`config.OLLAMA_MODEL`). That is
    the point of putting the judgement at C2 at all: no model swap, so no
    Ollama reload between a conflict check and the next spoken reply. See
    `conflict.py`'s docstring for the full reasoning and for the incorrect
    UMA-carve claim that must not be inherited.
    """
    turn_id = req.turn_id
    log_event("C2", "conflict_check_start", turn_id)

    retrieval_result = retriever.retrieve(
        RetrievalRequest(
            corpus_id=req.corpus_id or config.CORPUS_ID,
            mode=req.mode,
            query=req.utterance,
            intent=INTENT_CONFLICT_CHECK,
            top_k=config.RETRIEVAL_TOP_K,
        )
    )
    evidence = format_evidence(retrieval_result)
    log_event(
        "C2",
        "conflict_check_retrieved",
        turn_id,
        chunks_by_path=retrieval_result.counts(),
        chunks_total=retrieval_result.total_chunks,
        unified_corpus=retrieval_result.unified_corpus,
        embed_s=retrieval_result.embed_s,
        query_s=retrieval_result.query_s,
    )

    # Nothing retrieved means nothing to contradict. Returning early skips
    # a model call that could only invent -- the failure mode the prompt is
    # written against.
    if retrieval_result.total_chunks == 0:
        log_event("C2", "conflict_check_done", turn_id, conflict=False,
                  reason="no chunks retrieved")
        return ConflictCheckResponse(
            turn_id=turn_id, conflict=False, retrieved_chunks=0,
            unified_corpus=retrieval_result.unified_corpus,
            rejected_reason="no chunks retrieved",
            model=config.OLLAMA_MODEL, model_digest=config.OLLAMA_MODEL_DIGEST,
        )

    prompt = build_conflict_prompt(req.transcript, req.utterance, evidence)
    result = generate(config, prompt, max_tokens=config.CONFLICT_MAX_TOKENS)
    outcome = parse_conflict_reply(
        result.get("response", ""), retrieval_result, req.utterance, turn_id
    )

    log_event(
        "C2",
        "conflict_check_done",
        turn_id,
        conflict=outcome.conflict,
        rejected_reason=outcome.rejected_reason,
        sources_offered=outcome.sources_offered,
        source=outcome.candidate.source if outcome.candidate else None,
        authority=outcome.candidate.authority if outcome.candidate else None,
        eval_count=result.get("eval_count"),
        prompt_eval_count=result.get("prompt_eval_count"),
        model=config.OLLAMA_MODEL,
        model_digest=config.OLLAMA_MODEL_DIGEST,
    )

    if not outcome.conflict:
        return ConflictCheckResponse(
            turn_id=turn_id, conflict=False,
            retrieved_chunks=retrieval_result.total_chunks,
            unified_corpus=retrieval_result.unified_corpus,
            rejected_reason=outcome.rejected_reason,
            model=config.OLLAMA_MODEL, model_digest=config.OLLAMA_MODEL_DIGEST,
        )

    candidate = outcome.candidate
    return ConflictCheckResponse(
        turn_id=turn_id,
        conflict=True,
        utterance=candidate.utterance,
        conflicts_with=candidate.conflicts_with,
        source=candidate.source,
        authority=candidate.authority,
        tier=candidate.tier,
        retrieved_chunks=retrieval_result.total_chunks,
        unified_corpus=retrieval_result.unified_corpus,
        model=config.OLLAMA_MODEL,
        model_digest=config.OLLAMA_MODEL_DIGEST,
    )


def run():
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    run()
