"""Thin httpx wrapper over the Ollama /api/generate endpoint.

Returns the raw response body (not just the text) because
prompt_eval_duration / eval_duration are the prefill/generate split Bar B's
decomposition needs, and Ollama already reports them per call -- no
separate probe required (DR-017 Bar A item 3).

`raw: true` is set per DR-024: the pinned Modelfile's server-side chat
renderer (RENDERER/PARSER gemma4) puts the model into an unbounded
"thinking" mode that consumes the whole token cap before any final
content, on both /api/generate (untemplated) and /api/chat (templated).
`raw: true` bypasses that renderer entirely; `prompt.PromptBuilder` hand
-renders the Gemma turn markers the model needs instead.

Per DR-027, closing DR-024's stop-sequence gap: `raw: true` also bypasses
Ollama's normal stop-token handling for the chat renderer, so `<end_of_turn>`
must be passed explicitly as a `stop` sequence or the model can emit it as
literal output text (observed thread-1.0.10 turn 9) rather than have it
consumed as a generation-ending token.
"""
import httpx

from .config import Config


def generate(config: Config, prompt: str, max_tokens: int | None = None) -> dict:
    """`max_tokens` overrides `config.MAX_TOKENS` for this call only.

    Added for the DR-043 conflict_check gate, which needs a slightly larger
    cap than the 40-token spoken reply: its answer is a two-line structured
    form, and a cap that truncates the SOURCE line turns a valid conflict
    into a rejected one (`conflict.parse_conflict_reply` refuses a conflict
    with no SOURCE). The spoken path's cap is untouched -- it is a measured
    figure in DR-020/DR-038 and is not changed as a side effect here.
    """
    response = httpx.post(
        f"{config.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": config.OLLAMA_MODEL,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "options": {
                "num_ctx": config.NUM_CTX,
                "num_predict": config.MAX_TOKENS if max_tokens is None else max_tokens,
                "stop": ["<end_of_turn>"],
            },
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()
