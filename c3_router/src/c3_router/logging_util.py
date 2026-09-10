"""Structured JSON logging, one line per stage-boundary event. See
c1_capture/logging_util.py for why this is duplicated, not imported,
across packages."""
import json
import sys
import time


def log_event(stage: str, event: str, turn_id: str, **fields) -> None:
    record = {
        "stage": stage,
        "event": event,
        "turn_id": turn_id,
        "monotonic_ts": time.monotonic(),
        "wall_ts": time.time(),
        **fields,
    }
    print(json.dumps(record), file=sys.stderr, flush=True)
