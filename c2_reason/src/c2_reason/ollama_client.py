"""Thin httpx wrapper over the Ollama /api/generate endpoint.

Returns the raw response body (not just the text) because
prompt_eval_duration / eval_duration are the prefill/generate split Bar B's
decomposition needs, and Ollama already reports them per call -- no
separate probe required (DR-017 Bar A item 3).
"""
import httpx

from .config import Config


def generate(config: Config, prompt: str) -> dict:
    response = httpx.post(
        f"{config.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": config.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": config.NUM_CTX,
                "num_predict": config.MAX_TOKENS,
            },
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()
