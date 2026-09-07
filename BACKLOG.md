# BACKLOG.md — Jester 1.0

## Open

- **D1 retrieval is wired into C2 and measured; C3 trigger logic is now the
  next build (thread 1.0.14, DR-035/DR-036/DR-037).** C2 answers questions
  from the corpus over the headset: `retrieval.py` implements DR-032's
  interface shape and DR-008's separate paths, and `retrieval_s` is a full
  member of the Bar B partition. **WHAT C3 MUST NOW DO, which this thread
  deliberately did not build:** (1) C3 has no trigger logic at all — it must
  decide WHEN to speak unprompted, which is a different problem from the
  question-answering path built here, and DR-008's "Tier 1 is the ONLY
  trigger source" binds it absolutely; (2) C3 must NOT reuse this thread's
  `intent="question_answering"` path — the unassigned collection is
  reachable only under that intent by DR-035's ruling, and a trigger caller
  carries a different intent and is rejected before it reaches that path.
  That rejection is asserted by test and must stay asserted; (3) C3 must fix
  a fire-rate bar BEFORE it is built, per WAYS_OF_WORKING §7 and DR-029 —
  DR-008's whole rationale is that the product's value is knowing when to
  stay SILENT, and a trigger path with no fire-rate bar cannot be evaluated
  against that; (4) the tier-assignment skew (41 of 46 documents UNASSIGNED,
  DR-034) is deferred to the C3 thread by operator ruling and lands there,
  not here — Tier 1 holding 5 documents is tolerable for question-answering
  because DR-035 opened a separate read path over the unassigned material,
  but a trigger path has no such fallback and fires off Tier 1 alone;
  (5) C3 must carry its own latency budget — retrieval already costs ~1.4 s
  at C2 (DR-037) and DR-017's 8 s kill switch is measured end to end.

- **DR-013(b)'s truncation policy is now an OPERATOR DECISION with the
  evidence assembled, not an open research question (thread 1.0.14,
  DR-036).** Measured: retrieval adds a CONSTANT ~794-token offset (not a
  growing one — evidence is never accumulated into the transcript), costing
  roughly 4 minutes of a ~43-minute meeting window. Four options are
  written up with their evidence in DR-036 (drop evidence first / truncate
  the transcript front / raise `num_ctx` / lower `top_k`); none is adopted.
  **Blocking sub-item, worth its own line because it is a live defect
  rather than a design question:** an overflow currently TERMINATES THE
  WHOLE RUN rather than degrading one turn — `PromptOverflowError` becomes
  a FastAPI 500 and `c5_orchestrator.main.run_turn`'s `raise_for_status()`
  is caught by nothing, so a real meeting would see Jester go permanently
  silent mid-session. Not fixed in 1.0.14 because the honest fix depends on
  which truncation policy is chosen.

- **DR-013(a)'s constraint buys back less than expected at D0, and this
  will change as transcripts lengthen (thread 1.0.14, DR-037).** G1 measured
  a ~5,000-token stable prefix with ~200 tokens appended; D0 runs the
  INVERSE ratio (~110-token stable prefix, ~800 tokens of fresh evidence
  every turn), so the cache hits but has little to hit. The constraint is
  not weakened and must not be relaxed — violating it still returns first
  audio to the 5-11 s regime — but re-measure the prefill split once real
  meeting-length transcripts exist, because the economics move in
  DR-013(a)'s favour as the transcript grows.

- **The pre-1.0.14 Bar B logs need `--allow-missing-retrieval` to
  re-decompose.** Runs recorded before the retrieval stage existed have no
  retrieval events. The flag is deliberately opt-in and must never be used
  on a retrieval-enabled run: it would report `retrieval_s` as 0.0 and
  silently understate exactly the cost the stage was added to measure.

- **Ingest built and run against the real DHI corpus (thread 1.0.13,
  DR-034); retrieval is NOT wired into C2 yet.** 46 documents ingested from
  `/mnt/jester_in` into 1.x's own Chroma store
  (`c2_reason/chroma_store`, `C2_CHROMA_PERSIST_DIR`), 622 chunks, 5 Tier1 /
  41 unassigned, embedding digest recorded and checked at store-open. What
  the next thread must do, in priority order: (1) wire retrieval into C2's
  `/respond` path per DR-032's interface shape (`corpus_id`/`mode`, evidence
  appended after the rolling transcript, never prepended — DR-013(a)); (2)
  build C3 trigger logic that actually reads Tier 1 (none exists yet — D1
  ingest only populates the store, it does not make Jester speak); (3)
  measure DR-013's `num_ctx` 8192 ceiling against a real retrieved-evidence
  payload added to a rolling transcript — untouched and unmeasured, and
  DR-032 already flags this as the first place a chat-mode caller's lack of
  a stable transcript prefix would bite too; (4) replace `tiering.py`'s
  path-keyword heuristic before the corpus grows past hand-auditable size
  (DR-034) — it was sized for ~46 documents, not a production ingest
  volume; (5) DR-030's purge mechanism still does not exist — this thread
  added a NEW persistent, cross-session retention surface (the Chroma store
  itself), which is a second concrete instance of the gap DR-030 already
  flagged, not a new finding, but worth re-stating: D1 retrieval now holds
  real (if low-sensitivity, per the corpus surveyed) DHI content on disk
  with no purge path.

- **D1 retrieval can now be scoped against a settled corpus/trigger design
  (thread 1.0.12, DR-029 through DR-032).** Buildable now: Tier 1 trigger
  path (DR-008, unchanged), Tier 2a substantiation-only path (DR-008/DR-029,
  unchanged), and a C2 request shape that carries `corpus_id` + `mode` with
  evidence appended after the rolling transcript (DR-032). Left open before
  build, in priority order: (1) fix a fire-rate bar for Tier 2b derived-
  criteria evaluation per WAYS_OF_WORKING §7 BEFORE running that experiment
  (DR-029) — nothing on this path may be built until the bar exists; (2)
  decide whether Tier 2b evaluation lives in C3 or C2, which needs a per-
  criterion latency measurement against C3's gate budget (DR-029, DR-006);
  (3) decide who signs off that a derived criterion is transformed enough
  to not be a derivative work (DR-029) — a legal call, not an engineering
  one; (4) build the ingest step's provenance/type/supersession/licensing
  capture and its three-way (Tier-1 / Tier-2 / reject) outcome before the
  DHI corpus can be classified (DR-031); (5) no purge mechanism exists for
  the box between sessions — DR-030's isolation posture is ruled as intent
  only, and the retention surfaces it names (logs, KV cache/ollama state,
  temp files) are unaddressed. Building D1 retrieval before (5) is closed
  means real session material accumulates on the box with no removal path.

- **The vector store to build D1 retrieval against is now specified
  (thread 1.0.12, DR-033).** Buildable now: Chroma, in a persistence
  directory distinct from 2.x's own (an env var, not yet wired), embeddings
  via `nomic-embed-text` pinned to blob digest
  `sha256-970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6`
  rather than the mutable `:latest` tag, and an ingest pipeline that is a
  COPY of 2.x's conversion code (pdfplumber/python-docx/python-pptx/
  openpyxl/beautifulsoup4/olefile/pytesseract) with a recorded fork-commit
  provenance hash — not a shared package, not a live dependency on
  `jester-2.1`. Left open before build: (1) the store must record the
  embedding-model digest it was built with, so a later tag move is
  detectable at store-open time rather than silently corrupting similarity
  results — the check mechanism itself is not designed yet; (2) the
  embedding model's fitness for 1.x's retrieval task on its merits is still
  fully open (`nomic-embed-text` is adopted here as the incumbent for
  convenience, not evaluated) — SEED §8 q2 carries this forward unclosed;
  (3) the copy-then-diverge fork point/commit for the ingest pipeline has
  not been chosen or hashed yet.


- **D0's rolling transcript is human-side-only and never truncated, and
  there is no retrieval yet -- a short, repetitive spoken script (e.g. a
  20-turn timing-calibration run saying "this is turn N" each time)
  reliably produces repetitive, semantically-thin replies (thread 1.0.11,
  DR-028: reproduced live, "I am here." / "Yes, I am here." /
  variations, and the operator observed the live run's turns 11+
  collapsing into variations of "Turn ten").** Root-caused, not a bug:
  `c2_reason.main.respond()` only ever calls
  `prompt_builder.append_transcript_line` for the human side -- the
  model's own past replies are never added to the rolling transcript, so
  it has no memory of what it already said -- combined with no retrieval
  (C3 stubbed, DR-013b) and no transcript truncation policy (also
  DR-013b, UNDECIDED). This is expected D0 behaviour given those already
  -documented gaps, not something to patch here. Worth revisiting
  together with the num_ctx truncation decision below, since both are
  about what the rolling transcript should actually contain.

- **`c4_speech`'s venv has no `pytest` installed** (found thread 1.0.11
  while adding `c4_speech/tests/test_text_filter.py`). Tests are written
  pytest-style (bare `test_*` functions) and were verified via a
  throwaway manual runner rather than `pytest`/`unittest discover`
  (`unittest` does not collect bare functions). Installing `pytest` was
  out of scope for a text-filter fix. Add it to `c4_speech/pyproject.toml`
  dev deps next time that package is touched, so `pytest` runs directly.

- **Interactive spoken Bar B runs are driven from the operator's own
  terminal, never relayed through chat (thread 1.0.10).** An earlier
  attempt (this same thread, stalled) tried routing "SPEAK NOW" turn
  prompts through a background monitor posting into chat. Root cause of
  that stall was separate (the prompt printed to `sys.stderr`, which
  `run_d0.sh` redirects to a log file, so it never reached any terminal —
  fixed in commit a641163) — but the chat-relay approach itself is also
  wrong on its own terms and should not be retried even once printing is
  fixed: chat is turn-based, a relay adds seconds of latency to every
  turn, and a T_ttfa measured on turns where the human was waiting on a
  chat message would not be the figure DR-017 asks for (real spoken
  latency, not chat-relay latency). Any future interactive/spoken
  harness run must be started by the operator directly in their own SSH
  terminal against the restructured foreground harness (`ops/run_d0.sh`,
  prompts on stdout with `flush=True`); a Claude Code session's role is
  to verify plumbing non-interactively first (`C1_CAPTURE_WAV`) and then
  hand off the exact command, not to drive or relay the live run itself.

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

- **Emoji/stage-direction suppression and DR-024's stop-sequence gap,
  both closed (DR-027, thread 1.0.11).** C2's `STABLE_PREAMBLE` now
  instructs the model not to emit emoji, asterisked stage directions, or
  parenthetical narration; C2's `/api/generate` call now passes
  `"stop": ["<end_of_turn>"]`, closing the gap DR-024 left open after
  turn 9 leaked a literal `<end_of_turn>` in thread 1.0.10. C4 also
  strips the same classes (plus complete-or-truncated Gemma control
  markers) defensively, independent of C2's prompt, in a new
  `c4_speech.text_filter.strip_unspeakable()`, unit-tested (10/10) and
  live-smoke-tested against the real model and Kokoro engine. `run_d0.sh`
  no longer truncates prior logs (writes to `logs/run_<timestamp>/`,
  `logs/latest` symlinked). Bar B was re-anchored; see DR-027 and
  RELAY.md's thread-1.0.11 STOP report for the fresh figure once the
  operator's spoken run completes.

- **Preamble-leak defect found on the first post-DR-027 spoken run and
  fixed (DR-028, thread 1.0.11).** Two of twenty turns synthesized a
  cap-truncated copy of C2's own system preamble instead of a reply.
  Reproduced live via direct HTTP stress-testing, root-caused to raw
  -mode completion drifting into copying nearby prompt text on a
  repetitive, information-free transcript. Fixed three ways: a recency
  -placed anti-echo reminder in the prompt (`c2_reason/prompt.py`), C2
  -side detection-and-replacement with a logged `preamble_leak_detected`
  event (`c2_reason/main.py`), and an independent C4-side backstop that
  refuses to synthesize a detected leak (`c4_speech/text_filter.py`,
  `c4_speech/main.py`). 14/14 unit tests pass; the fix was live-verified
  against the exact stress sequence that reproduced the bug (zero leaks
  across 30 turns) and the C4 backstop was verified in isolation. NOT yet
  validated on a real spoken run -- see DR-028 for why this run's figure
  is held provisional and a fresh operator run is recommended before
  re-anchoring Bar B.
