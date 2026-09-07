"""C5: the D0 driver. Pure HTTP client, no listener of its own.

One command runs the loop: C1 (blocking capture+ASR) -> C5 -> C2 (reason)
-> C4 (speech) -> headset. C3 is NOT wired in this session (thread-1.0.6
ruling) -- the D0 path is C1 -> C5 -> C2 -> C4 only.
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
    log_event("C5", "turn_done", turn_id)


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
