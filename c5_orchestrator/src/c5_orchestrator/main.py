"""C5: the D0 driver. Pure HTTP client, no listener of its own.

One command runs the loop: C1 (blocking capture+ASR) -> C5 -> C2 (reason)
-> C4 (speech) -> headset. C3 is NOT wired in this session (thread-1.0.6
ruling) -- the D0 path is C1 -> C5 -> C2 -> C4 only.
"""
import argparse
import sys
import uuid

import httpx

from .config import Config
from .logging_util import log_event
from .playback import play_wav_bytes


def run_turn(config: Config, client: httpx.Client) -> None:
    turn_id = str(uuid.uuid4())
    log_event("C5", "turn_start", turn_id)

    transcribe_resp = client.post(f"{config.c1_base_url}/transcribe", timeout=120.0)
    transcribe_resp.raise_for_status()
    transcript_data = transcribe_resp.json()
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
        },
        timeout=60.0,
    )
    respond_resp.raise_for_status()
    respond_data = respond_resp.json()
    log_event("C5", "c2_response_received", turn_id)

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

    with httpx.Client() as client:
        for i in range(turn_count):
            print(f"--- turn {i + 1}/{turn_count} ---", file=sys.stderr)
            run_turn(config, client)


if __name__ == "__main__":
    main()
