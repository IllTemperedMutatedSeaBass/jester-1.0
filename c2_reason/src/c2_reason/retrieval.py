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

DR-043 -- THE TIER PARTITION IS REMOVED AS A CONTROL ON TRIGGER AUTHORITY.
Everything above still describes the `question_answering` intent exactly as
DR-035 built it, and that path is UNCHANGED. DR-043 adds a second intent,
`conflict_check`, for the C3 trigger path, and it is different in one
specific way: it queries ALL FOUR collections unconditionally and lets any
of them contribute a candidate. There is no Tier-1-must-fire-first
condition on it.

Why that is not simply a reversal of DR-008: DR-008's measured finding was
about RETRIEVAL-AS-TRIGGER -- a cosine threshold standing in for a
judgement, which in 2.x flipped 4 of 6 correctly-Absent records because a
nearest-neighbour chunk always exists. Under DR-043 retrieval no longer
decides anything on this path. It ASSEMBLES EVIDENCE; a reasoning gate at
C2 decides whether a real contradiction exists, and DR-042's rate ceiling
is the hard backstop. DR-043(e) records honestly that this swap is an
argument and not a measurement, and that DR-045's scored run is the first
evidence either way.

The collections are still separate and results are still kept per-path,
because DR-043(d) needs the tier: authority weight is DERIVED FROM IT at
read time (see `AUTHORITY_BY_PATH`). "One corpus" in DR-043(c) means one
query set with no tier-based trigger gate -- it does not mean one blended
index, and no re-ingest happens here.

DR-043(d) HONESTY NOTE, mirrored from the DR so the code is readable
without it: chunks do NOT carry a licence flag today. `ingest/run.py`
writes `source_path`, `tier`, `tier_evidence`, `chunk_index`,
`embedding_model`, `embedding_model_digest` and nothing else. Authority is
derived from `tier`; licence is NOT derivable and needs a re-ingest, which
is carried in `BACKLOG.md`. Do not read `AUTHORITY_BY_PATH` as evidence
that the licence half of DR-043(d) is built. It is not.
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

# DR-035's question-answering intent: a human asked, Jester answers.
INTENT_QUESTION_ANSWERING = "question_answering"

# DR-043(f)'s trigger-side intent: Jester decided on its own to look.
# A NEW NAME rather than reusing `question_answering` -- recorded in DR-043
# as a PREFERENCE, not a necessity. Reusing the existing intent would work
# mechanically; the reason not to is that DR-045's scoring must be able to
# tell "a human asked and Jester answered" from "Jester decided on its own
# to look", and one shared intent name makes those indistinguishable in
# exactly the logs that become the evaluation set.
INTENT_CONFLICT_CHECK = "conflict_check"

SUPPORTED_INTENTS = (INTENT_QUESTION_ANSWERING, INTENT_CONFLICT_CHECK)

PATH_TIER1 = "tier1"
PATH_UNASSIGNED = "unassigned"
PATH_TIER2A = "tier2a"
PATH_TIER2B = "tier2b"

# DR-043(d) AUTHORITY, DERIVED FROM TIER AT READ TIME. "A company policy
# binds; a standard is advisory" -- and this is a property Jester STATES
# WHEN IT SPEAKS (DR-044 requires every flag to name the authority of what
# it conflicts with), never a gate on whether it may notice.
#
# Derived rather than stored because DR-031 already made `tier` a
# per-document PROVENANCE/AUTHORITY judgement -- "is this an instrument of
# THIS COMPANY'S OWN governance, or does it carry general legal/normative
# force without being company-specific" -- so authority is precisely what
# the tier field was standing in for. Deriving it needs no re-ingest.
#
# UNASSIGNED is "unlabelled", NOT "advisory": DR-034 left 41 of 46
# documents unassigned, and calling those advisory would be asserting a
# judgement nobody made. DR-043(g) keeps re-tiering on the backlog for
# exactly this reason -- the skew stopped being a C3 blocker, it did not
# stop mattering.
AUTHORITY_BINDING = "binding"
AUTHORITY_ADVISORY = "advisory"
AUTHORITY_UNLABELLED = "unlabelled"

AUTHORITY_BY_PATH = {
    PATH_TIER1: AUTHORITY_BINDING,
    PATH_TIER2A: AUTHORITY_ADVISORY,
    PATH_TIER2B: AUTHORITY_ADVISORY,
    PATH_UNASSIGNED: AUTHORITY_UNLABELLED,
}

# Spoken-language rendering of the above, for DR-044's "name the authority
# of that source" requirement. C4 speaks these, so they are phrases a
# person would say, not enum values.
AUTHORITY_PHRASE = {
    AUTHORITY_BINDING: "binding company policy",
    AUTHORITY_ADVISORY: "an advisory standard",
    AUTHORITY_UNLABELLED: "a source whose authority is not yet labelled",
}


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
    # True when this result came from DR-043(c)'s unified-corpus trigger
    # path. Logged, so a scored run (DR-045) can tell which retrieval
    # regime produced a candidate without inferring it from the intent.
    unified_corpus: bool = False

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
        if request.intent not in SUPPORTED_INTENTS:
            # Still fails loudly on an unknown intent (DR-020). DR-043(f)
            # widens WHICH intents are accepted; it does not remove the
            # refusal. A typo'd intent must not quietly retrieve nothing
            # and read as "no conflict found".
            raise UnsupportedModeError(
                f"intent {request.intent!r} is not implemented "
                f"(supported: {list(SUPPORTED_INTENTS)})."
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

        if request.intent == INTENT_CONFLICT_CHECK:
            # DR-043(c) -- ONE CORPUS FOR TRIGGER EVALUATION.
            #
            # All four collections are queried unconditionally. There is no
            # "Tier 1 must fire first" precondition, because that
            # precondition IS the partition DR-043 removes: it is what makes
            # a conflict BETWEEN a company instrument and an external
            # obligation unreachable (DR-043(b) -- the insight lives in the
            # join between documents).
            #
            # Note what has NOT changed: four separate collections, four
            # separate queries, results kept per-path. DR-043(c) removes a
            # TRIGGER GATE, not the separation -- the tier is still needed
            # on every chunk to derive authority for DR-044's spoken
            # citation.
            for path in (PATH_TIER1, PATH_TIER2A, PATH_TIER2B, PATH_UNASSIGNED):
                result.by_path[path] = self._query_path(
                    query_vector, path, request.top_k
                )
            # Recorded as consulted-unconditionally rather than left False:
            # on this path `tier2_consulted` no longer means "Tier 1 flagged
            # something first", and a reader of the logs must not be able to
            # mistake it for that.
            result.tier2_consulted = True
            result.unified_corpus = True
            result.query_s = time.monotonic() - query_start
            return result

        # ---- DR-035's question-answering path, UNCHANGED by DR-043 -------
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
