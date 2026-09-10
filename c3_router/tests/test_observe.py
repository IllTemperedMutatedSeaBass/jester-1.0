"""End-to-end tests of C3's /observe gate with C2 stubbed out.

C2 is stubbed because C3's contract is that NO MODEL RUNS IN C3: every
decision /observe makes is arithmetic over the verdict it was handed. That
property is only actually asserted if the verdict is controlled by the
test.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from fastapi.testclient import TestClient

from c3_router import main


@pytest.fixture(autouse=True)
def reset_state():
    """C3 holds budget/queue/hand-up at process level, matching C2's own
    process-level prompt builder -- one process serves one meeting."""
    main.budget = main.Budget(main.config.MAX_INTERJECTIONS, main.config.BUDGET_WINDOW_S)
    main.queue = main.PendingQueue(
        ttl_s=main.config.CANDIDATE_TTL_S, max_queue=main.config.MAX_QUEUE
    )
    main._HandUp.raised = False
    main._HandUp.raised_at = None
    yield


def _stub_c2(monkeypatch, verdicts):
    """`verdicts` is a list consumed one per /observe call."""
    calls = iter(verdicts)

    def _fake(req):
        return next(calls)

    monkeypatch.setattr(main, "_ask_c2", _fake)


def _conflict(n=1, authority="binding"):
    return {
        "conflict": True,
        "utterance": f"utterance {n}",
        "conflicts_with": f"that contradicts finding {n}",
        "source": f"docs/source{n}.pptx",
        "authority": authority,
        "retrieved_chunks": 3,
        "unified_corpus": True,
    }


NO_CONFLICT = {"conflict": False, "retrieved_chunks": 3, "rejected_reason": ""}


def _observe(client, n, **kwargs):
    body = {"turn_id": f"turn-{n}", "utterance": f"utterance {n}"}
    body.update(kwargs)
    return client.post("/observe", json=body).json()


def test_no_conflict_stays_silent_and_queues_nothing(monkeypatch):
    _stub_c2(monkeypatch, [NO_CONFLICT])
    with TestClient(main.app) as client:
        result = _observe(client, 1, gap_s=5.0, now=0.0)
    assert result["action"] == "silent"
    assert result["queue_depth"] == 0
    assert result["hand_up"] is False


def test_a_candidate_is_queued_and_the_hand_goes_up_but_it_is_not_spoken(monkeypatch):
    """DR-042(b): candidates are NOT spoken on arrival. DR-006: the hand-up
    is load-bearing and is not optimised away -- even with a gap present,
    a candidate raised in this call waits."""
    _stub_c2(monkeypatch, [_conflict(1)])
    with TestClient(main.app) as client:
        result = _observe(client, 1, gap_s=5.0, now=0.0)
    assert result["action"] == "hand_up"
    assert result["candidates_spoken"] == 0
    assert result["queue_depth"] == 1
    assert result["hand_up"] is True


def test_two_queued_candidates_produce_one_interjection_not_two(monkeypatch):
    """Task 5(d), asserted through the real endpoint: two candidates
    arrive on separate turns, and the next opportunity yields ONE
    interjection carrying BOTH -- costing ONE budget slot."""
    _stub_c2(monkeypatch, [_conflict(1), _conflict(2), NO_CONFLICT])
    with TestClient(main.app) as client:
        first = _observe(client, 1, gap_s=0.0, now=0.0)
        second = _observe(client, 2, gap_s=0.0, now=10.0)
        assert first["queue_depth"] == 1 and second["queue_depth"] == 2
        # A gap arrives on a turn that raises nothing new.
        spoken = _observe(client, 3, gap_s=5.0, now=20.0)

    assert spoken["action"] == "speak"
    assert spoken["candidates_spoken"] == 2
    assert spoken["queue_depth"] == 0
    assert spoken["text"].count("contradicts finding") == 2
    # ONE interjection -> ONE slot spent, not two.
    assert spoken["budget_used"] == 1
    assert spoken["budget_remaining"] == 1
    assert spoken["hand_up"] is False


def test_budget_suppresses_a_third_interjection_in_the_window(monkeypatch):
    """DR-042(a) enforced in C3, through the endpoint."""
    _stub_c2(monkeypatch, [
        _conflict(1), NO_CONFLICT, _conflict(2), NO_CONFLICT, _conflict(3), NO_CONFLICT,
    ])
    with TestClient(main.app) as client:
        _observe(client, 1, gap_s=0.0, now=0.0)
        first = _observe(client, 2, gap_s=5.0, now=10.0)
        _observe(client, 3, gap_s=0.0, now=20.0)
        second = _observe(client, 4, gap_s=5.0, now=30.0)
        _observe(client, 5, gap_s=0.0, now=40.0)
        third = _observe(client, 6, gap_s=5.0, now=50.0)

    assert first["action"] == "speak" and second["action"] == "speak"
    # Third has an opportunity AND a queued candidate, and is refused.
    assert third["action"] == "hand_up"
    assert third["candidates_spoken"] == 0
    assert third["queue_depth"] == 1
    assert "budget exhausted" in third["reason"]


def test_the_ceiling_lifts_once_the_window_rolls(monkeypatch):
    """The third candidate is raised LATE (t=600), not early, so this test
    isolates the budget window from the staleness rule. An earlier draft
    raised it at t=4 and it expired at its 300 s TTL long before the window
    rolled -- which was the staleness rule working correctly, not the
    ceiling failing, but it meant the test asserted nothing about the
    ceiling."""
    _stub_c2(monkeypatch, [
        _conflict(1), NO_CONFLICT, _conflict(2), NO_CONFLICT, _conflict(3), NO_CONFLICT,
    ])
    with TestClient(main.app) as client:
        _observe(client, 1, gap_s=0.0, now=0.0)
        first = _observe(client, 2, gap_s=5.0, now=1.0)
        _observe(client, 3, gap_s=0.0, now=2.0)
        second = _observe(client, 4, gap_s=5.0, now=3.0)
        # Budget is now spent: two interjections at t=1 and t=3.
        assert first["action"] == "speak" and second["action"] == "speak"
        _observe(client, 5, gap_s=0.0, now=600.0)
        # t=601 is past the 600 s window from the t=1 interjection.
        after = _observe(client, 6, gap_s=5.0, now=601.0)
    assert after["action"] == "speak"
    assert after["candidates_spoken"] == 1


def test_no_gap_means_no_opportunity_and_the_hand_stays_up(monkeypatch):
    _stub_c2(monkeypatch, [_conflict(1), NO_CONFLICT])
    with TestClient(main.app) as client:
        _observe(client, 1, gap_s=0.0, now=0.0)
        result = _observe(client, 2, gap_s=0.1, now=10.0)
    assert result["action"] == "hand_up"
    assert result["queue_depth"] == 1
    assert "no gap" in result["reason"]


def test_an_invitation_is_an_opportunity_even_with_no_gap(monkeypatch):
    """DR-006: 'wait for invitation OR a natural gap'. An invitation IS the
    opportunity, so it bypasses the hand-up wait -- but never the budget."""
    _stub_c2(monkeypatch, [_conflict(1)])
    with TestClient(main.app) as client:
        result = _observe(client, 1, gap_s=0.0, invited=True, now=0.0)
    assert result["action"] == "speak"
    assert result["candidates_spoken"] == 1
    assert result["reason"] == "invited"


def test_an_invitation_does_not_bypass_the_budget(monkeypatch):
    """The ceiling is HARD. Being asked to speak does not create budget."""
    _stub_c2(monkeypatch, [_conflict(1), _conflict(2), _conflict(3)])
    with TestClient(main.app) as client:
        _observe(client, 1, invited=True, now=0.0)
        _observe(client, 2, invited=True, now=10.0)
        third = _observe(client, 3, invited=True, now=20.0)
    assert third["action"] == "hand_up"
    assert third["candidates_spoken"] == 0
    assert "budget exhausted" in third["reason"]


def test_a_stale_candidate_expires_instead_of_surfacing_late(monkeypatch):
    """Task 5(f), through the endpoint: a candidate that never got an
    opportunity is gone by the time one arrives."""
    _stub_c2(monkeypatch, [_conflict(1), NO_CONFLICT])
    with TestClient(main.app) as client:
        _observe(client, 1, gap_s=0.0, now=0.0)
        # A gap arrives, but only past the 300 s TTL.
        late = _observe(client, 2, gap_s=5.0, now=400.0)
    assert late["action"] == "silent"
    assert late["candidates_spoken"] == 0
    assert late["queue_depth"] == 0
    assert late["reason"] == "nothing queued"
    # Nothing was spoken, so no budget was spent on stale material.
    assert late["budget_used"] == 0


def test_a_c2_failure_degrades_to_silence_rather_than_raising(monkeypatch):
    """DR-039's principle: a failure in an advisory path degrades one turn,
    it never terminates the meeting. Silence is also the safe direction."""
    def _boom(req):
        raise RuntimeError("C2 is down")
    monkeypatch.setattr(main, "_ask_c2", main._ask_c2)
    monkeypatch.setattr(main.httpx, "Client", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("C2 is down")))
    with TestClient(main.app) as client:
        result = _observe(client, 1, gap_s=5.0, now=0.0)
    assert result["action"] == "silent"
    assert result["queue_depth"] == 0


def test_state_endpoint_reports_the_live_policy_constants():
    with TestClient(main.app) as client:
        state = client.get("/state").json()
    assert state["max_interjections"] == 2
    assert state["window_s"] == 600.0
    assert state["candidate_ttl_s"] == 300.0
