"""Persistent Chroma store for 1.x's OWN corpus. DR-033(b): a separate
persistent directory per stream, never a shared collection with 2.x -- the
directory comes from C2_CHROMA_PERSIST_DIR (ingest_config.IngestConfig),
required, no default (see that module's docstring for why).

DR-033's embedding pin: a store records the embedding model digest it was
built with as store-level metadata (a sidecar JSON next to the persist
directory, since Chroma's own collection.metadata is the natural place but
we also want it readable without opening Chroma at all), so a mismatch
between the currently-pinned embedding model and a store's recorded digest
is DETECTABLE at open time rather than silently returning results from a
corrupted similarity space.

DR-008: Tier 1 and Tier 2(a/b) are separate Chroma COLLECTIONS inside this
one persistent directory -- "separate collections," not "separate
directories per tier." DR-033(b)'s directory-separation ruling is about the
1.x/2.x boundary; DR-008's collection-separation ruling is about the
tier boundary within 1.x. Both are satisfied: one directory (this stream's
own), two-plus collections inside it (tier1, tier2a, tier2b, unassigned),
never blended.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import chromadb
import ollama

from .ingest_config import IngestConfig

_DIGEST_SIDECAR = "embedding_digest.json"

_COLLECTION_NAMES = {
    "tier1": "jester1x_tier1",
    "tier2a": "jester1x_tier2a_law_standards_text",
    "tier2b": "jester1x_tier2b_derived_criteria",
    "unassigned": "jester1x_unassigned_nontriggering",
}


class EmbeddingDigestMismatch(RuntimeError):
    pass


def _digest_sidecar_path(persist_dir: str) -> Path:
    return Path(persist_dir) / _DIGEST_SIDECAR


def check_and_record_digest(persist_dir: str, digest: str) -> None:
    """Fails loudly on mismatch (DR-033). Records the digest on first use."""
    path = _digest_sidecar_path(persist_dir)
    if path.exists():
        recorded = json.loads(path.read_text()).get("embedding_model_digest")
        if recorded != digest:
            raise EmbeddingDigestMismatch(
                f"store at {persist_dir} was built with digest {recorded!r}, "
                f"current pinned digest is {digest!r} -- refusing to write "
                f"against a possibly-corrupted similarity space (DR-033)."
            )
    else:
        os.makedirs(persist_dir, exist_ok=True)
        path.write_text(json.dumps({"embedding_model_digest": digest}, indent=2))


def embed(texts: list[str], base_url: str, model: str) -> list[list[float]]:
    client = ollama.Client(host=base_url)
    vectors = []
    for text in texts:
        resp = client.embeddings(model=model, prompt=text)
        vectors.append(resp["embedding"])
    return vectors


def get_client(persist_dir: str) -> "chromadb.ClientAPI":
    return chromadb.PersistentClient(path=persist_dir)


def get_collection(client, tier: str):
    name = _COLLECTION_NAMES.get(tier)
    if name is None:
        raise ValueError(f"unknown tier {tier!r}")
    return client.get_or_create_collection(name=name)
