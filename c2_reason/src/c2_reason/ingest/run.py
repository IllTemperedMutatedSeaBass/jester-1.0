"""D1 ingest entrypoint: read Jester_IN, convert, tier, chunk, embed, store.
Read-only against JESTER_IN_DIR -- this module never opens a path under it
for writing, by construction (only Path.open in 'rb' mode is ever called on
source files).

Usage:
    C2_CHROMA_PERSIST_DIR=/home/jester/jester-1.0/c2_reason/chroma_store \\
    C2_EMBED_MODEL_DIGEST=sha256-970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6 \\
    python -m c2_reason.ingest.run
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from . import converters, tiering, chunking, store
from .ingest_config import IngestConfig

# The Jester_IN survey (thread D1) found the corpus mirrored twice on the
# volume: the top-level DHI-*/  and _cross-entity/ trees, and an identical
# copy under engagement/ (verified by md5sum, not assumed -- see the STOP
# report). Ingesting both would double-count every document. Only the
# top-level tree is walked; engagement/ is skipped as a known duplicate
# mirror, not silently ignored.
_SKIP_DIR_NAMES = {"System Volume Information", "engagement"}

# charter_dhi.json / charter_dhi.json.old are the 2.x assessor's OWN
# engagement-scoping config (role, criteria_edition, org_boundary) -- not a
# DHI document. Excluded from ingest as tooling artefact, not corpus
# content; recorded here so the exclusion is a decision, not an oversight.
_SKIP_FILENAMES = {"charter_dhi.json", "charter_dhi.json.old"}

_CONVERTERS = {
    ".pptx": converters.convert_pptx,
    ".jpg": converters.convert_image,
    ".jpeg": converters.convert_image,
    ".png": converters.convert_image,
}


def _log(event: str, **fields) -> None:
    print(json.dumps({"ts": time.time(), "event": event, **fields}), file=sys.stderr)


def _iter_source_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        if path.name in _SKIP_FILENAMES:
            continue
        yield path


def run() -> dict:
    started = time.time()
    root = Path(IngestConfig.JESTER_IN_DIR)
    if not root.is_dir():
        _log("ingest.abort", reason="jester_in_not_mounted", path=str(root))
        raise SystemExit(f"{root} is not mounted or not a directory -- aborting, per read-only survey convention.")

    store.check_and_record_digest(IngestConfig.CHROMA_PERSIST_DIR, IngestConfig.EMBED_MODEL_DIGEST)
    client = store.get_client(IngestConfig.CHROMA_PERSIST_DIR)

    stats = {
        "documents_seen": 0,
        "documents_processed": 0,
        "documents_rejected": 0,
        "documents_unprocessed": 0,
        "documents_degraded": 0,
        "chunks_written": 0,
        "by_tier": {},
        "rejects": [],
        "failures": [],
    }

    for path in _iter_source_files(root):
        stats["documents_seen"] += 1
        rel = str(path.relative_to(root))
        suffix = path.suffix.lower()
        conv = _CONVERTERS.get(suffix)
        if conv is None:
            stats["documents_unprocessed"] += 1
            stats["failures"].append({"path": rel, "reason": f"no converter for {suffix!r}"})
            _log("ingest.skip", path=rel, reason="no-converter", suffix=suffix)
            continue

        text, status, reason = conv(path)
        if status == converters.UNPROCESSED:
            stats["documents_unprocessed"] += 1
            stats["failures"].append({"path": rel, "reason": reason})
            _log("ingest.convert_failed", path=rel, reason=reason)
            continue
        if status == converters.DEGRADED:
            stats["documents_degraded"] += 1
            _log("ingest.degraded", path=rel, reason=reason)
            if not text.strip():
                continue  # nothing to tier/chunk/store

        tier, evidence = tiering.classify(rel, text)
        if tier == tiering.REJECTED:
            stats["documents_rejected"] += 1
            stats["rejects"].append({"path": rel, "evidence": evidence})
            _log("ingest.rejected", path=rel, evidence=evidence)
            continue

        chunks = chunking.chunk_text(text)
        if not chunks:
            _log("ingest.no_chunks", path=rel, tier=tier)
            continue

        vectors = store.embed(chunks, IngestConfig.OLLAMA_BASE_URL, IngestConfig.EMBED_MODEL)
        collection = store.get_collection(client, tier)
        ids = [f"{rel}::chunk{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source_path": rel,
                "tier": tier,
                "tier_evidence": evidence,
                "chunk_index": i,
                "embedding_model": IngestConfig.EMBED_MODEL,
                "embedding_model_digest": IngestConfig.EMBED_MODEL_DIGEST,
            }
            for i in range(len(chunks))
        ]
        collection.upsert(ids=ids, embeddings=vectors, documents=chunks, metadatas=metadatas)

        stats["documents_processed"] += 1
        stats["chunks_written"] += len(chunks)
        stats["by_tier"][tier] = stats["by_tier"].get(tier, 0) + 1
        _log("ingest.stored", path=rel, tier=tier, evidence=evidence, chunks=len(chunks))

    stats["elapsed_seconds"] = round(time.time() - started, 2)
    _log("ingest.complete", **{k: v for k, v in stats.items() if k not in ("rejects", "failures")})
    return stats


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
