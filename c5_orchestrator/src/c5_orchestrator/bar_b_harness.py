"""Bar B measurement harness (DR-017).

Drives twenty scripted turns via run_turn() (see main.py) and computes
median/p90 T_ttfa plus the mandatory per-stage decomposition, reading
ONLY the structured JSON log lines each component already emits at its
stage boundaries -- no test-only probes (DR-017 Bar A item 3).

All four components (C1, C2, C4, C5) run on this one host, so their
time.monotonic() values share the same CLOCK_MONOTONIC and are directly
comparable across process boundaries -- this does NOT hold once any
component moves to a different machine, and this harness would need
NTP-disciplined wall-clock timestamps (or a single shared clock source)
at that point.

DOES NOT RUN THE MEASUREMENT ITSELF this session (thread-1.0.6 ruling) --
it needs the operator on the headset. This module is exercised only via
its own unit-testable pure functions until then.
"""
import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any


class MissingCarveError(RuntimeError):
    pass


def read_uma_carve_bytes() -> int:
    """Read the current UMA carve from sysfs. Refuses to guess -- Bar B's
    figure is meaningless without the carve that was in force (DR-017).

    CAVEAT (DR-021): mem_info_vram_total is the fixed VRAM BAR, not
    necessarily "the carve" as a single number once GTT (dynamic system-RAM
    borrowing) is substantial -- observed live at a small 2 GiB BAR / 14.3
    GiB Ollama-reported compute total. This function reports the sysfs
    value verbatim, matching box/HARDWARE.md's own method; it does not
    reconcile it against Ollama's "inference compute total" log line.
    Confirm the BIOS setting is the intended one before trusting this
    figure for a real measurement run.
    """
    matches = sorted(Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"))
    if not matches:
        raise MissingCarveError(
            "Could not read /sys/class/drm/card*/device/mem_info_vram_total "
            "-- refusing to emit a T_ttfa figure without the UMA carve in "
            "force (DR-017 Bar B)."
        )
    return int(matches[0].read_text().strip())


def load_events(log_paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    """Read JSONL structured-log files, group by turn_id."""
    by_turn: dict[str, list[dict[str, Any]]] = {}
    for path in log_paths:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                # Non-JSON lines (e.g. uvicorn's own startup/access logs,
                # which share the same stderr stream) are expected and
                # skipped rather than treated as a parse failure.
                continue
            if "turn_id" not in record:
                continue
            by_turn.setdefault(record["turn_id"], []).append(record)
    return by_turn


def _find(events: list[dict], stage: str, event: str) -> dict | None:
    for e in events:
        if e["stage"] == stage and e["event"] == event:
            return e
    return None


def decompose_turn(
    events: list[dict], allow_missing_retrieval: bool = False
) -> dict[str, float] | None:
    """Compute one turn's stage durations and T_ttfa. Returns None if any
    required event is missing (incomplete/failed turn -- excluded, not
    padded with a guess).

    `allow_missing_retrieval` exists ONLY to re-decompose runs recorded
    before thread 1.0.14 added the retrieval stage (e.g. DR-026's D0
    baseline logs), which have no retrieval events at all. It is OFF by
    default and must be asked for explicitly, because defaulting a missing
    retrieval stage to 0.0 inside a retrieval-ENABLED run would silently
    understate exactly the cost this stage was added to measure. Turning it
    on for such a run is a measurement error, not a convenience."""
    endpoint = _find(events, "C1", "endpoint_declared")
    asr_done = _find(events, "C1", "asr_done")
    retrieval_start = _find(events, "C2", "retrieval_start")
    retrieval_done = _find(events, "C2", "retrieval_done")
    prefill_start = _find(events, "C2", "prefill_start")
    prefill_done = _find(events, "C2", "prefill_done")
    generate_done = _find(events, "C2", "generate_done")
    synth_start = _find(events, "C4", "synthesize_start")
    synth_done = _find(events, "C4", "synthesize_done")
    playout_start = _find(events, "C5", "playout_start")
    playout_done = _find(events, "C5", "playout_done")

    retrieval_missing = retrieval_start is None or retrieval_done is None
    if retrieval_missing and not allow_missing_retrieval:
        return None

    required = [
        endpoint, asr_done, prefill_start, prefill_done, generate_done,
        synth_start, synth_done, playout_start, playout_done,
    ]
    if any(e is None for e in required):
        return None

    endpoint_ts = endpoint["endpoint_monotonic_ts"]
    return {
        "asr_tail_s": asr_done["monotonic_ts"] - endpoint_ts,
        # Retrieval is a full partition member, not a footnote: it runs
        # between C2 receiving the turn and C2 starting prefill (see
        # c2_reason/main.py's module docstring -- prefill_start is
        # deliberately logged AFTER retrieval_done so retrieval cost
        # cannot hide inside c2_prefill_s with no error raised).
        "retrieval_s": 0.0 if retrieval_missing else (
            retrieval_done["monotonic_ts"] - retrieval_start["monotonic_ts"]
        ),
        "c2_prefill_s": prefill_done["prefill_done_monotonic_ts"] - prefill_start["monotonic_ts"],
        "c2_generate_s": generate_done["generate_done_monotonic_ts"] - prefill_done["prefill_done_monotonic_ts"],
        "tts_s": synth_done["monotonic_ts"] - synth_start["monotonic_ts"],
        "playout_s": playout_done["monotonic_ts"] - playout_start["monotonic_ts"],
        "t_ttfa_s": playout_start["monotonic_ts"] - endpoint_ts,
        # Not durations -- carried alongside so the retrieval COST can be
        # read against the retrieval VOLUME in the same record. The
        # evidence-attributable share of prefill is the dominant half of
        # retrieval's effect on T_ttfa and it lands in c2_prefill_s, not
        # in retrieval_s.
        "retrieved_chunks": 0 if retrieval_missing else retrieval_done.get("chunks_total", 0),
        "evidence_tokens_est": 0 if retrieval_missing else retrieval_done.get("evidence_tokens_est", 0),
        "prompt_eval_count": prefill_done.get("prompt_eval_count", 0),
        "embed_s": 0.0 if retrieval_missing else retrieval_done.get("embed_s", 0.0),
        "query_s": 0.0 if retrieval_missing else retrieval_done.get("query_s", 0.0),
    }


_PARTITION_STAGES = [
    "asr_tail_s", "retrieval_s", "c2_prefill_s", "c2_generate_s", "tts_s",
]


def summarize(decompositions: list[dict[str, float]]) -> dict[str, Any]:
    """Note (DR-027 decomposition audit): `_PARTITION_STAGES` are the ONLY
    stages that partition T_ttfa -- per-turn, their sum matches t_ttfa_s to
    within a few ms (scheduling overhead between stage boundaries). Do not
    compare a *summed median* of these stages against the *median* of
    t_ttfa_s: medians do not add across turns with different individual
    timings, so that comparison is not a validity check and will look wrong
    even when the underlying data is fine -- compare per-turn sums instead
    (see `partition_gap_median_s` below, or bar_b_harness tests).

    `playout_s` (playout_start -> playout_done, i.e. end-of-audio) is
    POST-T_ttfa by DR-017's definition (T_ttfa ends at first PCM frame,
    logged as playout_start) and is reported separately, never inside the
    partition, so it is not mistaken for a fifth partition member."""
    t_ttfa_values = [d["t_ttfa_s"] for d in decompositions]
    summary: dict[str, Any] = {
        "n_turns": len(decompositions),
        "t_ttfa_median_s": statistics.median(t_ttfa_values),
        "t_ttfa_p90_s": statistics.quantiles(t_ttfa_values, n=10)[8]
        if len(t_ttfa_values) >= 10
        else max(t_ttfa_values),
    }
    for stage in _PARTITION_STAGES:
        values = [d[stage] for d in decompositions]
        summary[f"{stage}_median"] = statistics.median(values)

    partition_gaps = [
        d["t_ttfa_s"] - sum(d[stage] for stage in _PARTITION_STAGES)
        for d in decompositions
    ]
    summary["partition_gap_median_s"] = statistics.median(partition_gaps)
    summary["partition_gap_max_s"] = max(partition_gaps)

    summary["post_ttfa_playout_s_median"] = statistics.median(
        d["playout_s"] for d in decompositions
    )

    # Retrieval volume, reported next to retrieval cost so the two are
    # read together. `evidence_tokens_est` is an ESTIMATE (chars/4);
    # `prompt_eval_count` is Ollama's own exact count of tokens actually
    # prefilled this turn. On a cache hit the latter is the DELTA, so the
    # evidence share of it is the figure that says what retrieval costs
    # in prefill.
    for field_name in (
        "retrieved_chunks", "evidence_tokens_est", "prompt_eval_count",
        "embed_s", "query_s",
    ):
        values = [d.get(field_name, 0) for d in decompositions]
        summary[f"{field_name}_median"] = statistics.median(values)

    return summary


KILL_SWITCH_MEDIAN_S = 8.0


def run_calibration_click_hook() -> None:
    """Hook for the external-recorder click-at-endpoint calibration run
    (DR-017 Bar B). NOT ATTEMPTED this session -- it needs a physical
    recorder against the earpiece and the operator present. Wire the
    actual recording/analysis here when that run happens."""
    raise NotImplementedError(
        "External-recorder calibration run is not automated -- it needs "
        "the operator, a recorder, and a physical click at the headset. "
        "See DR-017 Bar B."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bar B T_ttfa harness")
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs/latest"),
        help="Directory containing c1.jsonl, c2.jsonl, c4.jsonl, c5.jsonl "
        "(default: logs/latest, the symlink run_d0.sh points at its most "
        "recent per-run timestamped log directory -- DR-027)",
    )
    parser.add_argument(
        "--allow-missing-retrieval",
        action="store_true",
        help="Re-decompose a run recorded BEFORE the retrieval stage "
        "existed (pre-thread-1.0.14, e.g. DR-026's D0 baseline logs), "
        "treating retrieval_s as 0.0. Never use this on a "
        "retrieval-enabled run: it would silently understate the retrieval "
        "cost the stage exists to measure.",
    )
    args = parser.parse_args()

    try:
        carve_bytes = read_uma_carve_bytes()
    except MissingCarveError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    log_paths = [args.log_dir / f"{c}.jsonl" for c in ("c1", "c2", "c4", "c5")]
    by_turn = load_events(log_paths)

    decompositions = []
    for turn_id, events in by_turn.items():
        d = decompose_turn(events, allow_missing_retrieval=args.allow_missing_retrieval)
        if d is not None:
            decompositions.append(d)

    if len(decompositions) < args.turns:
        print(
            f"Only {len(decompositions)}/{args.turns} turns had complete "
            f"stage logs -- run more turns or check for hung components "
            f"before trusting this figure.",
            file=sys.stderr,
        )

    if not decompositions:
        print("No complete turns to summarize.", file=sys.stderr)
        sys.exit(1)

    summary = summarize(decompositions)
    summary["uma_carve_bytes"] = carve_bytes
    summary["uma_carve_gib"] = round(carve_bytes / (1024**3), 2)
    summary["kill_switch_median_s"] = KILL_SWITCH_MEDIAN_S
    summary["kill_switch_fired"] = summary["t_ttfa_median_s"] > KILL_SWITCH_MEDIAN_S

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
