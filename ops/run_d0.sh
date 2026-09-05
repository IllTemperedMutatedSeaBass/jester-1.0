#!/usr/bin/env bash
# One command runs the D0 loop: headset -> C1 -> C5 -> C2 -> C4 -> headset.
# Starts C1 and C4 (HTTP services) in the foreground process group, waits
# for both to report healthy, then runs C5's turn loop. No systemd, no
# manual step between components (DR-017 Bar A items 1, 5; Bar C: no
# systemd units at D0).
#
# C3 is NOT started here -- it is not wired into the D0 loop this session
# (thread-1.0.6 ruling): the path is C1 -> C5 -> C2 -> C4 only.
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
C4_PORT="${C4_PORT:-8004}"

LOG_DIR="${REPO_ROOT}/logs"
mkdir -p "${LOG_DIR}"

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
"${REPO_ROOT}/c4_speech/.venv/bin/python" -m c4_speech.main 2>"${LOG_DIR}/c4.jsonl" &
PIDS+=("$!")

wait_healthy "http://${C1_HOST:-127.0.0.1}:${C1_PORT}" "C1"
wait_healthy "http://${C2_HOST:-127.0.0.1}:${C2_PORT}" "C2"
wait_healthy "http://${C4_HOST:-127.0.0.1}:${C4_PORT}" "C4"

"${REPO_ROOT}/c5_orchestrator/.venv/bin/python" -m c5_orchestrator.main "$@" 2>"${LOG_DIR}/c5.jsonl"
