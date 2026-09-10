"""Non-interactive smoke test for C3, the interjection gate (thread 1.0.16).

Proves the gate, queue, budget, batching and expiry work WITHOUT the
headset and without a human, which is Task 7's precondition before the
spoken run is handed over. C1 blocks on real audio, so C1 and C5's turn
loop are deliberately not driven here.

TWO PARTS, and the split is the point:

  PART A -- POLICY, against a STUBBED C2. C3's contract is that NO MODEL
      RUNS IN C3: every decision is arithmetic over the verdict it is
      handed. Stubbing C2 is what actually asserts that -- with a live
      model the budget/batching/expiry assertions would depend on whether
      the model happened to find a conflict, which is not a test of the
      policy. Time is injected, so the rolling-window and TTL boundaries
      are exact rather than approximate.

  PART B -- THE LIVE PATH, against the REAL C2 and the REAL store. Proves
      the DR-043 `conflict_check` intent reaches the unified corpus, that
      C2 answers in the parseable form, and that the whole C3 -> C2 ->
      Chroma -> Ollama path is wired. It does NOT assert that a conflict IS
      found: whether this corpus contains a real contradiction is exactly
      the open question DR-045 says only a scored run can answer, and an
      assertion here would be asserting the answer.

Exit code 0 = all assertions held.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
C2_URL = f"http://{os.environ.get('C2_HOST','127.0.0.1')}:{os.environ.get('C2_PORT','8002')}"
C3_URL = f"http://{os.environ.get('C3_HOST','127.0.0.1')}:{os.environ.get('C3_PORT','8003')}"

failures: list[str] = []


def check(condition: bool, description: str) -> None:
    if condition:
        print(f"      PASS  {description}")
    else:
        print(f"      FAIL  {description}")
        failures.append(description)


# ----------------------------------------------------------------- PART A
def part_a() -> None:
    """Policy, in-process, C2 stubbed and time injected."""
    sys.path.insert(0, str(REPO / "c3_router" / "src"))
    from fastapi.testclient import TestClient
    from c3_router import main

    def fresh():
        main.budget = main.Budget(main.config.MAX_INTERJECTIONS,
                                  main.config.BUDGET_WINDOW_S)
        main.queue = main.PendingQueue(ttl_s=main.config.CANDIDATE_TTL_S,
                                       max_queue=main.config.MAX_QUEUE)
        main._HandUp.raised = False

    verdicts: list[dict] = []
    main._ask_c2 = lambda req: verdicts.pop(0)

    def conflict(n):
        return {"conflict": True, "utterance": f"utterance {n}",
                "conflicts_with": f"that contradicts finding {n}",
                "source": f"docs/source{n}.pptx", "authority": "binding",
                "retrieved_chunks": 3, "unified_corpus": True}

    none = {"conflict": False, "retrieved_chunks": 3}

    def observe(client, n, **kw):
        body = {"turn_id": f"t{n}", "utterance": f"utterance {n}"}
        body.update(kw)
        return client.post("/observe", json=body).json()

    with TestClient(main.app) as client:
        print("\n[A1] GATE: a no-conflict verdict queues nothing and stays silent.")
        fresh(); verdicts[:] = [none]
        r = observe(client, 1, gap_s=5.0, now=0.0)
        check(r["action"] == "silent" and r["queue_depth"] == 0,
              "no-conflict -> silent, queue empty")

        print("\n[A2] QUEUE + ETIQUETTE: a candidate is queued, the hand goes")
        print("     up, and it is NOT spoken on arrival (DR-042(b), DR-006).")
        fresh(); verdicts[:] = [conflict(1)]
        r = observe(client, 1, gap_s=5.0, now=0.0)
        check(r["action"] == "hand_up", "candidate raised -> hand_up, not speak")
        check(r["queue_depth"] == 1, "candidate is queued")
        check(r["candidates_spoken"] == 0, "nothing spoken on arrival")
        check(r["hand_up"] is True, "hand-up raised (GPIO stubbed)")

        print("\n[A3] BATCHING: two queued candidates produce ONE interjection")
        print("     carrying both, costing ONE budget slot (DR-042(b)).")
        fresh(); verdicts[:] = [conflict(1), conflict(2), none]
        observe(client, 1, gap_s=0.0, now=0.0)
        observe(client, 2, gap_s=0.0, now=10.0)
        r = observe(client, 3, gap_s=5.0, now=20.0)
        check(r["action"] == "speak", "opportunity -> speak")
        check(r["candidates_spoken"] == 2, "BOTH candidates in one interjection")
        check(r["text"].count("contradicts finding") == 2,
              "one utterance carries both points")
        check(r["budget_used"] == 1, "ONE budget slot spent, not two")
        check("[" not in r["text"], "citation is prose, no bracket marker (DR-044)")

        print("\n[A4] BUDGET: a third interjection inside the window is refused")
        print("     (DR-042(a), hard ceiling).")
        fresh(); verdicts[:] = [conflict(1), none, conflict(2), none, conflict(3), none]
        observe(client, 1, gap_s=0.0, now=0.0)
        a = observe(client, 2, gap_s=5.0, now=10.0)
        observe(client, 3, gap_s=0.0, now=20.0)
        b = observe(client, 4, gap_s=5.0, now=30.0)
        observe(client, 5, gap_s=0.0, now=40.0)
        c = observe(client, 6, gap_s=5.0, now=50.0)
        check(a["action"] == "speak" and b["action"] == "speak",
              "first two interjections allowed")
        check(c["action"] == "hand_up" and c["candidates_spoken"] == 0,
              "third refused despite an opportunity and a queued candidate")
        check("budget exhausted" in c["reason"], "refusal names the budget")
        check(c["queue_depth"] == 1, "suppressed candidate stays queued")

        print("\n[A5] BUDGET ROLLS: the ceiling lifts past the window.")
        fresh(); verdicts[:] = [conflict(1), none, conflict(2), none, conflict(3), none]
        observe(client, 1, gap_s=0.0, now=0.0)
        observe(client, 2, gap_s=5.0, now=1.0)
        observe(client, 3, gap_s=0.0, now=2.0)
        observe(client, 4, gap_s=5.0, now=3.0)
        observe(client, 5, gap_s=0.0, now=600.0)
        r = observe(client, 6, gap_s=5.0, now=601.0)
        check(r["action"] == "speak", "past 600s the ceiling lifts")

        print("\n[A6] EXPIRY: a candidate that never got an opportunity expires")
        print("     rather than surfacing minutes late (Task 5(f)).")
        fresh(); verdicts[:] = [conflict(1), none]
        observe(client, 1, gap_s=0.0, now=0.0)
        r = observe(client, 2, gap_s=5.0, now=400.0)
        check(r["action"] == "silent" and r["queue_depth"] == 0,
              "stale candidate expired before the opportunity arrived")
        check(r["budget_used"] == 0, "no budget spent on stale material")

        print("\n[A7] INVITATION is an opportunity, but never bypasses budget.")
        fresh(); verdicts[:] = [conflict(1), conflict(2), conflict(3)]
        observe(client, 1, invited=True, now=0.0)
        observe(client, 2, invited=True, now=10.0)
        r = observe(client, 3, invited=True, now=20.0)
        check(r["action"] == "hand_up", "invitation does not create budget")


# ----------------------------------------------------------------- PART B
def _wait_healthy(url: str, proc: subprocess.Popen, name: str, timeout_s=90.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"{name} exited during startup, code {proc.returncode}")
        try:
            if httpx.get(f"{url}/docs", timeout=2.0).status_code == 200:
                return
        except Exception:
            time.sleep(0.5)
    raise SystemExit(f"{name} did not become healthy at {url}")


def part_b() -> None:
    print("\n[B] LIVE PATH: real C2, real store, real model.")
    log_dir = REPO / "logs" / "smoke_c3"
    log_dir.mkdir(parents=True, exist_ok=True)
    c2_log = (log_dir / "c2.jsonl").open("w")
    c3_log = (log_dir / "c3.jsonl").open("w")

    c2 = subprocess.Popen(
        [str(REPO / "c2_reason/.venv/bin/python"), "-m", "c2_reason.main"],
        stderr=c2_log, stdout=subprocess.DEVNULL)
    c3 = subprocess.Popen(
        [str(REPO / "c3_router/.venv/bin/python"), "-m", "c3_router.main"],
        stderr=c3_log, stdout=subprocess.DEVNULL)
    try:
        _wait_healthy(C2_URL, c2, "C2")
        _wait_healthy(C3_URL, c3, "C3")
        print("      C2 and C3 both healthy (a DR-033 digest mismatch or a bad")
        print("      store path would have killed C2 here, at startup).")

        turns = [
            "We'll approve the ERP phase two spend at this meeting without "
            "going back to the board.",
            "The programme director can sign off the whole capital amount "
            "on her own authority.",
            "Let's skip the risk register review this quarter.",
        ]
        with httpx.Client() as client:
            for i, text in enumerate(turns, 1):
                started = time.monotonic()
                response = client.post(
                    f"{C2_URL}/conflict_check",
                    json={"turn_id": str(uuid.uuid4()), "utterance": text,
                          "transcript": "\n".join(turns[:i - 1]),
                          "corpus_id": os.environ.get("C2_CORPUS_ID", "dhi")},
                    timeout=120.0)
                response.raise_for_status()
                body = response.json()
                elapsed = time.monotonic() - started
                verdict = "CONFLICT" if body["conflict"] else "no conflict"
                print(f"      turn {i}: {verdict}, {body['retrieved_chunks']} chunks, "
                      f"{elapsed:.2f}s"
                      + (f" -- {body['source']} ({body['authority']})"
                         if body["conflict"] else
                         (f" [{body['rejected_reason']}]"
                          if body.get("rejected_reason") else "")))
                check(body["unified_corpus"] is True or body["retrieved_chunks"] == 0,
                      f"turn {i}: retrieval ran over the UNIFIED corpus (DR-043(c))")
                if body["conflict"]:
                    check(bool(body["source"]) and bool(body["authority"]),
                          f"turn {i}: candidate names a source AND its authority")

        c2_log.flush()
        events = [json.loads(l) for l in (log_dir / "c2.jsonl").read_text().splitlines()
                  if l.startswith("{")]
        names = {e.get("event") for e in events}
        check("conflict_check_start" in names and "conflict_check_done" in names,
              "conflict_check emits its own stage events")
        check("retrieval_start" not in names,
              "conflict_check does NOT emit /respond's Bar B events "
              "(the sample stays exactly the turns C5 drove)")
        retrieved = [e for e in events if e.get("event") == "conflict_check_retrieved"]
        if retrieved:
            paths = retrieved[0].get("chunks_by_path", {})
            check(set(paths) >= {"tier1", "tier2a", "tier2b", "unassigned"},
                  f"all four collections queried: {sorted(paths)}")
    finally:
        for proc in (c3, c2):
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        c2_log.close(); c3_log.close()
    print(f"      Logs: {log_dir}")


def main() -> int:
    print("=" * 70)
    print("C3 SMOKE TEST -- gate, queue, budget, batching, expiry (thread 1.0.16)")
    print("=" * 70)
    part_a()
    if "--policy-only" not in sys.argv:
        part_b()
    print("\n" + "=" * 70)
    if failures:
        print(f"SMOKE TEST FAILED -- {len(failures)} assertion(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("SMOKE TEST PASSED -- gate, queue, budget, batching and expiry all hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
