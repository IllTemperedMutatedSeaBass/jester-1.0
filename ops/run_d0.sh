#!/usr/bin/env bash
# One command runs the D0 loop:
#   headset -> C1 -> C5 -> C2 -> C4 -> headset, then C5 -> C3.
# Starts C1, C2, C3 and C4 (HTTP services) in the foreground process group,
# waits for all of them to report healthy, then runs C5's turn loop. No
# systemd, no manual step between components (DR-017 Bar A items 1, 5;
# Bar C: no systemd units at D0).
#
# C3 IS STARTED HERE, from thread 1.0.16. This header previously read "C3
# is NOT started here -- it is not wired into the D0 loop this session
# (thread-1.0.6 ruling): the path is C1 -> C5 -> C2 -> C4 only." That
# ruling is superseded: C3 is the interjection gate (DR-042 budget and
# batching, DR-043 conflict_check, DR-044 form, DR-006 etiquette) and C5
# calls it after each completed utterance.
#
# To reproduce the pre-C3 baseline on this same build, set
# C5_C3_ENABLED=0 in .env -- C3 still starts, C5 simply does not call it.
# NOTE that setting it on the command line does NOT work: this script
# sources .env with `set -a` AFTER the shell environment is inherited, so
# .env silently WINS over both an inline `VAR=x ops/run_d0.sh` prefix and
# an exported variable. Change .env, or pass a CLI flag that C5 parses.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
else
    echo "No .env found at ${ENV_FILE} -- copy .env.example and fill it in." >&2
    exit 1
fi

C1_PORT="${C1_PORT:-8001}"
C2_PORT="${C2_PORT:-8002}"
C3_PORT="${C3_PORT:-8003}"
C4_PORT="${C4_PORT:-8004}"

# Each invocation gets its own timestamped directory (DR-027) -- logs used
# to be written with `>` truncation straight into logs/, so a second run
# silently destroyed the first run's figures. `logs/latest` is refreshed to
# point at the most recent run for convenience; it is a symlink, never a
# copy, so it never itself holds data that could be overwritten.
RUN_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="${REPO_ROOT}/logs/run_${RUN_STAMP}"
mkdir -p "${LOG_DIR}"
ln -sfn "run_${RUN_STAMP}" "${REPO_ROOT}/logs/latest"
echo "Logging this run to ${LOG_DIR} (logs/latest -> run_${RUN_STAMP})" >&2

# The bonded headset comes up on A2DP (sink-only) by default; C1 capture
# and C4 playback are simultaneous, so this must be HFP/mSBC before any
# turn runs (thread 1.0.8 finding, folded in per thread 1.0.9 / DR-024).
"${REPO_ROOT}/ops/ensure_hfp.sh"

PIDS=()
cleanup() {
    for pid in "${PIDS[@]:-}"; do
        kill "${pid}" 2>/dev/null || true
    done
}
trap cleanup EXIT

wait_healthy() {
    local url="$1"
    local name="$2"
    for _ in $(seq 1 60); do
        if curl -sf "${url}/docs" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.5
    done
    echo "${name} did not become healthy at ${url}" >&2
    exit 1
}

"${REPO_ROOT}/c1_capture/.venv/bin/python" -m c1_capture.main 2>"${LOG_DIR}/c1.jsonl" &
PIDS+=("$!")
"${REPO_ROOT}/c2_reason/.venv/bin/python" -m c2_reason.main 2>"${LOG_DIR}/c2.jsonl" &
PIDS+=("$!")
"${REPO_ROOT}/c3_router/.venv/bin/python" -m c3_router.main 2>"${LOG_DIR}/c3.jsonl" &
PIDS+=("$!")
"${REPO_ROOT}/c4_speech/.venv/bin/python" -m c4_speech.main 2>"${LOG_DIR}/c4.jsonl" &
PIDS+=("$!")

wait_healthy "http://${C1_HOST:-127.0.0.1}:${C1_PORT}" "C1"
wait_healthy "http://${C2_HOST:-127.0.0.1}:${C2_PORT}" "C2"
wait_healthy "http://${C3_HOST:-127.0.0.1}:${C3_PORT}" "C3"
wait_healthy "http://${C4_HOST:-127.0.0.1}:${C4_PORT}" "C4"

"${REPO_ROOT}/c5_orchestrator/.venv/bin/python" -m c5_orchestrator.main "$@" 2>"${LOG_DIR}/c5.jsonl"
