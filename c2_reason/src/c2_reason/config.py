"""Env-driven config for C2.

OLLAMA_MODEL and OLLAMA_MODEL_DIGEST are both required, no default, per
DR-020's standing convention: a tag is mutable, a digest is not, and every
measured figure must cite both. Fail loudly on startup if either is unset
rather than silently falling back to a guessed tag (DR-019/DR-020).
"""
import os


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is required and unset. Per DR-020, C2 must not guess a "
            f"model identity -- set {name} explicitly in the environment."
        )
    return value


class Config:
    HOST = os.environ.get("C2_HOST", "127.0.0.1")
    PORT = int(os.environ.get("C2_PORT", "8002"))
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL = _require("OLLAMA_MODEL")
    OLLAMA_MODEL_DIGEST = _require("OLLAMA_MODEL_DIGEST")
    MAX_TOKENS = int(os.environ.get("C2_MAX_TOKENS", "40"))
    NUM_CTX = int(os.environ.get("C2_NUM_CTX", "8192"))
