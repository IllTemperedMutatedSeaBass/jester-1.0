"""C3 policy tests: DR-042's ceiling and batching rule, DR-006's etiquette,
and Task 5(f)'s staleness expiry.

Time is INJECTED throughout (`now=`), never taken from the clock. A rolling
ten-minute window tested against the real clock is either a slow test or a
flaky one, and the ceiling is exactly the kind of rule whose boundary must
be asserted exactly -- at 600.0 s, not "about ten minutes".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from c3_router.policy import Budget, Candidate, PendingQueue, merge


def _candidate(n: int = 1, raised_at: float = 0.0, authority: str = "binding",
               phrase: str = "binding company policy") -> Candidate:
    return Candidate(
        utterance=f"utterance {n}",
        conflicts_with=f"that contradicts finding {n}",
        source=f"docs/source{n}.pptx",
        authority=authority,
        authority_phrase=phrase,
        turn_id=f"turn-{n}",
        raised_at=raised_at,
        candidate_id=f"cand-{n}",
    )


# --------------------------- DR-042(a): the ceiling -----------------------

def test_budget_allows_exactly_two_interjections_then_refuses():
    budget = Budget(max_interjections=2, window_s=600.0)
    assert budget.allows(now=0.0)
    budget.record(now=0.0)
    assert budget.allows(now=10.0)
    budget.record(now=10.0)
    # Third inside the window is refused. This is the hard ceiling.
    assert not budget.allows(now=20.0)
    assert budget.remaining(now=20.0) == 0


def test_budget_window_rolls_at_the_exact_boundary():
    """The boundary is asserted exactly, not approximately: an interjection
    at t=0 has left a 600 s window at t=600.0, and has not at t=599.9."""
    budget = Budget(max_interjections=2, window_s=600.0)
    budget.record(now=0.0)
    budget.record(now=1.0)
    assert not budget.allows(now=599.9)
    # At exactly 600.0 the t=0 interjection is outside the window.
    assert budget.allows(now=600.0)
    assert budget.used(now=600.0) == 1


def test_a_merged_interjection_costs_one_budget_slot_not_one_per_candidate():
    """DR-042(b) is only coherent if batching is cheaper than not batching.
    If three merged candidates cost three slots, the rule is pointless."""
    budget = Budget(max_interjections=2, window_s=600.0)
    queue = PendingQueue(ttl_s=300.0, max_queue=16)
    for n in (1, 2, 3):
        queue.add(_candidate(n, raised_at=0.0))
    batch = queue.drain()
    assert len(batch) == 3
    budget.record(now=0.0)
    assert budget.used(now=0.0) == 1
    assert budget.remaining(now=0.0) == 1


def test_next_free_at_reports_when_the_ceiling_lifts():
    budget = Budget(max_interjections=2, window_s=600.0)
    budget.record(now=100.0)
    budget.record(now=200.0)
    assert budget.next_free_at(now=250.0) == 700.0
    budget.record(now=0.0)  # ignored: pruned, outside nothing yet
    assert budget.next_free_at(now=800.0) is None


# --------------------------- DR-042(b): batching --------------------------

def test_two_queued_candidates_produce_one_interjection_not_two():
    """The rule Task 5(d) names explicitly. `drain` is all-or-nothing --
    there is deliberately no take(n) -- so a partial batch is not
    expressible."""
    queue = PendingQueue(ttl_s=300.0, max_queue=16)
    queue.add(_candidate(1, raised_at=0.0))
    queue.add(_candidate(2, raised_at=1.0))
    assert len(queue) == 2

    batch = queue.drain()
    assert len(batch) == 2
    assert len(queue) == 0

    text = merge(batch)
    # ONE utterance carrying BOTH points.
    assert text.count("contradicts finding") == 2
    assert text.startswith("2 things before you move on:")
    assert "1." in text and "2." in text


def test_merge_of_one_candidate_does_not_announce_a_count():
    text = merge([_candidate(1, raised_at=0.0)])
    assert text.startswith("One thing before you move on:")
    # No numbered-list prefix. Checked as ": 1. " rather than "1." because
    # a source filename legitimately contains "1." (source1.pptx).
    assert ": 1. " not in text


def test_merge_states_the_conflict_and_stops_proposing_nothing():
    """DR-044: name what was said, what it conflicts with, and the
    authority of that source -- then STOP."""
    text = merge([_candidate(1, raised_at=0.0)])
    assert "that contradicts finding 1" in text
    assert "source1.pptx" in text
    assert "binding company policy" in text
    # No resolution language. A resolution may only be given if a human
    # asks, which is the existing question-answering path.
    for proposing in ("you should", "I suggest", "I recommend", "instead"):
        assert proposing.lower() not in text.lower()


def test_merge_renders_the_citation_as_prose_never_as_a_bracket_marker():
    """Coupled to C4's text filter, which now strips `[...]` markers. A
    bracketed citation here would be silently deleted on its way to the
    speaker -- removing the citation DR-044 exists to require."""
    text = merge([_candidate(1, raised_at=0.0), _candidate(2, raised_at=0.0)])
    assert "[" not in text and "]" not in text
    assert "per source1.pptx" in text


def test_merge_names_the_authority_of_each_source_separately():
    """DR-043(d): every flag must name the authority weight of what it
    conflicts with, and two candidates can carry different weights."""
    binding = _candidate(1, raised_at=0.0)
    advisory = _candidate(2, raised_at=0.0, authority="advisory",
                          phrase="an advisory standard")
    text = merge([binding, advisory])
    assert "binding company policy" in text
    assert "an advisory standard" in text


def test_merge_of_nothing_is_empty():
    assert merge([]) == ""


# --------------------------- Task 5(f): staleness -------------------------

def test_a_candidate_past_its_ttl_expires_rather_than_surfacing_late():
    queue = PendingQueue(ttl_s=300.0, max_queue=16)
    queue.add(_candidate(1, raised_at=0.0))
    # Still alive just inside the TTL.
    assert queue.expire(now=300.0) == []
    assert len(queue) == 1
    # Past it, the candidate is expired and RETURNED so it can be logged.
    expired = queue.expire(now=300.1)
    assert len(expired) == 1
    assert expired[0].candidate_id == "cand-1"
    assert len(queue) == 0


def test_expiry_is_per_candidate_not_whole_queue():
    queue = PendingQueue(ttl_s=300.0, max_queue=16)
    queue.add(_candidate(1, raised_at=0.0))
    queue.add(_candidate(2, raised_at=250.0))
    expired = queue.expire(now=400.0)
    assert [c.candidate_id for c in expired] == ["cand-1"]
    assert [c.candidate_id for c in queue.items] == ["cand-2"]


def test_an_expired_candidate_can_never_be_merged():
    """The reason the sweep runs FIRST in `observe`."""
    queue = PendingQueue(ttl_s=300.0, max_queue=16)
    queue.add(_candidate(1, raised_at=0.0))
    queue.add(_candidate(2, raised_at=350.0))
    queue.expire(now=400.0)
    text = merge(queue.drain())
    assert "finding 1" not in text
    assert "finding 2" in text


def test_queue_overflow_drops_the_oldest_and_returns_it_for_logging():
    queue = PendingQueue(ttl_s=300.0, max_queue=2)
    assert queue.add(_candidate(1, raised_at=0.0)) is None
    assert queue.add(_candidate(2, raised_at=0.0)) is None
    evicted = queue.add(_candidate(3, raised_at=0.0))
    assert evicted is not None and evicted.candidate_id == "cand-1"
    assert len(queue) == 2
