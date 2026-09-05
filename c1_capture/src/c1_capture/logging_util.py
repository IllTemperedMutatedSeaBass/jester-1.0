"""Structured JSON logging, one line per stage-boundary event.

Every stage boundary across C1-C5 emits one JSON line with this shape so
Bar B's latency decomposition (DR-017) is reconstructable from ordinary
logs, not from test-only probes. Duplicated per-package rather than
imported across packages, matching the "no in-process shortcuts, five
separate packages" rule (CLAUDE.md) -- this is a component boundary, not
a place to share code between components.
"""
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
