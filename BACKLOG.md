# BACKLOG.md — Jester 1.0

## Open

- **Walking skeleton code is written (thread 1.0.6): C1 → C5 → C2 → C4,
  C3 stubbed and NOT wired.** Bar A (DR-017) is NOT claimed as passed —
  it is proven by running the loop, not by writing it. See "Run Bar B
  measurement" below for what's blocking an actual run.
  - Pass bar fixed before build, three parts (DR-017): binary build bar
    (Bar A), a measured T_ttfa figure with a kill-switch at median > 8 s
    with the cap in place (Bar B, no pass side otherwise), and a
    coexistence bar protecting the 2.x demo (Bar C). C4 engine direction
    is HeathenS_Talkings, with kokoro as the D0 measurement engine and C4
    built engine-agnostic (DR-018).
  - OLLAMA_MODEL pinned to `gemma4-e4b-bakeoff:latest` (DR-020). Whether
    this is the same model identity G1/G3/the 10.5s 2.x cycle actually
    measured against is UNPROVEN — DR-020 records this as an
    identity-unverified comparison, not settled.

- **BAR A AND BAR B: BOTH RUN THIS SESSION (thread 1.0.9). Bar A item 5 is
  PROVEN; Bar B has a measured figure that PASSES the kill-switch.**
  1. `libportaudio2` blocker (1.0.6): CLOSED.
  2. Headset connectivity + HFP/A2DP blocker (1.0.7/1.0.8): CLOSED and now
     PERMANENT — `ops/ensure_hfp.sh` switches the CX 6.00BT off its
     power-on-default A2DP onto `headset-head-unit` (HFP/mSBC) and
     verifies `codec: msbc` via `pw-dump` before returning; `ops/run_d0.sh`
     calls it automatically before starting any service, so no future
     session repeats the manual `wpctl`/`pw-cli` steps.
  3. DR-023's empty-response blocker: CLOSED by DR-024. `c2_reason` now
     sends `/api/generate` with `raw: true` and a hand-rendered Gemma
     turn (`c2_reason/prompt.py`, `c2_reason/ollama_client.py`) instead
     of the pinned Modelfile's server-side `RENDERER gemma4` chat
     renderer, which DR-024 measured putting the model into an unbounded
     "thinking" mode that ate the whole 40-token cap on both
     `/api/generate` and `/api/chat`. Both candidate paths preserved G1's
     KV-cache prefix reuse (delta prefill ~0.55s against a 1.5s bar); the
     empty-response symptom, not prefix reuse, was the deciding factor.
  4. **NEW, found and fixed live this session:** C1 and C5 never shared a
     `turn_id` — C1 minted its own per-request id that never matched C5's,
     so the Bar B harness's per-turn log join always returned zero
     complete turns even though every turn ran correctly. Fixed in
     `c5_orchestrator/main.py`: C5 now adopts C1's returned `turn_id` as
     the canonical id for the rest of the turn instead of using its own.
  5. Ten-turn Bar A run (`ops/run_d0.sh`): **10/10 turns started and
     completed, zero tracebacks across all four services, no manual
     PipeWire/bluetoothctl touch after launch.** Bar A item 5 PROVEN.
  6. Twenty-turn Bar B run (`ops/run_d0.sh --turns 20`, re-run once after
     the turn_id fix so logs could actually be joined): T_ttfa median
     **4.28 s**, p90 **5.84 s**, kill-switch (median > 8 s) did NOT fire.
     Full stage decomposition, live carve, kernel, and model digest
     recorded — see RELAY.md's thread-1.0.9 STOP report.
  - Still needs the external-recorder click calibration run (Bar B) —
    hook exists (`c5_orchestrator.bar_b_harness.run_calibration_click_hook`),
    not automated, not attempted, per standing instruction (no confirmed
    equipment).
  - DR-021/DR-022/DR-025: live UMA carve settled at **2 GiB** across four
    readings on the same uninterrupted boot, against documented 16 GiB
    and the operator's stated 24 GiB. Not reconciled, not touched.

- **Two carried G1 constraints (DR-013), both binding on C2's design:**
  - Retrieved evidence must be appended AFTER the rolling transcript, never
    inserted before it — anything prepended invalidates the cached prefix and
    returns first-audio latency to the 5-11 s regime. (Seam exists in
    `c2_reason.prompt.PromptBuilder.build(evidence=...)`, exercised by
    signature only — no retrieval yet.)
  - num_ctx is 8192; a real meeting overflows it in 30-45 minutes. How to
    truncate the transcript WITHOUT destroying the cached prefix is
    UNDECIDED. `c2_reason.prompt` does not invent a policy — it raises
    `PromptOverflowError` loudly on overflow instead.

- **Clause-splitter optimisation, deferred (DR-013 G2).** Whether to split
  C2's output into clauses and synthesise them sequentially through C4 is
  an optimisation deferred to real HFP measurement, not built this
  session. Additive to the current whole-utterance C4 interface; does not
  change it.

- **C2 output currently decodes to empty text** against the pinned model
  under the bare `{{ .Prompt }}` template (no chat-turn wrapping) —
  `eval_count` shows real tokens generated but `response` is empty in
  smoke testing. Not investigated further this session (out of scope: the
  skeleton's job is wiring, not prompt-template tuning) — worth checking
  before Bar B is trusted as a meaningful figure, since an empty
  completion may synthesize near-silence through C4 and skew T_ttfa.

- **Kokoro weights provisioning into the D0 image is still open (DR-014).**
  Moved this session from `/tmp` (cleared on reboot) to
  `/home/jester/models/kokoro/` — outside both repos, not committed,
  checksum-verified before/after the move — but this is still a
  by-hand provisioning step, not an image-build artifact.

- **HeathenS_Talkings items carried from DR-018, none resolved:** the
  `stream_synthesize`/`chunk_size` claim (own gate, bar fixed
  beforehand), the 22050 Hz vs 24000 Hz sample-rate handling (C4's
  interface already carries sample_rate per DR-018, so this is
  positioned but not exercised against a real Glow-TTS backend), and the
  `HEATHEN_TTS_CACHE_DIR` runtime-fetch collision (recorded box-side in
  `jesterai/box/MULTI-STREAM.md` §9).

## Done

- Walking-skeleton code written: five packages, HTTP between every hop,
  env-driven config, structured JSON logging at every stage boundary,
  stable-prefix-plus-append C2 prompt builder, engine-agnostic C4 behind
  kokoro, C5 as pure client/driver, `ops/run_d0.sh` as the one-command
  entry point. Bar B harness written
  (`c5_orchestrator.bar_b_harness`) and unit-verified against synthetic
  log data — not yet run against a real loop. (thread 1.0.6)
