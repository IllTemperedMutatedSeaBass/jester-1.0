"""C2 HTTP surface: stable-prefix-plus-append reasoning over Ollama.

POST /respond takes the rolling transcript for a turn and returns the
capped completion. Prefill and generate are logged as separate stage
boundaries using Ollama's own prompt_eval_duration / eval_duration, which
is Bar B's "C2 prefill" / "C2 generate" decomposition (DR-017).
"""
import time

from fastapi import FastAPI
from pydantic import BaseModel

from .config import Config
from .logging_util import log_event
from .ollama_client import generate
from .prompt import PromptBuilder, PromptOverflowError

config = Config()
app = FastAPI()

# One PromptBuilder per process: the stable prefix (preamble + rolling
# transcript) accumulates across turns so G1's prefix reuse is exercised
# call over call, not rebuilt from scratch each turn.
prompt_builder = PromptBuilder(num_ctx=config.NUM_CTX)


class RespondRequest(BaseModel):
    turn_id: str
    speaker: str
    text: str
    evidence: str | None = None


class RespondResponse(BaseModel):
    turn_id: str
    text: str
    max_tokens: int
    model: str
    model_digest: str


@app.post("/respond", response_model=RespondResponse)
def respond(req: RespondRequest) -> RespondResponse:
    turn_id = req.turn_id
    log_event("C2", "prefill_start", turn_id)

    prompt_builder.append_transcript_line(req.speaker, req.text)
    try:
        prompt = prompt_builder.build(evidence=req.evidence)
    except PromptOverflowError as exc:
        log_event("C2", "prompt_overflow", turn_id, error=str(exc))
        raise

    call_start = time.monotonic()
    result = generate(config, prompt)
    call_end = time.monotonic()

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

    return RespondResponse(
        turn_id=turn_id,
        text=result["response"],
        max_tokens=config.MAX_TOKENS,
        model=config.OLLAMA_MODEL,
        model_digest=config.OLLAMA_MODEL_DIGEST,
    )


def run():
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    run()
