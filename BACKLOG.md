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

- **RUN BAR B MEASUREMENT — next action, blocked on two items:**
  1. `libportaudio2` (the system shared library `sounddevice` needs) is
     NOT installed on this box — `import sounddevice` raises `OSError:
     PortAudio library not found`. This blocks C1 (mic capture) and C5
     (playback) from running at all. Needs `sudo apt install
     libportaudio2` — not attempted this session (no sudo authorised;
     brief said report and stop rather than install un-authorised
     things).
  2. DR-021: the live UMA carve read via
     `/sys/class/drm/card0/device/mem_info_vram_total` is currently
     **2 GiB**, not the documented "16 GiB current" — confirm what the
     BIOS is actually set to (and restore the intended value if 2 GiB
     was a leftover from the BIOS ladder exploration) before trusting
     Bar B's carve figure.
  - Needs the operator on the headset regardless (VAD/mic can't be
    scripted from this session). Also needs the external-recorder click
    calibration run (Bar B) — hook exists
    (`c5_orchestrator.bar_b_harness.run_calibration_click_hook`), not
    automated, not attempted.

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
