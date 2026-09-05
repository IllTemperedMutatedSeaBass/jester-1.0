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

- **RUN BAR B MEASUREMENT — next action, now blocked on DR-023 (thread
  1.0.8):**
  1. `libportaudio2` blocker (1.0.6): CLOSED, confirmed again this session.
  2. Headset connectivity blocker (1.0.7): CLOSED this session — CX 6.00BT
     connected, profile switched to `headset-head-unit` (HFP/mSBC,
     confirmed via `pw-dump`: `api.bluez5.codec: msbc`), both bluez sink
     and source were the active PipeWire defaults. C1 captured and
     transcribed live speech (`asr_done`, `transcript_chars: 36`) —
     the full capture path is proven working end-to-end for the first
     time.
  3. **NEW blocking item — DR-023:** with live audio working, turn 1
     crashed one hop later. `c2_reason`'s raw-prompt call to
     `/api/generate` returns an empty `response` string against this
     model's `RENDERER gemma4`/`PARSER gemma4` Modelfile (confirmed via
     direct `curl`, reproducible independent of live audio; `/api/chat`
     against the same model does not exhibit this). C5 has no per-turn
     error handling, so C4's resulting 500 (empty text to `kokoro_onnx`)
     killed the whole ten-turn loop after turn 1. This needs an operator
     ruling on whether `c2_reason` should move to `/api/chat` or a
     templated raw prompt — DR-023 explicitly did not fix this, because
     it may be in tension with the stable-prefix-plus-append caching
     rationale (DR-013a).
  4. DR-021/DR-022: live UMA carve read again this session — still
     **2 GiB**, unchanged since DR-021 (thread 1.0.6), still on the same
     uninterrupted boot, despite the operator's stated BIOS value moving
     from ~16 GiB to 24 GiB in the interim. Confirm what the BIOS is
     actually set to and reboot before trusting Bar B's carve figure.
  - Still needs the external-recorder click calibration run (Bar B) —
    hook exists (`c5_orchestrator.bar_b_harness.run_calibration_click_hook`),
    not automated, not attempted.

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
