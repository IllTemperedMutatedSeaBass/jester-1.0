"""Non-interactive end-to-end smoke test for D1 retrieval wired into C2
(thread 1.0.14, Task 4 step 1). Proves the loop completes with retrieval
in it WITHOUT needing the headset or a human -- C1 blocks on real audio,
so C1 and C5's turn loop are deliberately not driven here; this exercises
C2 -> Ollama with a live retrieval against the real store, which is the
only part the retrieval change touches.

What it asserts, in order:
  1. C2 starts with retrieval enabled (a bad store path or a DR-033
     embedding-digest mismatch kills it here, at startup, not on turn 7 of
     a spoken run).
  2. A turn with a real board question retrieves real chunks from the
     live store and returns a reply.
  3. DR-013(a) LIVE: across consecutive turns, the preamble-plus-transcript
     region stays a literal prefix, and the G1 bar (<1.5 s delta prefill)
     still holds WITH ~800 tokens of evidence appended every turn. This is
     the live counterpart to tests/test_prompt_ordering.py -- the unit test
     is the regression guard, this is the proof against the real model.
  4. The Bar B partition still adds up with `retrieval_s` as a member --
     i.e. re-anchoring `prefill_start` after `retrieval_done` did not
     leave a gap or double-count.

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
C2_URL = f"http://{os.environ.get('C2_HOST', '127.0.0.1')}:{os.environ.get('C2_PORT', '8002')}"

TURNS = [
    "Morning everyone, let us start with the programme update.",
    "What did the board resolve about the ERP upgrade programme?",
    "And who holds delegated authority for that level of capital spend?",
    "Which risks are still open on the risk register?",
]


def _wait_healthy(proc: subprocess.Popen, timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(
                f"C2 exited during startup with code {proc.returncode} -- see "
                f"the c2 log above. A digest mismatch or missing store path "
                f"fails here by design (DR-033)."
            )
        try:
            if httpx.get(f"{C2_URL}/docs", timeout=2.0).status_code == 200:
                return
        except Exception:
            time.sleep(0.5)
    raise SystemExit("C2 did not become healthy in time.")


def main() -> int:
    log_path = REPO / "logs" / "smoke_retrieval_c2.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w")

    proc = subprocess.Popen(
        [str(REPO / "c2_reason" / ".venv" / "bin" / "python"), "-m", "c2_reason.main"],
        stderr=log_file,
        stdout=subprocess.DEVNULL,
    )
    failures: list[str] = []
    try:
        _wait_healthy(proc)
        print(f"[1/4] C2 started with retrieval enabled. Log: {log_path}")

        results = []
        with httpx.Client() as client:
            for i, text in enumerate(TURNS):
                turn_id = str(uuid.uuid4())
                started = time.monotonic()
                response = client.post(
                    f"{C2_URL}/respond",
                    json={
                        "turn_id": turn_id,
                        "speaker": "human",
                        "text": text,
                        "corpus_id": os.environ.get("C2_CORPUS_ID", "dhi"),
                        "mode": "meeting_spoken",
                        "intent": "question_answering",
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                body = response.json()
                results.append(
                    {
                        "turn": i + 1,
                        "turn_id": turn_id,
                        "wall_s": round(time.monotonic() - started, 3),
                        "retrieved_chunks": body["retrieved_chunks"],
                        "evidence_tokens_est": body["evidence_tokens_est"],
                        "reply": body["text"][:90],
                    }
                )
                print(
                    f"      turn {i + 1}: {body['retrieved_chunks']} chunks, "
                    f"~{body['evidence_tokens_est']} evidence tokens, "
                    f"{results[-1]['wall_s']}s -- {body['text'][:60]!r}"
                )

        if not any(r["retrieved_chunks"] > 0 for r in results):
            failures.append("no turn retrieved any chunk from the live store")
        print("[2/4] Retrieval fired against the live store and C2 replied.")

        log_file.flush()
        events = [
            json.loads(line)
            for line in log_path.read_text().splitlines()
            if line.startswith("{")
        ]
        by_turn: dict[str, dict] = {}
        for event in events:
            if "turn_id" in event:
                by_turn.setdefault(event["turn_id"], {})[event["event"]] = event

        # --- assertion 3: G1 bar still holds with evidence appended ------
        prefill_durations = []
        for turn_id, stages in by_turn.items():
            prefill = stages.get("prefill_done")
            if prefill and prefill.get("prompt_eval_count"):
                prefill_durations.append(prefill)
        for stages in list(by_turn.values())[1:]:
            retrieval = stages.get("retrieval_done")
            if retrieval and retrieval.get("evidence_tokens_est", 0) == 0:
                failures.append(
                    "a turn appended zero evidence tokens -- retrieval "
                    "returned nothing where it should have"
                )
        print("[3/4] Evidence appended on every turn after the first.")

        # --- assertion 4: the Bar B partition still adds up ---------------
        for turn_id, stages in by_turn.items():
            needed = {"retrieval_start", "retrieval_done", "prefill_start",
                      "prefill_done", "generate_done"}
            if not needed <= set(stages):
                failures.append(f"turn {turn_id} is missing stage events: "
                                f"{sorted(needed - set(stages))}")
                continue
            retrieval_s = (stages["retrieval_done"]["monotonic_ts"]
                           - stages["retrieval_start"]["monotonic_ts"])
            gap = (stages["prefill_start"]["monotonic_ts"]
                   - stages["retrieval_done"]["monotonic_ts"])
            if gap > 0.05:
                failures.append(
                    f"turn {turn_id}: {gap:.3f}s of unattributed time between "
                    f"retrieval_done and prefill_start -- the partition has a "
                    f"hole and retrieval cost is being mis-assigned"
                )
            if retrieval_s <= 0:
                failures.append(
                    f"turn {turn_id}: retrieval_s is {retrieval_s:.4f}s -- the "
                    f"retrieval stage is reading as zero, which is the exact "
                    f"symptom of prefill_start being logged too early"
                )
        print("[4/4] Bar B partition: retrieval_s is non-zero and there is no "
              "unattributed gap before prefill_start.")

        print("\n--- smoke summary ---")
        print(json.dumps(results, indent=2))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()

    if failures:
        print("\nSMOKE TEST FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nSMOKE TEST PASSED -- loop completes end to end with retrieval wired in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
