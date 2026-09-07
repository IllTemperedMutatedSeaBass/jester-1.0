"""C2's retrieval interface and its Chroma-backed implementation.

Shaped per DR-032: the request carries a `corpus_id` and a `mode` rather
than assuming a meeting transcript, and retrieval sits BEHIND this
interface rather than inlined into `main.respond()`. DR-032 named the cost
of those two fields honestly -- at D0 each has exactly one live value and
"can be mis-set with nothing to catch it until a second caller exists to
disagree" -- so both are validated against the configured live values here
and a mismatch fails loudly, following `config.py`'s own `_require`
fail-loudly convention (DR-020). That check IS the mitigation DR-032 asked
for; without it the fields are decoration.

DR-008 -- SEPARATE COLLECTIONS, SEPARATE RETRIEVAL PATHS, NEVER BLENDED.
Three named paths run here, each issuing its OWN query against its OWN
Chroma collection. They are never merged into a single query, a single
collection, or a single ranked list:

  PATH 1 -- TIER 1 (the company). Always queried.
  PATH 2 -- UNASSIGNED (non-triggering). Queried in question-answering
      mode only. See the ruling note below; this path is read-only
      substantiation for an explicit user question and is NEVER offered to
      a trigger caller.
  PATH 3 -- TIER 2 (law/standards text 2a, derived criteria 2b). Queried
      ONLY after Path 1 returned at least one candidate, per DR-008's
      "Queried ONLY after Tier 1 has flagged a candidate, to confirm and
      cite. NEVER a trigger source on its own." Both 2a and 2b are empty
      on this box today (DR-034: zero documents tiered into either), so
      this path exists and is exercised by the code but returns nothing
      from real data -- the same "path exists, not exercised by real data,
      no claim it works untested" posture DR-034 took for the reject path.

WHY PATH 2 EXISTS AT ALL (ruled in DR-035, recorded here so the code is
readable without the decision log). DR-034 tiered 5 of 46 documents TIER1
and 41 UNASSIGNED. DR-008 restricts Tier 1 to being "THE ONLY TRIGGER
SOURCE -- C3 fires off Tier 1"; that restriction is scoped to TRIGGERING,
and DR-031's safe default for an unassigned document is "non-triggering,"
not "unreadable." This session builds question-answering only -- the user
asks, Jester answers, nothing fires unprompted -- so reading the
unassigned collection on an explicit question is consistent with both
rulings. It is a separately named path against its own collection and is
gated on `mode`; it grants C3 nothing whatsoever. Blending it into Path 1
WOULD violate DR-008 and is why it is not done.

The per-path results are kept separate all the way through
`RetrievalResult`. `format_evidence()` concatenates them into one labelled
evidence block for the prompt, which is not a violation: DR-008 forbids a
blended INDEX and blended retrieval paths, and every chunk here still
carries the tier it was retrieved from.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from .ingest import store

# DR-032's `mode`. Exactly one is live at D0 (the 1.x spoken caller);
# MODE_CHAT is the shape a 2.x chat caller would use and is deliberately
# NOT implemented -- an unimplemented mode that fails loudly is honest,
# a mode that silently behaves like the other one is not.
MODE_MEETING_SPOKEN = "meeting_spoken"
MODE_CHAT = "chat"

# Question-answering is the only retrieval intent this session builds
# (thread 1.0.14 scope: no trigger logic, no unprompted speech).
INTENT_QUESTION_ANSWERING = "question_answering"

PATH_TIER1 = "tier1"
PATH_UNASSIGNED = "unassigned"
PATH_TIER2A = "tier2a"
PATH_TIER2B = "tier2b"


class RetrievalConfigError(RuntimeError):
    pass


class UnsupportedModeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetrievalRequest:
    """DR-032's shared shape: corpus and mode are explicit, and the query
    is passed in rather than assumed to be "the last transcript line" --
    a chat caller has no transcript."""

    corpus_id: str
    mode: str
    query: str
    intent: str = INTENT_QUESTION_ANSWERING
    top_k: int = 3


@dataclass(frozen=True)
class EvidenceChunk:
    text: str
    source_path: str
    tier: str
    chunk_index: int
    distance: float | None


@dataclass
class RetrievalResult:
    """Per-path results stay separate (DR-008). `by_path` is ordered by the
    path constants above so evidence rendering is deterministic turn over
    turn -- non-deterministic evidence ordering would change the appended
    region for no semantic reason, which matters for reproducibility of
    the Bar B figure even though it sits after the cached prefix."""

    by_path: dict[str, list[EvidenceChunk]] = field(default_factory=dict)
    embed_s: float = 0.0
    query_s: float = 0.0
    tier2_consulted: bool = False

    @property
    def total_chunks(self) -> int:
        return sum(len(v) for v in self.by_path.values())

    def counts(self) -> dict[str, int]:
        return {path: len(chunks) for path, chunks in self.by_path.items()}


class Retriever(Protocol):
    def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...


class NullRetriever:
    """Retrieval disabled. Returns an empty result rather than None so
    every caller path is identical with and without retrieval -- the
    measurement harness still sees retrieval_start/retrieval_done on every
    turn, and turns are never silently dropped from the Bar B sample for
    lack of an event."""

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        return RetrievalResult(by_path={})


class ChromaRetriever:
    """Reads the store D1 ingest wrote (DR-033(b): 1.x's OWN persistent
    directory, never a shared collection with 2.x). Collection names come
    from `ingest.store` rather than being restated here, so the reader and
    the writer can never drift apart.

    The embedding digest is checked at CONSTRUCTION, not per query: a
    mismatch means every vector in the store is against a different
    similarity space (DR-033's silent-corruption failure mode), which is a
    startup-time refusal, not a per-request one.
    """

    def __init__(
        self,
        persist_dir: str,
        ollama_base_url: str,
        embed_model: str,
        embed_model_digest: str,
        corpus_id: str,
        supported_modes: tuple[str, ...] = (MODE_MEETING_SPOKEN,),
    ):
        store.check_and_record_digest(persist_dir, embed_model_digest)
        self._client = store.get_client(persist_dir)
        self._base_url = ollama_base_url
        self._embed_model = embed_model
        self._embed_model_digest = embed_model_digest
        self._corpus_id = corpus_id
        self._supported_modes = supported_modes

    def _validate(self, request: RetrievalRequest) -> None:
        """DR-032's dead-parameter mitigation, made real."""
        if request.corpus_id != self._corpus_id:
            raise RetrievalConfigError(
                f"corpus_id {request.corpus_id!r} does not match this C2's "
                f"configured corpus {self._corpus_id!r} -- refusing to "
                f"answer from a corpus the caller did not ask for (DR-032)."
            )
        if request.mode not in self._supported_modes:
            raise UnsupportedModeError(
                f"mode {request.mode!r} is not implemented by this C2 "
                f"(supported: {list(self._supported_modes)}). DR-032 shapes "
                f"the interface for a second caller; it does not build one."
            )
        if request.intent != INTENT_QUESTION_ANSWERING:
            raise UnsupportedModeError(
                f"intent {request.intent!r} is not implemented. Thread "
                f"1.0.14 builds question-answering only -- no trigger "
                f"logic, no unprompted speech."
            )

    def _query_path(
        self, query_vector: list[float], tier: str, top_k: int
    ) -> list[EvidenceChunk]:
        collection = store.get_collection(self._client, tier)
        if collection.count() == 0:
            return []
        result = collection.query(
            query_embeddings=[query_vector], n_results=min(top_k, collection.count())
        )
        chunks = []
        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[None] * len(documents[0])]
        for text, meta, distance in zip(documents[0], metadatas[0], distances[0]):
            chunks.append(
                EvidenceChunk(
                    text=text,
                    source_path=str(meta.get("source_path", "")),
                    tier=str(meta.get("tier", tier)),
                    chunk_index=int(meta.get("chunk_index", -1)),
                    distance=distance,
                )
            )
        return chunks

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        self._validate(request)
        result = RetrievalResult(by_path={})

        query = (request.query or "").strip()
        if not query:
            return result

        embed_start = time.monotonic()
        query_vector = store.embed([query], self._base_url, self._embed_model)[0]
        result.embed_s = time.monotonic() - embed_start

        query_start = time.monotonic()

        # PATH 1 -- Tier 1. Its own query, its own collection.
        result.by_path[PATH_TIER1] = self._query_path(
            query_vector, PATH_TIER1, request.top_k
        )

        # PATH 2 -- unassigned/non-triggering, question-answering only.
        if request.intent == INTENT_QUESTION_ANSWERING:
            result.by_path[PATH_UNASSIGNED] = self._query_path(
                query_vector, PATH_UNASSIGNED, request.top_k
            )

        # PATH 3 -- Tier 2, ONLY after Tier 1 flagged a candidate (DR-008).
        if result.by_path[PATH_TIER1]:
            result.tier2_consulted = True
            for tier2_path in (PATH_TIER2A, PATH_TIER2B):
                result.by_path[tier2_path] = self._query_path(
                    query_vector, tier2_path, request.top_k
                )

        result.query_s = time.monotonic() - query_start
        return result


_PATH_LABELS = {
    PATH_TIER1: "Company record",
    PATH_UNASSIGNED: "Other meeting material",
    PATH_TIER2A: "Law and standards",
    PATH_TIER2B: "Derived criteria",
}

_RENDER_ORDER = (PATH_TIER1, PATH_TIER2A, PATH_TIER2B, PATH_UNASSIGNED)


def format_evidence(result: RetrievalResult) -> str:
    """Render the per-path results as one labelled block for the prompt.

    Returns "" when nothing was retrieved, so `PromptBuilder.build()`
    appends nothing at all rather than an empty "[Evidence]" header --
    an empty header would still be extra tokens appended every turn for
    no content.
    """
    sections: list[str] = []
    for path in _RENDER_ORDER:
        chunks = result.by_path.get(path) or []
        if not chunks:
            continue
        lines = [f"-- {_PATH_LABELS[path]} --"]
        for chunk in chunks:
            lines.append(f"[{chunk.source_path} #{chunk.chunk_index}] {chunk.text}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)
