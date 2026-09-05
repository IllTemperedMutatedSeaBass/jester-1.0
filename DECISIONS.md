# DECISIONS.md — Jester 1.0 decision log

> **Append-only.** Entries are never edited or renumbered after the fact;
> corrections are new entries. This file carries the Jester 1.x stream's DR
> series, which **continues from the existing series in `jesterai/DECISIONS.md`**
> — the next free number in this repo is **DR-016**, not DR-001.
>
> DR-002 through DR-015 were filed in `jesterai/DECISIONS.md` before this repo
> existed. They remain frozen there and are never renumbered or copied into
> this file. See `jesterai/DECISIONS.md` for that record.
>
> Before assigning a new DR number here, check the highest number across
> **both** this file and `jesterai/DECISIONS.md`.

---

## 2026-09-05 — Thread 1.0.5: pass bar and C4 engine direction

### DR-017 — D0 walking skeleton pass bar fixed before build (2026-09-05)

The bar is fixed before any build work per `WAYS_OF_WORKING.md` §7, and is
split in three because DR-014 charged the skeleton with PRODUCING the first
honest first-audio figure — so that figure cannot also be the build's
pass/fail. Precedent on record: G2 failed a bar that measured the wrong
thing, G3(b) was anchored to the wrong number, and the mirror-image error
here would be a bar that reads an honest bad measurement as a failed build.

**BAR A — SKELETON IS BUILT.** Binary, all five required:

1. One command runs headset → C1 → C5 → C2 → C4 → headset, no file staging,
   no manual step between components.
2. Every hop is HTTP on env-configured addresses, no in-process shortcut,
   per SEED §7.
3. Every stage boundary emits a structured JSON log line carrying a turn id
   and a monotonic timestamp, so the latency decomposition is
   reconstructable from ordinary logs rather than from probes added for the
   test.
4. C2's prompt is built as stable prefix plus append, exercising G1's
   prefix reuse, and C4 is called whole-utterance with no assumption of
   incremental output per DR-013.
5. Ten consecutive scripted turns with no restart, no manual PipeWire
   reconnect, no hung component.

**BAR B — THE FIGURE.** A measurement with a kill-switch, not a graded bar.
Primary metric T_ttfa: VAD-declared end-of-speech to first PCM frame
written to the headset sink, over twenty scripted 1-on-1 turns. Reported as
median and p90, never mean alone, citing G3's worst-case spike as
precedent. C2 output capped at 40 tokens with the cap recorded alongside
the figure, because DR-013 established TTFA is a function of utterance
length and an uncapped figure is uninterpretable. Per-stage decomposition
mandatory (endpoint, ASR tail, C2 prefill, C2 generate, TTS, playout),
because a single aggregate is not diagnosable. One calibration run with an
external recorder capturing the earpiece against a click at endpoint, to
bound the 100-200 ms Bluetooth transport that `jesterai/box/AUDIO.md` still
carries as ESTIMATED, UNMEASURED. The UMA carve in force MUST be recorded
with the figure; a T_ttfa without its carve is not a comparable number.

KILL-SWITCH: median T_ttfa greater than 8 s with the cap in place. That is
the 5-11 s regime DR-006 held etiquette cannot rescue, and indicates prefix
reuse is not surviving the assembled loop. If it fires the sprint stops and
a re-architecture DR precedes further build work; per
`WAYS_OF_WORKING.md` §9 a fire is documented, never silently cleared. Any
median at or below 8 s is RECORDED AS THE D0 BASELINE, NOT GRADED. Bar B
has no pass side.

**BAR C — COEXISTENCE WITH 2.x.** The objective is demo AIamA 2.2,
reconfigure, demo Jester 1.0 on one box; a skeleton that passes A and B
while breaking that has failed. Binding on the D0 build, each item
traceable to a numbered finding in `jesterai/box/MULTI-STREAM.md` §2:

- No `ollama cp` or aliasing of any kind — 1.0 addresses models by their
  real tag, protecting finding #5's global model namespace.
- No writes to `/run/jester` or `/var/log/jester` (#1, #2, #3) — 1.0 uses
  its own env-var-driven paths.
- NO systemd units installed at D0 — the skeleton runs in the foreground
  from the repo, which also avoids pre-empting the ops/ boundary question
  §6 leaves open.
- All ports env-driven and chosen clear of 2.x's webui and kiosk units
  (#10, #16).
- Bluetooth pairing and PipeWire defaults must leave the shared per-user
  bond store usable by 2.x unchanged (§3).

ACCEPTANCE: after a D0 run, the 2.2 demo comes up clean with no step beyond
the documented switch.

### DR-018 — C4 TTS engine: HeathenS_Talkings is the direction, Kokoro is the D0 measurement engine (2026-09-05)

RULED: the intended long-term engine behind C4 is HeathenS_Talkings
(github.com/IllTemperedMutatedSeaBass/HeathenS_Talkings, package
`heathen-tts`, Apache-2.0, the operator's own project). It is a separate
standalone project, not a Jester stream, and its own
`docs/PROJECT_STATUS.md` locks in "HeathenS_Talkings standalone; Jester
optional consumer", with Jester integration as its Phase 5.

CONSEQUENCE FOR CODE POLICY: `WAYS_OF_WORKING.md` §12 copy-then-diverge
does NOT apply here, because that rule governs reuse BETWEEN Jester
streams. HeathenS is an external dependency and is consumed as one —
declared in `c4_speech/pyproject.toml` and pinned to a commit hash, never
vendored, never forked into this repo.

SEQUENCING, and the reason for it. HeathenS_Talkings is at Phase 1 with the
Glow-TTS engine backend NOT yet implemented — its own `PROJECT_STATUS.md`
lists it as the immediate next task, while `api.py` and the CLI are already
written against that interface. kokoro-onnx is measured working on this
box under G2. D0 therefore builds C4 against kokoro, and HeathenS is
adopted when its Phase 1 closes.

BINDING ON THE BUILD: C4 exposes ONE engine-agnostic interface —
`synthesize(text, voice)` returning PCM plus sample rate — with the engine
selected by environment variable. Nothing upstream of C4 may know which
engine is behind it. Swapping engines must be a config change, not a code
change.

THREE ITEMS CARRIED, none resolved here:

1. HeathenS advertises `stream_synthesize` with a `chunk_size`, which if
   real REVERSES DR-013's binding constraint that C4 must not assume
   incremental output. That claim is UNVERIFIED and must be measured
   before anything is designed against it — G2 is the precedent, in which
   a documented async generator yielded exactly one chunk. It gets its own
   gate with a bar fixed beforehand.
2. Glow-TTS runs at 22050 Hz against Kokoro's 24000 Hz, so C4's interface
   must carry the sample rate rather than assume it, and resampling to the
   HFP path is C4's responsibility.
3. HeathenS defaults its model cache to `HEATHEN_TTS_CACHE_DIR` under
   `~/.local/share` and downloads models on first use — a new shared
   per-user singleton, and a collision with DR-014's ruling that the
   appliance must not fetch weights at runtime.

Both (2) and (3) are recorded box-side in a companion session on
`jesterai`.

ALSO NOTED, NOT ADOPTED: HeathenS also ships an STT module built on
faster-whisper. C1 stays on faster-whisper called directly for D0.
Consolidating C1 onto HeathenS is a legitimate later question and is
explicitly out of D0 scope.
