"""C5: the D0 driver. Pure HTTP client, no listener of its own.

One command runs the loop: C1 (blocking capture+ASR) -> C5 -> C2 (reason)
-> C4 (speech) -> headset, and then C5 -> C3 (interjection gate).

C3 IS NOW IN THE D0 PATH (thread 1.0.16). The previous thread-1.0.6 ruling
-- "the D0 path is C1 -> C5 -> C2 -> C4 only" -- is superseded: C3 is
started by `ops/run_d0.sh` and called here after each completed utterance.

WHERE THE C3 CALL SITS, AND WHY IT MATTERS TO BAR B. The call is made
AFTER playback completes, i.e. after `T_ttfa` for this turn has already
been determined. It therefore does NOT enter the T_ttfa decomposition and
`bar_b_harness._PARTITION_STAGES` does not gain a member. What it DOES add
is wall-clock time between the end of one turn and the "SPEAK NOW" prompt
for the next, because the call BLOCKS: C3 in turn blocks on C2's
conflict_check, which is an Ollama call.

That blocking is a deliberate D0 choice, and its cost is real. It is
acceptable here only because the D0 loop is prompt-driven -- the human
waits for "SPEAK NOW" and does not speak into the gap. It would NOT be
acceptable in a real meeting, and it is also the reason DR-006's latency
mitigation is structurally present but not yet realised (see
`c3_router.main`'s docstring). Making the loop concurrent is carried in
BACKLOG.md.
"""
import argparse
import uuid

import httpx

from .config import Config
from .logging_util import log_event
from .playback import play_wav_bytes


def run_turn(config: Config, client: httpx.Client) -> None:
    pre_turn_id = str(uuid.uuid4())
    log_event("C5", "turn_start", pre_turn_id)

    transcribe_resp = client.post(
        f"{config.c1_base_url}/transcribe", timeout=config.TRANSCRIBE_TIMEOUT_S
    )
    transcribe_resp.raise_for_status()
    transcript_data = transcribe_resp.json()
    # C1 mints its own turn_id (it has no way to receive one -- /transcribe
    # takes no body). Adopt it as the canonical id for the rest of the turn
    # so every stage's structured log lines join on the same turn_id (Bar B
    # harness fix, thread 1.0.9 -- previously C5's own id never matched
    # C1's, so decompose_turn() could never find a complete turn).
    turn_id = transcript_data["turn_id"]
    log_event(
        "C5",
        "c1_response_received",
        turn_id,
        endpoint_monotonic_ts=transcript_data["endpoint_monotonic_ts"],
    )

    respond_resp = client.post(
        f"{config.c2_base_url}/respond",
        json={
            "turn_id": turn_id,
            "speaker": "human",
            "text": transcript_data["transcript"],
            # DR-032's shared-shape fields, sent explicitly rather than
            # left to C2's defaults: the point of the two fields is that a
            # caller declares which corpus and which caller-shape it is,
            # and C2 rejects a mismatch. Defaulting them at both ends
            # would leave nothing to disagree.
            "corpus_id": config.CORPUS_ID,
            "mode": "meeting_spoken",
            "intent": "question_answering",
        },
        timeout=60.0,
    )
    respond_resp.raise_for_status()
    respond_data = respond_resp.json()
    log_event(
        "C5", "c2_response_received", turn_id,
        status=respond_data.get("status", "ok"),
    )

    # DR-039: C2 signals context exhaustion as a NORMAL 200 response with
    # a status field, not as a 500. On the first occurrence it supplies a
    # short spoken notice; after that it returns empty text and this turn
    # produces no audio at all. Either way the loop continues -- capture
    # keeps running and the meeting is still recorded. Before DR-039 this
    # path was an uncaught exception that terminated the entire run, which
    # mid-meeting meant Jester simply stopped with a stack trace on a
    # terminal nobody was watching.
    if respond_data.get("status") == "context_exhausted" and not respond_data["text"]:
        log_event("C5", "turn_skipped_context_exhausted", turn_id)
        log_event("C5", "turn_done", turn_id)
        return

    synth_resp = client.post(
        f"{config.c4_base_url}/synthesize",
        params={"text": respond_data["text"], "turn_id": turn_id},
        timeout=60.0,
    )
    synth_resp.raise_for_status()
    log_event("C5", "c4_response_received", turn_id)

    play_wav_bytes(synth_resp.content, turn_id)

    # --- C3: the interjection gate (thread 1.0.16) --------------------
    # After playback, so this is outside T_ttfa for this turn. See the
    # module docstring for what it costs instead.
    _observe(config, client, turn_id, transcript_data["transcript"])

    log_event("C5", "turn_done", turn_id)


def _observe(config: Config, client: httpx.Client, turn_id: str, utterance: str) -> None:
    """Hand the completed utterance to C3 and speak an interjection if C3
    returns one.

    A C3 failure NEVER terminates the run. DR-039 established the
    principle for C2's overflow -- an advisory path degrades one turn, it
    does not end the meeting -- and it applies with more force here: C3 is
    strictly additive to a loop that worked without it, so a broken gate
    must cost silence, not the meeting.
    """
    if not config.C3_ENABLED:
        return

    _TRANSCRIPT.append(utterance)
    try:
        observe_resp = client.post(
            f"{config.c3_base_url}/observe",
            json={
                "turn_id": turn_id,
                "utterance": utterance,
                "transcript": "\n".join(_TRANSCRIPT),
                # A CONFIGURED STAND-IN, not a measurement -- C1's
                # endpointer is the only thing that knows the real gap.
                # See config.C3_ASSUMED_GAP_S.
                "gap_s": config.C3_ASSUMED_GAP_S,
            },
            timeout=config.C3_OBSERVE_TIMEOUT_S,
        )
        observe_resp.raise_for_status()
        observed = observe_resp.json()
    except Exception as exc:
        log_event("C5", "c3_observe_failed", turn_id,
                  error=f"{type(exc).__name__}: {exc}")
        return

    log_event("C5", "c3_response_received", turn_id,
              action=observed.get("action"),
              queue_depth=observed.get("queue_depth"),
              budget_remaining=observed.get("budget_remaining"),
              hand_up=observed.get("hand_up"))

    if observed.get("action") != "speak" or not observed.get("text"):
        return

    # C3 decided to interject. Synthesize and play it -- the SAME C4 path a
    # normal reply takes, so DR-044's prose citation goes through the same
    # text filter that strips bracketed markers.
    log_event("C5", "interjection_start", turn_id,
              candidates=observed.get("candidates_spoken"))
    try:
        synth = client.post(
            f"{config.c4_base_url}/synthesize",
            params={"text": observed["text"], "turn_id": turn_id},
            timeout=60.0,
        )
        synth.raise_for_status()
        play_wav_bytes(synth.content, turn_id)
    except Exception as exc:
        log_event("C5", "interjection_failed", turn_id,
                  error=f"{type(exc).__name__}: {exc}")
        return
    log_event("C5", "interjection_done", turn_id)


# Rolling transcript, process-level to match C2's own process-level prompt
# builder: one C5 process drives one meeting at D0.
_TRANSCRIPT: list[str] = []


def main() -> None:
    parser = argparse.ArgumentParser(description="D0 walking-skeleton driver")
    parser.add_argument("--turns", type=int, default=None)
    args = parser.parse_args()

    config = Config()
    turn_count = args.turns or config.TURN_COUNT

    print(
        f"D0 Bar B run: {turn_count} turns, "
        f"per-turn speak window {config.TRANSCRIBE_TIMEOUT_S:.0f}s.",
        flush=True,
    )

    with httpx.Client() as client:
        for i in range(turn_count):
            print(f"--- turn {i + 1}/{turn_count}: SPEAK NOW ---", flush=True)
            run_turn(config, client)


if __name__ == "__main__":
    main()
