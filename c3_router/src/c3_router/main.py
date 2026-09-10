"""C3: the interjection gate. Budget, pending queue, etiquette, merge.

C3 IS NOW IN THE D0 PATH. It is started by `ops/run_d0.sh` and called by
C5 after each completed utterance. (It was previously a stub that returned
"speak_now" unconditionally and was not started at all -- the thread-1.0.6
ruling that D0 is C1 -> C5 -> C2 -> C4 only is superseded by this thread's
build, and the old `/decide` endpoint is gone with it.)

WHAT C3 DOES AND DOES NOT DO. C3 is a CHEAP, DETERMINISTIC POLICY
COMPONENT. NO MODEL RUNS IN C3. It asks C2 for a judgement under the
DR-043 `conflict_check` intent, and then applies arithmetic: is there
budget (DR-042(a)), is there an opportunity (DR-006), what is outstanding
(DR-042(b)), what has gone stale. `policy.py` holds that arithmetic;
`conflict.py` in C2 records why the judgement lives there.

THE FLOW, per Task 5(a)-(f):

  1. C5 calls POST /observe after each completed utterance, with the
     rolling transcript.
  2. C3 asks C2 for a conflict_check. C2 retrieves over the UNIFIED corpus
     (DR-043(c)) and returns either a structured candidate or an explicit
     no-conflict.
  3. A candidate goes to the PENDING QUEUE. It is NOT spoken on arrival.
  4. The hand-up is raised (DR-006).
  5. When an opportunity arrives -- a VAD gap or an invitation -- and the
     budget allows, ALL queued candidates are merged into ONE utterance.
  6. Candidates that never get an opportunity EXPIRE.

AN HONEST LIMIT ON DR-006's LATENCY MITIGATION AT D0, recorded here rather
than left for a reader to discover. DR-006 makes the hand-up load-bearing
because "C2 runs in the background while the humans finish their sentence"
-- the wait is what buys back the latency. At D0 the C5 loop is strictly
SEQUENTIAL and prompt-driven ("--- turn N: SPEAK NOW ---"), so there is no
concurrent conversation for C2's work to hide behind: /observe blocks C5
until C2 answers. What is built here is the correct STRUCTURE -- queue,
hand-up, deferred speaking, batching -- and that structure is what makes
the mitigation possible. The mitigation itself is only REALISED when the
loop becomes concurrent (C1 capturing the next utterance while C3/C2 work
on the last). That is a C5 change, not a C3 one, and it is carried in
BACKLOG.md. Do not read this module as evidence that DR-006's latency
saving has been obtained; read it as the gate DR-006 needs in order to
obtain it.
"""
from __future__ import annotations

import time
import uuid

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from .config import Config
from .logging_util import log_event
from .policy import Budget, Candidate, PendingQueue, merge

config = Config()
app = FastAPI()

budget = Budget(config.MAX_INTERJECTIONS, config.BUDGET_WINDOW_S)
queue = PendingQueue(ttl_s=config.CANDIDATE_TTL_S, max_queue=config.MAX_QUEUE)


class _HandUp:
    """DR-006's hand-up signal.

    THE LIGHT IS A STUB. There is no GPIO at D0; raising the hand emits a
    structured log event carrying `gpio_stub: true` and nothing physical
    happens. Stated explicitly because DR-006 classifies the signal as the
    PRIMARY latency mitigation rather than a UX nicety -- a reader must not
    assume a light exists in the room. Wiring real GPIO is carried in
    BACKLOG.md.
    """

    raised = False
    raised_at: float | None = None


ACTION_SILENT = "silent"
ACTION_HAND_UP = "hand_up"
ACTION_SPEAK = "speak"


class ObserveRequest(BaseModel):
    turn_id: str
    # The utterance that just completed -- the line to check.
    utterance: str
    # Rolling transcript for context. C5 sends it; C3 windows it.
    transcript: str = ""
    # Silence observed since the utterance ended, as measured by the
    # caller (C1's endpointer is the only thing that actually knows). C3
    # does not measure it: a policy component that times its own inputs
    # cannot be tested at a boundary.
    gap_s: float = 0.0
    # A human explicitly invited Jester to speak. DR-006: "wait for
    # invitation OR a natural gap" -- an invitation IS the opportunity, so
    # it bypasses the hand-up wait but NEVER the budget.
    invited: bool = False
    # Test-only monotonic override. Production callers omit it.
    now: float | None = None


class ObserveResponse(BaseModel):
    turn_id: str
    action: str
    text: str | None = None
    candidates_spoken: int = 0
    queue_depth: int = 0
    budget_used: int = 0
    budget_remaining: int = 0
    hand_up: bool = False
    reason: str = ""


def _window(transcript: str) -> str:
    if len(transcript) <= config.TRANSCRIPT_WINDOW_CHARS:
        return transcript
    return transcript[-config.TRANSCRIPT_WINDOW_CHARS:]


def _ask_c2(req: ObserveRequest) -> dict:
    """Ask C2 for a conflict_check. HTTP, per project-structure discipline.

    A C2 failure is logged and treated as NO CONFLICT rather than raised.
    C3 sits in C5's turn loop, and DR-039 established the principle
    directly: a failure in an advisory path must degrade one turn, never
    terminate the meeting. Silence on error is also the safe direction --
    it cannot produce a spurious interjection.
    """
    try:
        with httpx.Client() as client:
            response = client.post(
                f"{config.c2_base_url}/conflict_check",
                json={
                    "turn_id": req.turn_id,
                    "utterance": req.utterance,
                    "transcript": _window(req.transcript),
                    "corpus_id": config.CORPUS_ID,
                },
                timeout=config.CONFLICT_CHECK_TIMEOUT_S,
            )
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        log_event("C3", "conflict_check_failed", req.turn_id,
                  error=f"{type(exc).__name__}: {exc}")
        return {"conflict": False, "rejected_reason": "c2 call failed"}


@app.post("/observe", response_model=ObserveResponse)
def observe(req: ObserveRequest) -> ObserveResponse:
    now = req.now if req.now is not None else time.monotonic()
    turn_id = req.turn_id

    # --- staleness sweep first (Task 5(f)) ----------------------------
    # Before anything else, so an expired candidate can never be merged
    # into an interjection later in this same call.
    for expired in queue.expire(now):
        log_event("C3", "candidate_expired", expired.turn_id,
                  age_s=round(now - expired.raised_at, 3),
                  ttl_s=config.CANDIDATE_TTL_S,
                  **expired.log_fields())

    # --- ask C2 for a judgement (DR-043(e)(i)) -------------------------
    log_event("C3", "conflict_check_requested", turn_id, utterance=req.utterance)
    verdict = _ask_c2(req)

    raised_now = False
    if verdict.get("conflict"):
        candidate = Candidate(
            utterance=verdict.get("utterance") or req.utterance,
            conflicts_with=verdict.get("conflicts_with") or "",
            source=verdict.get("source") or "",
            authority=verdict.get("authority") or "unlabelled",
            authority_phrase=_authority_phrase(verdict.get("authority")),
            turn_id=turn_id,
            raised_at=now,
            candidate_id=str(uuid.uuid4()),
        )
        evicted = queue.add(candidate)
        raised_now = True
        # DR-045: `raised` and `queued` are the first two lifecycle events.
        log_event("C3", "candidate_raised", turn_id,
                  retrieved_chunks=verdict.get("retrieved_chunks", 0),
                  unified_corpus=verdict.get("unified_corpus", False),
                  **candidate.log_fields())
        log_event("C3", "candidate_queued", turn_id,
                  candidate_id=candidate.candidate_id, queue_depth=len(queue))
        if evicted is not None:
            log_event("C3", "candidate_dropped_queue_full", evicted.turn_id,
                      max_queue=config.MAX_QUEUE, **evicted.log_fields())
        if not _HandUp.raised:
            _HandUp.raised = True
            _HandUp.raised_at = now
            # DR-006's signal. STUBBED: no GPIO at D0.
            log_event("C3", "hand_up_raised", turn_id,
                      candidate_id=candidate.candidate_id,
                      gpio_stub=not config.HAND_UP_GPIO_ENABLED)
    else:
        log_event("C3", "no_conflict", turn_id,
                  rejected_reason=verdict.get("rejected_reason", ""),
                  retrieved_chunks=verdict.get("retrieved_chunks", 0))

    return _decide(req, now, raised_now)


def _decide(req: ObserveRequest, now: float, raised_now: bool) -> ObserveResponse:
    turn_id = req.turn_id

    def _respond(action: str, reason: str, text=None, spoken=0) -> ObserveResponse:
        return ObserveResponse(
            turn_id=turn_id, action=action, text=text,
            candidates_spoken=spoken, queue_depth=len(queue),
            budget_used=budget.used(now), budget_remaining=budget.remaining(now),
            hand_up=_HandUp.raised, reason=reason,
        )

    if not len(queue):
        return _respond(ACTION_SILENT, "nothing queued")

    # --- DR-006: is there an opportunity? ------------------------------
    # An invitation IS the opportunity and bypasses the wait. A natural gap
    # counts only once the hand has been up since a PREVIOUS observation --
    # DR-006's hand-up is load-bearing and must not be optimised away, so a
    # candidate raised in this very call does not also get spoken in it.
    if req.invited:
        opportunity, why = True, "invited"
    elif req.gap_s >= config.VAD_GAP_S and (
        not raised_now or config.SPEAK_ON_SAME_OBSERVATION
    ):
        opportunity, why = True, f"vad_gap {req.gap_s:.2f}s >= {config.VAD_GAP_S}s"
    elif req.gap_s >= config.VAD_GAP_S:
        opportunity, why = False, "hand just raised; waiting per DR-006"
    else:
        opportunity, why = False, f"no gap ({req.gap_s:.2f}s < {config.VAD_GAP_S}s)"

    if not opportunity:
        log_event("C3", "opportunity_declined", turn_id,
                  reason=why, queue_depth=len(queue), gap_s=req.gap_s)
        return _respond(ACTION_HAND_UP if _HandUp.raised else ACTION_SILENT, why)

    # --- DR-042(a): the hard ceiling -----------------------------------
    # Checked AFTER the opportunity so the logs distinguish "no chance to
    # speak" from "had a chance and the ceiling refused it". DR-045's
    # scoring needs that difference: suppressed-by-budget is evidence
    # about the constant, declined-opportunity is not.
    if not budget.allows(now):
        for item in queue.items:
            log_event("C3", "candidate_suppressed_by_budget", item.turn_id,
                      max_interjections=config.MAX_INTERJECTIONS,
                      window_s=config.BUDGET_WINDOW_S,
                      next_free_in_s=round((budget.next_free_at(now) or now) - now, 3),
                      **item.log_fields())
        return _respond(ACTION_HAND_UP, "budget exhausted (DR-042(a))")

    # --- DR-042(b): ALL outstanding candidates, ONE interjection --------
    batch = queue.drain()
    text = merge(batch)
    budget.record(now)
    _HandUp.raised = False

    log_event("C3", "candidates_merged", turn_id,
              candidate_count=len(batch),
              candidate_ids=[c.candidate_id for c in batch],
              batched=len(batch) > 1)
    log_event("C3", "interjection_spoken", turn_id,
              candidate_count=len(batch),
              candidates=[c.as_dict() for c in batch],
              text=text, opportunity=why,
              budget_used=budget.used(now),
              budget_remaining=budget.remaining(now))
    log_event("C3", "hand_up_lowered", turn_id)

    return _respond(ACTION_SPEAK, why, text=text, spoken=len(batch))


_AUTHORITY_PHRASES = {
    "binding": "binding company policy",
    "advisory": "an advisory standard",
    "unlabelled": "a source whose authority is not yet labelled",
}


def _authority_phrase(authority: str | None) -> str:
    return _AUTHORITY_PHRASES.get(authority or "", _AUTHORITY_PHRASES["unlabelled"])


@app.get("/state")
def state() -> dict:
    """Read-only introspection, for the smoke test and for a human
    wondering why Jester has not spoken."""
    now = time.monotonic()
    return {
        "queue_depth": len(queue),
        "budget_used": budget.used(now),
        "budget_remaining": budget.remaining(now),
        "hand_up": _HandUp.raised,
        "max_interjections": config.MAX_INTERJECTIONS,
        "window_s": config.BUDGET_WINDOW_S,
        "candidate_ttl_s": config.CANDIDATE_TTL_S,
        "vad_gap_s": config.VAD_GAP_S,
    }


def run():
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    run()
