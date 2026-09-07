"""D1 ingest retrieval sanity check (Task 4) -- confirms the store is
searchable, not a quality evaluation. Run with the same env vars as
c2_reason.ingest.run."""
import sys
sys.path.insert(0, "src")
from c2_reason.ingest import store
from c2_reason.ingest.ingest_config import IngestConfig

client = store.get_client(IngestConfig.CHROMA_PERSIST_DIR)

queries = [
    ("tier1", "board governance structure of DHI Group"),
    ("tier1", "AI management system process and risk compliance"),
    ("unassigned", "project status of the ERP upgrade programme"),
    ("unassigned", "AI awareness training for staff"),
    ("unassigned", "whiteboard notes from a workshop"),
]

for tier, q in queries:
    coll = store.get_collection(client, tier)
    vec = store.embed([q], IngestConfig.OLLAMA_BASE_URL, IngestConfig.EMBED_MODEL)[0]
    res = coll.query(query_embeddings=[vec], n_results=2)
    print(f"\n=== [{tier}] {q!r} ===")
    for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
        print(f"  {meta['source_path']}  (chunk {meta['chunk_index']})")
        print(f"    {doc[:150]!r}")
