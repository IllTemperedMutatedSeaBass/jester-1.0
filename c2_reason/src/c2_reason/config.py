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

    # --- Retrieval (thread 1.0.14, DR-032/DR-033/DR-008) ---------------
    # RETRIEVAL_ENABLED exists so the D0-without-retrieval baseline
    # (DR-026's 3.076 s / 4.959 s) stays reproducible on the same build --
    # otherwise "before retrieval" and "after retrieval" would be two
    # different commits and the comparison would not be like-for-like.
    RETRIEVAL_ENABLED = os.environ.get("C2_RETRIEVAL_ENABLED", "1") == "1"
    # Persist dir / embedding pin are the SAME env vars ingest_config reads
    # (DR-033(b), DR-033's embedding pin) -- deliberately not a second,
    # separately-settable copy, which could point the reader at a different
    # store than the writer wrote.
    CHROMA_PERSIST_DIR = os.environ.get("C2_CHROMA_PERSIST_DIR", "")
    EMBED_MODEL = os.environ.get("C2_EMBED_MODEL", "nomic-embed-text:latest")
    EMBED_MODEL_DIGEST = os.environ.get("C2_EMBED_MODEL_DIGEST", "")
    # DR-032's two shared-shape fields. Exactly one live value each at D0;
    # retrieval.ChromaRetriever validates incoming requests against these
    # and fails loudly on a mismatch (that check is DR-032's own named
    # mitigation for the dead-parameter cost it accepted).
    CORPUS_ID = os.environ.get("C2_CORPUS_ID", "dhi")
    RETRIEVAL_TOP_K = int(os.environ.get("C2_RETRIEVAL_TOP_K", "3"))

    @classmethod
    def require_retrieval_settings(cls) -> None:
        """Only enforced when retrieval is switched ON, so the
        no-retrieval baseline still starts on a box with no store."""
        if not cls.CHROMA_PERSIST_DIR:
            _require("C2_CHROMA_PERSIST_DIR")
        if not cls.EMBED_MODEL_DIGEST:
            _require("C2_EMBED_MODEL_DIGEST")
