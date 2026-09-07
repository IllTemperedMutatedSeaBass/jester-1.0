"""DR-008 path-separation and DR-032 field-validation tests.

These use a fake collection layer rather than the live Chroma store: the
properties under test are structural (which collection each path queries,
in what order, under what condition) and must hold on a box with no store
at all. Live searchability was verified separately against the real store
(thread 1.0.13, `verify_retrieval.py`) and again by this thread's smoke
run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from c2_reason import retrieval
from c2_reason.retrieval import (
    ChromaRetriever,
    NullRetriever,
    RetrievalConfigError,
    RetrievalRequest,
    UnsupportedModeError,
    format_evidence,
    MODE_CHAT,
    MODE_MEETING_SPOKEN,
    PATH_TIER1,
    PATH_TIER2A,
    PATH_TIER2B,
    PATH_UNASSIGNED,
)


class _FakeCollection:
    def __init__(self, name, docs):
        self.name = name
        self._docs = docs

    def count(self):
        return len(self._docs)

    def query(self, query_embeddings, n_results):
        docs = self._docs[:n_results]
        return {
            "documents": [[d["text"] for d in docs]],
            "metadatas": [[
                {"source_path": d["src"], "tier": self.name, "chunk_index": i}
                for i, d in enumerate(docs)
            ]],
            "distances": [[0.1] * len(docs)],
        }


class _FakeStore:
    """Records every (collection, query) pair so the test can assert that
    each path issued its OWN query against its OWN collection -- the
    structural form of DR-008's "never blended into one index"."""

    def __init__(self, contents):
        self.contents = contents
        self.queried = []

    def install(self, monkeypatch):
        monkeypatch.setattr(retrieval.store, "check_and_record_digest",
                            lambda *a, **k: None)
        monkeypatch.setattr(retrieval.store, "get_client", lambda p: object())
        monkeypatch.setattr(retrieval.store, "embed",
                            lambda texts, base_url, model: [[0.0, 1.0]])

        def _get_collection(client, tier):
            self.queried.append(tier)
            return _FakeCollection(tier, self.contents.get(tier, []))

        monkeypatch.setattr(retrieval.store, "get_collection", _get_collection)


def _retriever():
    return ChromaRetriever(
        persist_dir="/nonexistent",
        ollama_base_url="http://127.0.0.1:11434",
        embed_model="nomic-embed-text:latest",
        embed_model_digest="sha256-deadbeef",
        corpus_id="dhi",
    )


def _request(**kwargs):
    base = dict(corpus_id="dhi", mode=MODE_MEETING_SPOKEN, query="who approved it")
    base.update(kwargs)
    return RetrievalRequest(**base)


POPULATED = {
    PATH_TIER1: [{"text": "The board approved phase 2.", "src": "minutes.pptx"}],
    PATH_UNASSIGNED: [{"text": "ERP status amber.", "src": "pmo.pptx"}],
}


def test_each_path_queries_its_own_collection_never_a_blended_one(monkeypatch):
    fake = _FakeStore(POPULATED)
    fake.install(monkeypatch)
    result = _retriever().retrieve(_request())

    # Tier 1 and unassigned were queried as separate collections.
    assert PATH_TIER1 in fake.queried
    assert PATH_UNASSIGNED in fake.queried
    # Results stay separated by path, never merged into one list.
    assert result.by_path[PATH_TIER1][0].source_path == "minutes.pptx"
    assert result.by_path[PATH_UNASSIGNED][0].source_path == "pmo.pptx"
    # No collection name outside the four DR-008/DR-031 collections was
    # ever opened -- i.e. there is no combined index.
    assert set(fake.queried) <= {
        PATH_TIER1, PATH_UNASSIGNED, PATH_TIER2A, PATH_TIER2B
    }


def test_tier2_is_consulted_only_after_tier1_flags_a_candidate(monkeypatch):
    """DR-008: Tier 2 is 'Queried ONLY after Tier 1 has flagged a
    candidate... NEVER a trigger source on its own.'"""
    fake = _FakeStore(POPULATED)
    fake.install(monkeypatch)
    result = _retriever().retrieve(_request())
    assert result.tier2_consulted is True
    assert PATH_TIER2A in fake.queried and PATH_TIER2B in fake.queried


def test_tier2_is_not_consulted_when_tier1_returns_nothing(monkeypatch):
    fake = _FakeStore({PATH_UNASSIGNED: POPULATED[PATH_UNASSIGNED]})
    fake.install(monkeypatch)
    result = _retriever().retrieve(_request())
    assert result.tier2_consulted is False
    assert PATH_TIER2A not in fake.queried
    assert PATH_TIER2B not in fake.queried


def test_unassigned_path_is_gated_on_question_answering_intent(monkeypatch):
    """The unassigned collection is a question-answering READ path only
    (DR-035). It must never be reachable by a non-QA intent -- which is
    what a future C3 trigger caller would be."""
    fake = _FakeStore(POPULATED)
    fake.install(monkeypatch)
    with pytest.raises(UnsupportedModeError):
        _retriever().retrieve(_request(intent="trigger_scan"))
    assert PATH_UNASSIGNED not in fake.queried


def test_corpus_id_mismatch_fails_loudly(monkeypatch):
    """DR-032 named the dead-parameter cost: 'can be mis-set with nothing
    to catch it'. This check is the mitigation."""
    fake = _FakeStore(POPULATED)
    fake.install(monkeypatch)
    with pytest.raises(RetrievalConfigError):
        _retriever().retrieve(_request(corpus_id="some_other_corpus"))


def test_unimplemented_mode_fails_loudly_rather_than_behaving_like_the_other(monkeypatch):
    fake = _FakeStore(POPULATED)
    fake.install(monkeypatch)
    with pytest.raises(UnsupportedModeError):
        _retriever().retrieve(_request(mode=MODE_CHAT))


def test_empty_query_retrieves_nothing_without_calling_the_store(monkeypatch):
    fake = _FakeStore(POPULATED)
    fake.install(monkeypatch)
    result = _retriever().retrieve(_request(query="   "))
    assert result.total_chunks == 0
    assert fake.queried == []


def test_format_evidence_is_empty_when_nothing_retrieved():
    """An empty '[Evidence]' header would still be tokens appended every
    turn for no content."""
    assert format_evidence(NullRetriever().retrieve(_request())) == ""


def test_format_evidence_labels_every_chunk_with_its_tier(monkeypatch):
    fake = _FakeStore(POPULATED)
    fake.install(monkeypatch)
    text = format_evidence(_retriever().retrieve(_request()))
    assert "-- Company record --" in text
    assert "-- Other meeting material --" in text
    assert "minutes.pptx" in text and "pmo.pptx" in text
    # Tier 1 renders before the unassigned material.
    assert text.index("Company record") < text.index("Other meeting material")


def test_null_retriever_returns_an_empty_result_not_none():
    """Every caller path must be identical with and without retrieval, so
    the Bar B harness sees retrieval events on every turn and no turn is
    silently dropped from the sample."""
    result = NullRetriever().retrieve(_request())
    assert result.total_chunks == 0
    assert result.counts() == {}
