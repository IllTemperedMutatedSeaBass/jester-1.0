"""Env-driven config for the D1 ingest pipeline, following c2_reason.config's
own convention (DR-020): required values fail loudly rather than falling
back to a guessed default, because a silently-wrong path or digest is worse
than a crash at startup.

CHROMA_PERSIST_DIR is DR-033(b)'s "one environment variable... pointing 1.x's
store at its own directory, distinct from 2.x's" -- required, no default, so
a session can never accidentally write into 2.x's store by inheriting a
convenient-looking default.

EMBED_MODEL / EMBED_MODEL_DIGEST follow DR-033's embedding pin, mirroring
config.py's OLLAMA_MODEL / OLLAMA_MODEL_DIGEST pattern exactly.

JESTER_IN_DIR is the read-only source volume (DR-031); read-only is enforced
in code (ingest/run.py never opens it for writing), not by this config.
"""
import os


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is required and unset. Ingest must not guess a corpus "
            f"path or embedding identity -- set {name} explicitly."
        )
    return value


class IngestConfig:
    JESTER_IN_DIR = os.environ.get("JESTER_IN_DIR", "/mnt/jester_in")
    CHROMA_PERSIST_DIR = _require("C2_CHROMA_PERSIST_DIR")
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    EMBED_MODEL = os.environ.get("C2_EMBED_MODEL", "nomic-embed-text:latest")
    EMBED_MODEL_DIGEST = _require("C2_EMBED_MODEL_DIGEST")
