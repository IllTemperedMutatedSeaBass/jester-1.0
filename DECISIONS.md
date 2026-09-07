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

## 2026-09-05 — Thread 1.0.6: model-tag mismatch found before build

### DR-019 — "gemma4:e4b" NEVER EXISTED ON THIS BOX; TRUE ANCHOR IDENTITY RECORDED (2026-09-05)

Every measured anchor on record — G1's prefix-reuse figures, G3's whisper
concurrency runs, the 10.5 s/106-record 2.x end-to-end cycle cited by
DR-006 and SEED §6 — names the model as "gemma4:e4b". Checking
`ollama list` on this box at the start of thread 1.0.6 found **no tag with
that exact name**. This is filed as a finding, not silently corrected,
because a mis-specified anchor is exactly G3(b)'s failure mode (DR-013)
and guessing a replacement would repeat it rather than avoid it.

**Tags actually present:** `gemma4:26b`, `nomic-embed-text:latest`,
`jester-gen:latest`, `gemma4-e4b-bakeoff:latest`. The last is the closest
name match and was checked with `ollama show gemma4-e4b-bakeoff:latest`
and `/api/show`:

- architecture: `gemma4` (i.e. the "Gemma 4" family, NOT "Gemma 3n" —
  these are different model generations; `gemma4-e4b-bakeoff:latest` is
  **not** a Gemma 3n E4B elastic model despite the "e4b" substring in its
  tag)
- parameter count: 7,518,069,290 (~7.5B), `size_label` "7.5B"
- quantization: Q4_K_M
- context length: 131072 (num_ctx pinned to 8192 in the Modelfile)
- license: `apache-2.0`, linked to the Gemma 4 license
- blob digest: `sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`

**This does not resolve to Gemma 3n E4B.** Per the standing instruction
that governed this check, no substitute tag is picked in its place.
**OLLAMA_MODEL is NOT pinned by this session.** Whether the historical
"gemma4:e4b" anchors (G1, G3, DR-006's 10.5 s cycle) were in fact measured
against this same `gemma4-e4b-bakeoff:latest` blob under an since-renamed
or since-retagged alias, or against a genuinely different model that no
longer exists on this box, is UNRESOLVED and is not this session's call —
it requires the operator's own record of what was pulled/tagged at the
time, which this session has no access to.

BINDING ON ALL FUTURE RECORDS: cite the model tag exactly as it exists on
the box at measurement time (`ollama list` / `ollama show`), never a
remembered or assumed short name. If a tag is retagged or re-pulled,
the record citing it becomes stale and must say so rather than silently
continuing to resolve.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

### DR-020 — OLLAMA_MODEL PINNED TO gemma4-e4b-bakeoff:latest; DR-019's parameter-count reasoning corrected; tag+digest citation made standing convention (2026-09-05)

DR-019 stands as written and is not edited. This entry corrects one piece
of its reasoning and settles the pin.

**CORRECTION TO DR-019.** DR-019 read the 7.5B parameter count as
disproving a Gemma 3n E4B identity. That inference is WRONG. In the Gemma
naming convention, "E4B" denotes approximately 4B **effective** parameters
achieved via per-layer embeddings offloaded from the main forward pass;
the raw on-disk checkpoint for an E4B model is itself approximately 7.5–8B
parameters. A 7.5B parameter count is therefore CONSISTENT with an E4B
checkpoint, not evidence against one. DR-019's parameter-count argument is
retracted; its residual anomaly — the tag's declared architecture is
`gemma4`, not `gemma3n` — is unresolved by this correction and is not
itself settled here.

**CHEAP EVIDENCE, gathered before writing any Stage 2 code:**

(a) `ollama show --modelfile gemma4-e4b-bakeoff:latest`:
```
FROM /usr/share/ollama/.ollama/models/blobs/sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f
TEMPLATE {{ .Prompt }}
RENDERER gemma4
PARSER gemma4
PARAMETER num_ctx 8192
PARAMETER stop <turn|>
```
The FROM line points at a **local blob path**, not a registry base tag —
there is no named upstream tag on this box to cross-check the "gemma4 vs
gemma3n" question against.

(b) Digest comparison across every pulled tag (`/api/show` FROM lines):
- `gemma4:26b` → `sha256-7121486771cbfe218851513210c40b35dbdee93ab1ef43fe36283c883980f0df` (different blob)
- `nomic-embed-text:latest` → `sha256-970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6` (different blob, unrelated model)
- `jester-gen:latest` → `sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f` — **SAME blob as `gemma4-e4b-bakeoff:latest`.**
- `gemma4-e4b-bakeoff:latest` → `sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`

**`jester-gen:latest` and `gemma4-e4b-bakeoff:latest` are two tags over the
identical weight blob** — confirming the anticipated "Modelfile wrapper
over the same blob" pattern, though this establishes only that the two
*current* tags are aliases of each other, not that either is the model
G1/G3 actually measured.

(c) Manifest mtime for `gemma4-e4b-bakeoff` under
`~/.ollama/models/manifests/`: **NOT OBTAINED.** That directory
(`/usr/share/ollama/.ollama/models/manifests/`) is owned by the `ollama`
service account and returned "Permission denied" to the `jester` user; no
sudo was authorised this session. This is a genuine gap, not a negative
result — it is recorded as unattempted-successfully, not as "no evidence
of an earlier pull."

**THE PIN.** `OLLAMA_MODEL=gemma4-e4b-bakeoff:latest`, resolving to blob
digest `sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`.
No fresh pull was performed or considered: re-pulling a tag can silently
change what it resolves to, which would trade a known, fixed, if
unprovenanced blob for an unknown one — a strictly worse position for
comparability with G1, G3 and the 10.5 s 2.x cycle, for no offsetting gain.

**STANDING CONVENTION, the durable part of this entry.** From now on,
every measured figure in this stream cites BOTH the model tag AND its
blob digest (`sha256-...`, from `ollama show`/`/api/show`'s FROM line or
equivalent). A tag is mutable — it can be retagged, re-pulled, or aliased,
as (b) just demonstrated in miniature — and only the digest is a fixed
identity. Historical entries (G1, G3, DR-006's 10.5 s cycle, DR-013) that
cite only "gemma4:e4b" cannot be retroactively completed with a digest
they never recorded; they remain identity-unverified, per below.

**WHAT REMAINS UNPROVEN.** Neither (a) nor (b) nor (c) establishes that
digest `sha256-90ce9812...` is the model G1, G3, and the 2.x 10.5 s cycle
actually ran against. (a) offers no upstream tag to check against; (b)
shows two current tags are aliases of each other but says nothing about
what existed under the name "gemma4:e4b" historically; (c) could not be
read at all. The honest position, stated plainly and not resolved by
assertion: **D0's Bar B figure is anchored to digest
`sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`,
under the tag `gemma4-e4b-bakeoff:latest`, and any comparison to G1's,
G3's, or the 2.x cycle's historical figures carries an unverified-identity
assumption.** Whether that assumption holds is not this session's call —
it would need the operator's own record of what was pulled and tagged at
the time G1/G3 ran.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

## 2026-09-05 — Thread 1.0.6: live carve reading found NOT 16 GiB while building the Bar B harness

### DR-021 — LIVE UMA CARVE DOES NOT MATCH THE DOCUMENTED "16 GiB CURRENT"; FLAGGED, NOT ACTED ON (2026-09-05)

While building the Bar B harness's `read_uma_carve_bytes()` (which reads
`/sys/class/drm/card*/device/mem_info_vram_total`, the same method
`jesterai/box/HARDWARE.md` §2/§3 used to confirm "16 GiB (INTERIM)"), the
live reading on this box right now is **2147483648 bytes = 2 GiB**, not
16 GiB. This is reported as a finding, not corrected or acted on — no
carve change was made, attempted, or is proposed here, per the standing
instruction that D0 builds and measures at whatever carve is actually in
force and does not touch the BIOS.

**Evidence gathered (read-only):**
- `cat /sys/class/drm/card0/device/mem_info_vram_total` → `2147483648`
  (2 GiB), the only card present (`card0`, vendor `0x1002`/AMD).
- `journalctl -k` at the current boot (system up since 2026-09-04
  ~18:02, no reboot since — confirmed via `uptime -s`): `amdgpu
  0000:c5:00.0: VRAM: 2048M ... [drm] Detected VRAM RAM=2048M, BAR=2048M`
  and `2048M of VRAM memory ready` / `14600M of GTT memory ready`.
- `journalctl -u ollama`, consistently from boot (18:02) through the most
  recent restart (06:25 the following day): `msg="inference compute" ...
  type=iGPU total="14.3 GiB"` — Ollama's own reported compute total is
  14.3 GiB, not 16 GiB, and has been since this boot.
- `free -h`: system RAM total **28Gi**, not the ~15 GiB `box/HARDWARE.md`
  §2 records for a 16 GiB carve, nor the ~6.9 GiB recorded for a 24 GiB
  carve.

**Reading, offered but not asserted as settled.** This pattern — a small
fixed VRAM BAR (2 GiB) plus a much larger GTT pool (14.6 GiB) that Ollama
reports as its usable compute total (14.3 GiB) — is consistent with the
BIOS now being set to a **small "Specified" UMA value** (e.g. 2G) rather
than 16G or 24G, with the rest of the unified memory served dynamically
through GTT. This is plausibly a direct consequence of the same-day BIOS
Auto/Specified exploration recorded in the "UMA carve ladder corrected"
entry above (this box has not rebooted since 2026-09-04 18:02, which is
consistent with, but does not by itself prove, that exploration being the
cause) — offered as the likely explanation, not confirmed, since this
session has no record of what the operator actually left the BIOS set to.

**Consequence for the harness.** `read_uma_carve_bytes()` still reads
`mem_info_vram_total` because that is the exact method `HARDWARE.md`
itself uses and the only one available without `rocm-smi`/`amd-smi`
(neither installed, per §3). This entry records that the figure it will
report may not mean what earlier entries assumed it means once GTT is
substantially in play: **`mem_info_vram_total` and "the model's actual
usable compute memory" are not reliably the same number under this
driver, at least at a small BAR / large-GTT carve.** Bar B's harness will
report whatever this sysfs path says at run time — which is the honest,
non-guessed answer — but the operator should confirm what the BIOS is
actually set to before trusting that figure as "the carve," and should
restore the intended value before an actual D0 measurement run if 2 GiB
was not the intended state.

**NOT resolved here:** whether 2 GiB is a deliberate leftover from BIOS
exploration, an intended new value, or an unintended one. **NOT acted on
here:** no BIOS change was made, attempted, or proposed by this session.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

## 2026-09-05 — Thread 1.0.7: live carve reading still 2 GiB; operator's 24 GiB claim not reflected live

### DR-022 — LIVE UMA CARVE STILL 2 GiB; NEITHER THE DOCUMENTED 16 GiB NOR THE OPERATOR-STATED 24 GiB; FLAGGED, NOT ACTED ON (2026-09-05)

Thread 1.0.7 was told to read the live carve fresh (not reuse DR-021's
figure) because the operator now states the BIOS is set to 24 GiB, and to
report all three numbers alongside the Bar B record. Bar A item 5 did not
run to completion this session (see RELAY.md STOP report), so there is no
Bar B record to attach this to; it is recorded here instead.

**The three figures:**
- Documented (`jesterai/box/HARDWARE.md` §2, "16 GiB (INTERIM)"): 16 GiB.
- Operator-stated, this session: 24 GiB.
- Live, read this session: `cat /sys/class/drm/card0/device/mem_info_vram_total`
  → `2147483648` bytes = **2 GiB** — identical to DR-021's reading from
  thread 1.0.6, taken on the same uninterrupted boot (`uptime -s` still
  shows 2026-09-04 ~16:02 this session; no reboot has occurred between
  DR-021 and this entry).

**Reading.** The live figure has not moved since DR-021, across a change
in operator's stated BIOS value from (implicitly) 16 GiB to 24 GiB. Since
BIOS UMA carve changes require a reboot to take effect and this box has
not rebooted, an unchanged live reading following a stated BIOS change is
the expected result, not a new anomaly — it is consistent with DR-021's
prior finding that this box's `mem_info_vram_total` does not reflect the
BIOS carve setting without an intervening reboot regardless of which
value is set. This does not resolve DR-021; it is additional evidence for
the same open question.

**NOT resolved here:** what the BIOS is actually set to, or why a reboot
has not been taken. **NOT acted on here:** no BIOS change or reboot was
made, attempted, or proposed by this session, per the standing
instruction that the carve is not to be touched.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

## 2026-09-05 — Thread 1.0.8: live turn 1 run reaches C2, C2's raw-prompt call to Ollama returns empty text against this Modelfile's PARSER, turn 1 crashes C4/C5

### DR-023 — `c2_reason`'s `/api/generate` RAW-PROMPT CALL RETURNS EMPTY `response` AGAINST THIS MODEL'S `RENDERER gemma4`/`PARSER gemma4`; `/api/chat` DOES NOT. FLAGGED, NOT FIXED — DESIGN QUESTION, NOT A ONE-LINE BUG.

With the CX 6.00BT headset connected on HFP/mSBC this session, `ops/run_d0.sh`
got further than 1.0.7: C1 captured live speech and transcribed it
(`asr_done`, `transcript_chars: 36`), C2 prefilled and generated (`eval_count:
40`, hit the cap, `done_reason: "length"`) — but C2's `RespondResponse.text`
was the empty string, which C5 forwarded to C4's `/synthesize?text=`, which
5xx'd (`kokoro_onnx` raises `ValueError: need at least one array to
concatenate` on empty text), which raised in C5's `raise_for_status()` with
no per-turn error handling, killing the whole ten-turn loop after turn 1.

**Cheap evidence gathered (read-only, no code changed):**

(a) Direct `curl` to `/api/generate` with a prompt shaped like C2's actual
stable-prefix prompt (`"You are Jester, a meeting assistant...\n\nhuman:
hello there, how are you today"`), `num_predict: 40`: `"response": ""`,
`"done_reason": "length"` — reproduces the empty-text symptom exactly,
independent of C1/C4/live audio content.

(b) Same model, same 40-token cap, via `/api/chat` with a single user
message instead of a raw prompt string: `"message": {"content": "I'm doing
well, thank you for asking! As an AI, I don't experience feelings..."}` —
non-empty, coherent, ordinary chat completion.

**Reading.** The Modelfile pinned under DR-020 sets `RENDERER gemma4` /
`PARSER gemma4`, which is a chat-templating and (most likely) an
output-channel parser, not a raw-completion passthrough. `c2_reason`'s
`ollama_client.generate()` calls `/api/generate` with a hand-built raw
prompt string (`PromptBuilder`'s stable-prefix-plus-append design, DR-013a/b),
bypassing that template. Against this Modelfile, the raw-prompt path appears
to spend the full generation budget on parser-recognized non-final content
(most plausibly a channel/scaffold format PARSER gemma4 expects and strips
before exposing `response`), leaving the exposed `response` field empty at
the current 40-token cap even though tokens were genuinely generated
(`eval_count: 40` both times). This is not evidence about *what* the hidden
content is — no attempt was made to decode the raw `context` token IDs
returned by `/api/generate` — only that `/api/chat` against the same model
and the same token budget does not exhibit the symptom.

**NOT fixed here — this is a design question, not a one-line bug.** Two
architectures are in tension: `c2_reason.prompt.PromptBuilder`'s
stable-prefix-plus-append raw string (built specifically so a fixed prefix
stays cache-stable across turns, per DR-013a) versus `/api/chat`'s
per-message list, which does not obviously preserve the same cache-prefix
property this Modelfile/engine combination was chosen for. Switching C2 to
`/api/chat` without checking whether that breaks the prefix-caching
rationale DR-013a exists for would be trading one unverified assumption for
another. This needs an operator ruling before Stage 2 code changes, the same
way DR-019/DR-020 needed one for the model pin itself.

**Consequence for this session.** Bar A item 5 is NOT proven (see RELAY.md
STOP report) — the loop reached and crashed inside turn 1, on a different
and more specific failure than 1.0.7's (which never got past C1 for lack of
live audio). Bar B was not attempted, per its stated conditional on Task 3
proving the loop runs.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

## 2026-09-05 — Thread 1.0.9: DR-023 settled — raw /api/generate with hand-rendered Gemma turn markers, `raw: true`

### DR-024 — C2 MOVES TO `/api/generate` + `raw: true` WITH HAND-RENDERED GEMMA TURN MARKERS; `/api/chat` MEASURED AND REJECTED (both preserve prefix reuse; only one avoids the empty-response symptom) (2026-09-05)

DR-023 left this open as a design question rather than a one-line fix. This
entry settles it with a measured G1-style micro-check, per the operator's
instruction, before choosing.

**METHOD.** For each candidate path, two calls were issued against the
live, pinned `gemma4-e4b-bakeoff:latest` (blob digest
`sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`,
per DR-020): call 1 against a ~5,000-token stable-prefix transcript (cold),
call 2 against the same transcript with ~200 tokens appended at the end
(the append point G1/DR-013a require). `num_ctx=8192`, `num_predict=40`
(the pinned Bar B cap) throughout. Delta prefill is call 2's
`prompt_eval_duration`; G1's bar is <1.5 s.

**PATH (a) — `/api/generate`, `raw: true`, prompt hand-wrapped in
`<start_of_turn>user\n...<end_of_turn>\n<start_of_turn>model\n`:**
call 1 (cold, 5396 prompt tokens): `prompt_eval_duration` 8.864 s (cold
prefill, as expected — not the figure the bar applies to). Call 2 (5639
prompt tokens, +~200 appended): `prompt_eval_duration` **0.548 s** — PASSES
the 1.5 s bar, cache hit confirmed. Response was non-empty on every call in
this session testing this path (multiple independent invocations, both the
short single-line micro-check in DR-023's own evidence and this session's
5k-token version): e.g. `"Seems like we've covered quite a bit! Shall we
summarize key takeaways or move onto action items?"`, `done_reason:
"stop"`.

**PATH (b) — `/api/chat`, one system + one user message, server-side
templated:** call 1 (cold, 5384 prompt tokens): `prompt_eval_duration`
1.982–8.294 s across repeated runs (cold prefill, load-time variable, not
the bar figure). Call 2 (5627 prompt tokens, +~200 appended):
`prompt_eval_duration` **0.538–0.577 s** — ALSO passes the 1.5 s bar,
cache hit confirmed. **But `message.content` was empty on the 5k-token
call** (`done_reason: "length"`, all 40 tokens consumed), with a populated
`message.thinking` field visible in the full response body (`"Thinking
Process:\n\n1. **Analyze the Request:**..."`, cut off mid-sentence by the
cap). A smaller, single-line-transcript `/api/chat` call earlier in this
investigation (no 5k-token filler) did return non-empty `content` within
the same 40-token cap — the symptom is content/length-dependent, not a
flat pass/fail on the endpoint itself.

**READING.** Both paths preserve KV-cache prefix reuse — this is not what
distinguishes them. The empty-response symptom DR-023 found is NOT
specific to `/api/generate`: `/api/chat`'s server-side renderer
(RENDERER/PARSER `gemma4` in the pinned Modelfile) puts the model into an
unbounded "thinking" mode that can consume the entire 40-token cap before
producing any final-channel content, and whether it does so is sensitive
to prompt content/length in a way this session did not fully
characterize. Hand-rendering the Gemma turn markers directly and sending
with `raw: true` bypasses that renderer entirely — the model completes
the turn directly, without entering the thinking scaffold, in every
observed case.

**CHOICE: Path (a).** `/api/generate` + `raw: true` + hand-rendered Gemma
turn markers. Reasoning: it is the only path that reliably keeps output
within the pinned 40-token cap across the content this session tested; a
correct, fast prefill is worthless to Bar B if the field it prefills for
comes back empty. `/api/chat`'s thinking-mode risk under load is not ruled
out as content grows toward the real transcript lengths D0 will see.

**DR-013a STILL HOLDS.** The Gemma turn-close markers
(`<end_of_turn>\n<start_of_turn>model\n`) are appended as a fixed suffix
AFTER the (evidence-extended, if any) rolling transcript, never before it
— `c2_reason.prompt.PromptBuilder.build()` still appends evidence after
the transcript and only then closes the turn. This is the same ordering
G1 and DR-013a measured; nothing about the turn-wrapping changes it.

**IMPLEMENTED.** `c2_reason/src/c2_reason/prompt.py`:
`PromptBuilder.build()` now wraps the stable-prefix-plus-evidence body in
`<start_of_turn>user\n...<end_of_turn>\n<start_of_turn>model\n`.
`c2_reason/src/c2_reason/ollama_client.py`: `generate()` now sends
`"raw": true` to `/api/generate`. No other files changed. No project
tests existed for either module to run against this change (confirmed by
search before editing).

**NOT settled here:** the precise mechanism by which `/api/chat` enters
thinking mode on longer content (no attempt was made to decode or
suppress it via an Ollama-level "think" option, since path (a) sidesteps
the question rather than needing an answer to it), and whether `raw: true`
`/api/generate` could itself enter a similar mode on sufficiently long or
different content than what this session's micro-check covered — that
risk is carried forward, not closed, and Bar B's live 20-turn run (this
same thread) is the next real test of it against actual conversational
content rather than filler.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

### DR-025 — LIVE UMA CARVE SETTLED AT 2 GiB (DR-021's discovered-value principle; box/HARDWARE.md's 16 GiB and the operator's 24 GiB recollection are NOT corrected here) (2026-09-05)

Read a fourth time this session (`cat
/sys/class/drm/card0/device/mem_info_vram_total` → `2147483648` bytes = 2
GiB), attached to this thread's live Bar B run. Three prior readings — DR-021
(thread 1.0.6), thread 1.0.7, thread 1.0.8 — all read the identical value,
all on the same uninterrupted boot (`uptime -s` → 2026-09-04 16:02:49,
unchanged across all four readings). Per the operator's own framing this
session, three (now four) consistent instrument readings against a
recollection favour the instrument. **The live carve is 2 GiB, settled, per
DR-021's discovered-value principle — not assumed, not corrected against
documentation.**

`box/HARDWARE.md`'s documented "16 GiB (INTERIM)" and the operator's stated
24 GiB are NOT edited or reconciled here — this entry is scoped to what the
live sysfs figure is, not to why it disagrees with either. Whether that
disagreement is a stale BIOS setting never actually applied without a
reboot (DR-022's reading), a driver/GTT artifact (DR-021's suspicion), or
something else remains open and is not this session's business — the carve
was not touched.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

### DR-026 — BAR B RE-ANCHORED AT LIVE 16 GiB CARVE; CARVE-VS-GTT RESIDENCY FAVOURS "CARVE WAS BINDING"; TWO C2-OUTPUT ANOMALIES RECORDED (2026-09-07)

**Configuration this figure is anchored to.** Live UMA carve
`/sys/class/drm/card1/device/mem_info_vram_total` → `17179869184` bytes =
**16.0 GiB**, matching `box/HARDWARE.md` §2 for the first time since
DR-021 (see `jesterai/DECISIONS.md` 2026-09-07 entry). Kernel
`7.0.0-31-generic`. Model unchanged, per DR-020's pin:
`gemma4-e4b-bakeoff:latest`, blob digest
`sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`,
confirmed both from `ollama show --modelfile` and from the actually-running
`llama-server` process's `--model` argument. Headset on `headset-head-unit`
(HFP), codec `msbc`, confirmed via `ops/ensure_hfp.sh` at launch (see the
harness-restructuring commit this same thread, a641163, for why that
verification exists and what it found: the profile does not survive idle
periods and must be re-asserted before every run).

**Bar B figure (20/20 turns, operator-run, spoken, via
`ops/run_d0.sh --turns 20` with `C5_TRANSCRIBE_TIMEOUT_S=300`).** Computed
by `c5_orchestrator.bar_b_harness` against `logs/{c1,c2,c4,c5}.jsonl`:

- **T_ttfa median: 3.076 s. p90: 4.959 s.** Kill switch (median > 8 s): NOT
  fired.
- Per-stage medians: ASR tail 0.757 s · C2 prefill 0.284 s · C2 generate
  0.975 s · TTS 0.916 s · playout 3.906 s (playout is not part of T_ttfa,
  which is measured to `playout_start`, not `playout_done`).
- 40-token cap: `max_tokens_cap=40` on every turn per DR-013/DR-024's
  pinned generation config. One turn (turn 18, `eval_count=40`) hit the cap
  exactly — its reply was truncated mid-generation. `eval_count` ranged
  8–40 across the 20 turns (median ~18), so turn 18 is the only turn where
  the cap itself, not natural sentence length, ended generation.

**Comparison against 1.0.9's 4.28 s median / 5.84 s p90 at a 2 GiB carve:**
median improved by ~1.2 s (28%), p90 by ~0.9 s (15%). This is directionally
consistent with "the carve was binding at 2 GiB" rather than "ROCm was
already drawing on GTT and the carve was never the constraint" — but see
the residency evidence below before weighting this conclusion; the T_ttfa
comparison alone, across a single pair of runs with different utterances,
is suggestive, not proof.

**Carve-vs-GTT residency, with the model loaded (method: sysfs, not
rocm-smi — no `rocm-smi`/`rocminfo`/`amd-smi` binary exists on this box,
confirmed by `which` and a filesystem search; this repeats
`box/HARDWARE.md` §3's standing finding).**
`/sys/class/drm/card1/device/mem_info_vram_used` → `4575764480` bytes ≈
**4.26 GiB** resident in the dedicated carve.
`/sys/class/drm/card1/device/mem_info_gtt_used` → `52367360` bytes ≈
**0.049 GiB (~50 MiB)** in GTT. `ollama ps` at the same moment: two models
resident, `jester-gen:latest` (same blob digest as
`gemma4-e4b-bakeoff:latest` — confirmed via `ollama list`'s shared model ID
`9f626629a870`) and `nomic-embed-text:latest`, both reported "100% GPU."

**Reading, and how strongly it's held.** At 16 GiB, essentially the entire
model footprint sits in the dedicated carve; GTT usage (~50 MiB) is
negligible and not plausibly where model weights live. At a 2 GiB carve,
the same model (whose resident footprint here is ~4.26 GiB, larger than
2 GiB outright) could not have fit in dedicated VRAM alone and must have
drawn on GTT/shared system RAM to some degree — consistent with DR-021's
own caveat that a small VRAM BAR does not mean a small "compute total."
Taken together with the observed T_ttfa improvement, this **favours "the
carve was binding at 2 GiB"** over "ROCm was already using GTT and the
carve was never the constraint" — moderately strongly, on the logic that a
mechanism (spillover to slower shared memory) is directly evidenced by the
residency figures and points the same direction as the outcome (faster
T_ttfa). It is not proof: this is one carve-change event, one pair of Bar B
runs with different spoken content and turn counts of complete data, and no
residency figure was captured live at the 2 GiB carve itself (thread 1.0.9
did not measure GTT/VRAM split) to compare directly against this thread's
16 GiB figures. A future measurement at an intermediate carve (matching
DR-025's now-confirmed 512M–24G ladder) would be a stronger test than
another run at either endpoint.

**Anomaly 1 — turn 9's leaked `<end_of_turn>` marker (DR-024).** The
operator reported turn 9's synthesized text ended with a literal
`<end_of_turn>` string — DR-024's hand-rendered Gemma turn markers are
appended as a fixed suffix on the prompt side (`c2_reason.prompt`), but
nothing on the response side strips a stop-token string the model itself
emits as literal output text when `/api/generate` with `raw: true` doesn't
suppress it as a stop sequence. Investigated against the logs: turn 9's
`eval_count` was 20 tokens (run range: 8–40, median ~18) and its
`c2_generate_s` was 1.060 s, both unremarkable against the rest of the run
— not the extreme value (that's turn 18's cap-hit at 40 tokens/1.754 s).
Turn 9's own T_ttfa (2.885 s) is *below* the run's median (3.076 s), not an
outlier. **Verdict: RETAIN turn 9 in the figure, anomaly noted, not
excluded.** The leaked marker cost a handful of tokens against a run where
token counts already range 8–40 for other reasons (varying reply length);
it is not visibly distorting this turn's contribution to the aggregate,
and dropping a turn from n=20 without a measurable effect to justify it
would be the less honest choice. Filed against DR-024: the raw-generate
path's stop-sequence handling for the literal `<end_of_turn>` string is
unresolved and should be addressed (add it as an explicit Ollama `stop`
sequence) before it appears in user-facing output rather than only in a
measurement run.

**Anomaly 2 — emoji and stage directions in C2's output, and Kokoro's
handling of them.** Investigated directly (not inferred): calling
`KokoroEngine.synthesize()` with matched test strings shows Kokoro does
**not** silently drop emoji or asterisk-delimited stage directions — it
voices them, materially inflating output audio duration. Measured:
"Sure, happy to help with that today." → 1.899 s. Same text plus
`*Giggles softly*` → 3.883 s (+104%). Plus a single `✨` → 2.880 s (+52%).
Plus `🎭` → 2.987 s (+57%). Because both C2's full generation (all tokens,
including any emoji/stage-direction tokens) and C4's full TTS synthesis
complete *before* `playout_start`, this is not a cosmetic issue confined to
audible playback — it sits inside the T_ttfa critical path on both the
token-count side (C2 must decode the extra tokens before returning text)
and the synthesis-time side (Kokoro must process the extra characters
before audio is ready). The measured T_ttfa this run is real, not
fabricated, but it is not the T_ttfa a system prompt that suppressed
emoji/stage-directions would produce — it is somewhat inflated by output
the system should not be generating in a voice-only channel. Not fixed
here: changing C2's system prompt now would void this session's own
figure. **Recorded in `BACKLOG.md`**, not fixed silently, per instruction.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

---

## 2026-09-07 — Thread 1.0.11: decomposition audit, emoji suppression, re-anchor

### DR-027 — Decomposition audit closes clean; DR-024 stop-sequence gap closed; emoji/stage-direction suppression added at both C2 and C4 (2026-09-07)

**Decomposition audit (Task 2).** 1.0.10's reported medians (ASR tail
0.757 s, C2 prefill 0.284 s, C2 generate 0.975 s, TTS 0.916 s, playout
3.906 s, against T_ttfa median 3.076 s) read as impossible because playout
alone exceeds the total. Read `decompose_turn()`
(`c5_orchestrator/src/c5_orchestrator/bar_b_harness.py`) and the C5 log
emission points (`c5_orchestrator/src/c5_orchestrator/playback.py`) to
establish ground truth:

- `t_ttfa_s = playout_start.monotonic_ts - endpoint.endpoint_monotonic_ts`.
  `playout_start` is logged at first-PCM-frame-write time (confirmed in
  `playback.py`'s own docstring: "Logs playout_start at first-frame-write
  time -- that is the T_ttfa..."), matching DR-017's definition exactly.
- `playout_s = playout_done.monotonic_ts - playout_start.monotonic_ts`,
  i.e. end-of-audio minus first-frame -- this is POST-T_ttfa by
  construction and was already excluded from `t_ttfa_s` in the code.
- The four stages that DO partition T_ttfa are sequential:
  `asr_tail_s` (endpoint -> asr_done), `c2_prefill_s` (prefill_start ->
  prefill_done), `c2_generate_s` (prefill_done -> generate_done), `tts_s`
  (synth_start -> synth_done).

Verified per-turn against all 20 of 1.0.10's backed-up log lines (see
below): summing the four partition stages per turn and comparing against
that turn's own `t_ttfa_s` gives a gap of 5-37 ms per turn (median 6 ms,
mean 9 ms) -- a genuine, near-exact sequential partition, not a
mislabelling. **Verdict: the code and the DR-017 T_ttfa definition were
already correctly applied; nothing was mismeasured or mislabelled at the
timestamp/field level, and `DECISIONS.md`'s 1.0.10 entry already carried
the correct caveat in prose** ("playout is not part of T_ttfa, which is
measured to `playout_start`, not `playout_done`"). The apparent
contradiction in this thread's prompt (summed stage *medians* of
0.757+0.284+0.975+0.916=2.932 s vs. playout's 3.906 s, against a 3.076 s
T_ttfa) is an artifact of comparing summed medians against a separately
computed median of the total -- medians do not add across a set of turns
with different individual timings, so that comparison was never valid
arithmetic, independent of whether the underlying measurement was correct.
1.0.10's **3.076 s / 4.959 s figure stands unchanged and is not
superseded by this audit** (Task 4's re-anchor below supersedes it for an
unrelated reason -- the emoji/stage-direction suppression change).

The one real defect found was presentational, not a measurement error:
`playout_s_median` was listed in `summarize()`'s output alongside the four
true partition members with no subtotal or partition-membership marker,
which is genuinely liable to make a reader eyeball it as a fifth term.
Fixed in `bar_b_harness.py`: `summarize()` now emits
`partition_gap_median_s` / `partition_gap_max_s` (the direct per-turn
partition-validity check above) and renames the playout figure to
`post_ttfa_playout_s_median` with a docstring explaining why it is
reported separately. Re-running `summarize()` against 1.0.10's own backed
-up logs reproduces the original figures exactly (t_ttfa_median_s =
3.076412712000092, t_ttfa_p90_s = 4.9590917236998395), confirming the fix
is presentational only -- no timestamp, event, or arithmetic changed.

1.0.10's logs were copied to `logs_1.0.10_backup/` (gitignored, not
committed) before any of this session's code changes or runs, per
instruction not to risk them; the original `logs/{c1,c2,c4,c5}.jsonl`
files were left untouched and are superseded only by the run_d0.sh log
-path fix below, not deleted.

**Emoji, stage-direction, and control-marker suppression (Task 3).**
DR-020's Anomaly 2 measured Kokoro voicing emoji and asterisked stage
directions aloud rather than dropping them (52-104% synthesis-time
inflation in test) and DR-024 left the raw-generate path's
`<end_of_turn>` stop-sequence handling as an open gap after it leaked into
turn 9's spoken output. Both closed here, independently, at both ends of
the pipeline:

- **C2 prompt (`c2_reason/src/c2_reason/prompt.py`, `STABLE_PREAMBLE`).**
  Before:
  > "You are Jester, a meeting assistant. Respond briefly and naturally to
  > the ongoing conversation below.\n\n"

  After:
  > "You are Jester, a meeting assistant. Respond briefly and naturally to
  > the ongoing conversation below. Your reply is spoken aloud, not read:
  > never include emoji, asterisked stage directions (e.g. *laughs*), or
  > parenthetical narration -- write only the words to be spoken.\n\n"

  This is a fixed addition to the stable preamble (still constant across
  turns), so it does not disturb DR-013a's append-after-transcript
  ordering or G1's cached-prefix property.

- **C2 stop sequence (`c2_reason/src/c2_reason/ollama_client.py`,
  `generate()`).** `raw: true` (DR-024) bypasses Ollama's normal chat
  -renderer stop-token handling, so `<end_of_turn>` was never registered
  as a stop sequence on the raw-generate call and could leak into output
  text verbatim if the model emitted it. Added `"stop": ["<end_of_turn>"]`
  to the `options` dict on the `/api/generate` call. **This closes
  DR-024's stop-sequence gap.**

- **C4 defensive filter (`c4_speech/src/c4_speech/text_filter.py`, new
  module; wired into `c4_speech/src/c4_speech/main.py`'s `/synthesize`
  handler).** `strip_unspeakable()` strips emoji, asterisk-delimited stage
  directions, parenthetical narration, and complete-or-cap-truncated
  Gemma control markers (`<end_of_turn>` and a truncated prefix such as
  `<end_of_tur` at end-of-string, covering the case where a 40-token cap
  cuts generation off mid-marker -- DR-020 recorded exactly one turn,
  turn 18, hitting that cap) before text reaches `engine.synthesize()`.
  This is deliberately independent of whatever C2's prompt asks the model
  to avoid, per the instruction to fix this defensively at both ends: it
  holds even if a future prompt change or model swap regresses C2's own
  output. `/synthesize` now logs `stripped` (bool), `raw_len`,
  `filtered_len` on `synthesize_start` -- not the raw text itself, kept
  consistent with the rest of this repo's structured logs, which never
  store transcript content -- so a future run can distinguish "the median
  moved because fewer turns needed stripping" from ordinary variance.

  **Unit tests** (`c4_speech/tests/test_text_filter.py`, 10 cases, run via
  a plain-Python runner since `pytest` is not installed in `c4_speech`'s
  venv -- `python3 -m unittest` does not collect bare pytest-style
  functions and installing a new dependency was out of scope for a filter
  fix): plain text passes through untouched; the four DR-020 anomaly
  strings (`*Giggles softly*`, a lone `✨`, a lone `🎭`, and the baseline
  sentence they were appended to) are stripped correctly; a complete
  `<end_of_turn>` marker and a cap-truncated `<end_of_tur` prefix are both
  stripped; parenthetical narration is stripped; a combined string
  carrying all four classes at once collapses to the intended spoken
  text; ordinary punctuation (`3:30 --`) and a bare mid-sentence `<` (not
  at end-of-string) are left untouched, guarding against
  over-stripping. **10/10 passed.**

  **Live wiring smoke-checked** (not just unit-tested) by starting C2 and
  C4 directly on alternate ports (8102/8104) and driving two turns
  through the real pinned model and real Kokoro engine: a real C2
  response ("Hello there.") passed through C4 unmodified
  (`stripped: false`); a hand-crafted string combining all four classes
  (`"Sure! 🎭 *laughs* (winks) Happy to help.<end_of_turn>"`, 52 chars) was
  filtered to `"Sure! Happy to help."` (20 chars, `stripped: true`) and
  synthesized to valid WAV audio (200 OK, non-zero byte count) in both
  cases. Both smoke processes were killed cleanly afterward; no residual
  processes were left running.

**Re-anchor (Task 4).** `ops/run_d0.sh` truncated `logs/{c1,c2,c4,c5}.jsonl`
via `>` redirection on every invocation, so a second run silently destroyed
the first run's figures -- a one-mistyped-command-away data-loss risk.
Fixed: each invocation now creates `logs/run_<UTC timestamp>/` and writes
there; `logs/latest` is refreshed as a symlink (never a copy) to the most
recent run directory for convenience. `bar_b_harness.py`'s `--log-dir`
default was changed from `logs` to `logs/latest` to match. `.gitignore`
gained `logs_*_backup/` alongside the existing `logs/` so this thread's
backup directory (and any future one) is never accidentally committed.

The fresh Bar B run itself is **operator-run, not CC-run**, per
thread-1.0.6's standing ruling and this thread's explicit instruction not
to drive the spoken run or relay prompts through chat. The exact handoff
command and log destination are printed in this session's STOP report in
`RELAY.md`, not repeated here.

**Carried forward unchanged, not re-verified this session:** model pin
(`gemma4-e4b-bakeoff:latest`, digest
`sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`),
live carve (16.0 GiB), kernel (`7.0.0-31-generic`). None of Task 1-4's
work touched the model, the carve, or the kernel -- confirmed by reading,
not by re-measuring, since the instruction was explicitly not to change
either.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

---

## 2026-09-07 — Thread 1.0.11 (continued): live spoken run's two defects investigated, Bar B provisionally NOT re-anchored

### DR-028 — Preamble-leak defect found and fixed (C2 + independent C4 backstop, both verified live); connection-reuse/repetition defect explained as benign D0 behaviour, not a bug; this run's figure held provisional pending a clean re-run (2026-09-07)

**Context.** The operator ran `ops/run_d0.sh --turns 20` after DR-027's
changes; logs are in `logs/run_20260907T095156Z/`. Emoji/stage-direction
suppression (Task 3) worked as intended -- confirmed by the operator. Two
defects were reported for investigation before trusting a figure from
this run.

**Defect 1 -- prompt leakage (BLOCKING, now fixed).** Turns 6 and 9
(ordinal position in the run; `turn_id`s `c4bdaddc...` and `c37313d3...`)
synthesized a 40-token-cap-truncated copy of `STABLE_PREAMBLE` instead of
a reply, confirmed against `c2.jsonl`: both are the only two turns in the
run with `eval_count == max_tokens_cap == 40`.

*Root cause, established by live reproduction, not guesswork.* Started
`c2_reason` directly and drove it through two stress sequences of short,
repetitive filler lines (`"This is turn one."` ... `"This is turn
twenty-five."`), approximating what a 20-turn timing-calibration script
plausibly sounds like (short, information-free, differing only by a
number word). The pre-fix code leaked the literal preamble verbatim,
cap-truncated at 40 tokens, on the first attempt (turn 9 of a 25-line
sequence) -- eval_count=40, matching the field signature exactly. A
second, independent sequence reproduced it again. Mechanism: `raw: true`
(DR-024) gives no chat-template-enforced turn boundary; the operator's
hypothesis was right in substance -- with nothing else compelling the
model to treat `<start_of_turn>model\n` as a hard boundary, and with an
increasingly repetitive, information-free transcript (no assistant-turn
history is ever appended -- `c2_reason.main.respond()` only calls
`prompt_builder.append_transcript_line` for the human side -- and no
retrieval yet, DR-013b), the model drifts into degenerate completion:
first repeating near-identical short replies, then occasionally copying
nearby prompt text verbatim, including the preamble sitting at the top of
the same prompt. This session's own `stop: ["<end_of_turn>"]` (DR-027)
only catches the LITERAL string if the model emits it; it does not stop a
continuation that never attempts to close the turn, so generation runs to
the 40-token cap instead -- consistent with both leaked turns hitting the
cap exactly.

*Fix, three parts:*
1. **Recency-placed mitigation** (`c2_reason/src/c2_reason/prompt.py`): a
   short fixed reminder -- "(Reply now with your own new words,
   addressing what was just said. Do not repeat or restate the
   instructions above.)" -- is now appended fresh after the
   transcript/evidence and immediately before the closing turn markers on
   every call, kept deliberately separate from `STABLE_PREAMBLE` so it
   stays adjacent to the generation point regardless of transcript
   length (raw-mode completion weights nearby context more heavily than
   distant context).
2. **C2-side detection and replacement** (`c2_reason/src/c2_reason/main.py`,
   `_strip_leaked_preamble`): if the model's response starts with the
   normalized signature phrase "you are jester, a meeting assistant"
   (`PREAMBLE_LEAK_SIGNATURE`, exported from `prompt.py`) -- matched as a
   prefix, not full equality, since a leak can be truncated anywhere by
   the token cap -- the response is replaced with a fixed fallback
   ("Sorry, could you say that again?") and a new `preamble_leak_detected`
   event is logged with `raw_eval_count`/`cap_hit`, so future runs can
   count occurrences directly instead of relying on the operator noticing
   audibly.
3. **C4-side independent backstop** (`c4_speech/src/c4_speech/text_filter.py`,
   `is_preamble_leak`/`strip_unspeakable`): carries its own copy of the
   same signature (components are HTTP-only per project-structure
   discipline, so this is duplicated by hand, not imported) and strips a
   detected leak to `""`. `c4_speech/src/c4_speech/main.py` now guards
   against empty filtered text by skipping the TTS engine call entirely
   and returning a minimal valid silent WAV (1 sample) rather than
   calling `engine.synthesize("")`, whose behaviour on empty input was
   untested. `synthesize_start` now also logs `preamble_leak_detected`.

*Verification, both synthetic and live:*
- Unit tests: 4 new cases added to `c4_speech/tests/test_text_filter.py`
  (detects a full leaked preamble, detects a cap-truncated one, strips
  both to `""`, and confirms ordinary replies -- including one that also
  starts with the words "you are" -- are never false-flagged).
  **14/14 passed** (up from 10/10 in the prior commit).
- Live re-test of the exact stress sequence that reproduced the bug pre
  -fix, run twice (30 turns total, a superset of the two sequences that
  triggered leaks before): **zero leaks, zero `preamble_leak_detected`
  events** with the fix in place.
- Live direct test of the C4 backstop in isolation: posted the verbatim
  cap-truncated leaked preamble text straight to `/synthesize` (bypassing
  C2 entirely, simulating a future regression in C2's own fix) --
  `preamble_leak_detected: true`, `filtered_len: 0`, engine call skipped,
  valid 46-byte silent WAV returned (200 OK), confirming the second line
  of defense holds independently.
- All investigation/verification processes were started on alternate
  ports, driven directly, and killed cleanly afterward; none were left
  running.

*Decision: turns 6 and 9 are EXCLUDED from this run's figure, not
retained.* This differs from DR-020's RETAIN call on turn 9's leaked
`<end_of_turn>` marker, and the difference is the substance of what was
measured, not a change of policy: DR-020's case was a few trailing
leaked tokens on an otherwise complete, correctly-directed reply, so that
turn's T_ttfa still measured "time to speak a real reply." Turns 6 and 9
here spoke ONLY the (truncated) system instructions -- there is no reply
content in them at all -- so their T_ttfa values measure time-to-speak-a
-prompt-echo, a materially different quantity from what Bar B is defined
to characterize. Retaining them would silently blend two different
phenomena into one figure; excluding two turns out of twenty, with the
anomaly fully documented here, is the more honest choice.

**Defect 2 -- connection reuse and model repetition (non-blocking,
recorded, not a bug).**

*Port stability from turn 11 onward.* `c5_orchestrator/src/c5_orchestrator/main.py`
opens exactly one `httpx.Client()` for the whole 20-turn loop (`with
httpx.Client() as client:` wraps the `for` loop, not each turn) --
by design, so that connection pooling can be exercised, not because
anything holds state it shouldn't. `httpx`'s default connection-pool
keepalive expiry is 5 seconds: if the gap between one turn's last request
and the next turn's first request exceeds that, the pooled connection is
dropped and a new one (new ephemeral source port) is opened; if the gap
is shorter, the same connection and port are reused. Early turns
plausibly had longer inter-turn gaps (operator getting oriented, longer
pauses before speaking) exceeding 5s, producing new ports each time;
later turns plausibly had tighter pacing (under 5s between turns) as the
run settled into a rhythm, so the same three ports persisted. **This is
ordinary keep-alive reuse contingent on request timing, not a bug or
anything holding state improperly** -- confirmed by reading the exact
client-lifetime code, not inferred.

*Replies collapsing to variations of "Turn ten."* `prompt_eval_count`
across the run (`c2.jsonl`, `prefill_done` events) grows smoothly and
monotonically turn over turn with no spike or reset at or near turn 11
(330 at turn 11, deltas of 14-38 tokens throughout the run) -- **this
rules out a cache-reset or cache-corruption explanation**: G1's prefix
-reuse property is working continuously, exactly as designed. The
repetition itself was reproduced live in this session's defect-1
investigation: driving `c2_reason` with a sequence of short, near
-identical filler lines (the same kind of content a 20-turn timing
-calibration script plausibly uses) reliably produces a model that
settles into short, repetitive, semantically-thin replies ("I am here.",
"Yes, I am here.", "I'm here and ready when you are.") -- because the
transcript genuinely contains little new information turn over turn, no
retrieval exists yet to inject variety (DR-013b, C3 stubbed), and the
model's own past replies are never appended to the rolling transcript, so
it has no memory of what it already said and no substantive new human
content to respond to. **Verdict: this is D0's expected behaviour given
its known, already-documented design gaps (no retrieval, no assistant
-turn history, no transcript truncation policy) -- not a new bug.**
Recorded in `BACKLOG.md`, not treated as a defect requiring a code fix
here.

**Task 5 -- figure computed, held PROVISIONAL, re-measurement
recommended.** Arithmetic over `logs/run_20260907T095156Z/` via the
(presentationally fixed, DR-027) `bar_b_harness.summarize()`:

- **All 20 turns:** T_ttfa median **2.705 s**, p90 **4.987 s**.
- **Excluding the two leaked-preamble turns (n=18):** T_ttfa median
  **2.626 s**, p90 **3.937 s**.
- Kill switch (median > 8 s): NOT fired, either way, by a wide margin.
- Live carve: **16.0 GiB** (`mem_info_vram_total` =
  17179869184 bytes, read fresh this session, unchanged from DR-026 --
  DO NOT CHANGE honored, this is a read, not an action). Kernel:
  `7.0.0-31-generic` (unchanged). Model digest:
  `sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`
  (unchanged, confirmed live against the running `llama-server` process's
  own `--model` blob path, not just `.env`).

**Why this is not adopted as the new Bar B anchor.** Turns 6 and 9 are
not a labelling artefact (unlike DR-027's decomposition audit) -- they
are two turns out of twenty (10%) where a live, uncorrected-at-the-time
correctness bug was active, and they happen to be the two SLOWEST turns
in the entire run, so they distort the tail statistic specifically: p90
drops by 1.05 s (21%) once they are excluded, while the median (robust to
two outliers out of twenty) moves only 0.08 s. The fix has been verified
synthetically (unit tests) and live against a direct HTTP stress-test
that reliably reproduced the original bug twice -- but it has NOT been
verified on an actual spoken run with real microphone/VAD/HFP timing,
which is the only measurement DR-017 actually counts. **Recommendation:
one more clean 20-turn operator spoken run, with this session's fix in
place, before either arithmetic figure above is adopted as the anchor
DR-026's 3.076 s / 4.959 s is superseded by.** Until then, both figures
above are reported as what the arithmetic says over the available data,
not as a trusted Bar B result.

**Comparison against DR-026's 3.076 s / 4.959 s, with explicit strength
grading (one run either side of the Task 3 change, as instructed not to
overclaim from).**

- *Median:* 2.705 s (all 20) or 2.626 s (excluding leaks) vs. 3.076 s --
  a drop of 0.37-0.45 s (12-15%), directionally consistent with removing
  emoji/stage-direction synthesis overhead (DR-020 measured 52-104%
  synthesis-time inflation from a single instance). **Weak-to-moderate
  signal, not proof:** n=1 run on each side, with different spoken
  content and no isolation of the emoji-suppression variable from
  ordinary turn-to-turn content variance -- the same caveat DR-026 itself
  applied when comparing against DR-023's run. The direction and rough
  magnitude are consistent with the fix working; that is what the
  evidence supports, no more.
- *p90:* 4.987 s (all 20, i.e. essentially unchanged from 4.959 s) vs.
  3.937 s (excluding the two leaked turns, a 21% drop). **This
  comparison is not currently interpretable and should not be used to
  argue the emoji fix affected p90 either way.** The all-20 figure's
  apparent "no change" is an artefact of defect 1 coincidentally
  replacing what might otherwise have been the tail's fastest position
  with its slowest; the excluding-leaks figure's 21% drop cannot be
  cleanly attributed to the emoji fix either, since it comes from a
  dataset with a different, unrelated defect actively distorting exactly
  the tail turns being compared. A clean re-run is needed before any p90
  attribution claim is defensible.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

## 2026-09-07 — Thread 1.0.12: corpus and trigger rulings before D1 retrieval

### DR-029 — TIER 2 GAINS A NARROW, SEPARATE THIRD TRIGGER PATH: DERIVED CRITERIA EVALUATION. DR-008's LEXICAL-RETRIEVAL PROHIBITION IS PRESERVED, NOT REVERSED. (2026-09-07)

**The gap.** DR-008 makes Tier 1 (the company's own material) the only
trigger source; Tier 2 (law and standards) is consulted only after Tier 1
flags a candidate. A live proposal that is novel — no Tier 1 precedent, so
nothing fires — but conceptually in breach of a standard or of good practice
falls through this gate entirely. That is precisely the case a board most
needs flagged, and DR-008 as written cannot flag it.

**What is NOT wrong.** DR-008's reasoning stands and is not reopened here.
Its target was measured, not theoretical: 2.x's end-to-end run flipped 4 of 6
correctly-Absent records to false-positive Partial because a large, generic,
lexically-overlapping corpus always returns a nearest-neighbour chunk.
Similarity search over raw law/standards TEXT as a trigger makes Jester a
chatterbox. That mechanism — retrieval-as-trigger over bulk text — is what
DR-008 correctly forbids, and it remains forbidden. DR-008's Tier 2 wording
("law and standards... NEVER a trigger source on its own") is narrowed by
this entry, not reversed: it continues to bind Tier 2's LEGISLATION/STANDARDS
TEXT sub-collection exactly as filed.

**RULING.** Tier 2 is split into two sub-collections with two different
retrieval/evaluation mechanisms, mirroring DR-009's existing derived-criteria
posture rather than inventing a new one:

- **Tier 2a — raw law and standards TEXT** (to the extent legislation is
  redistributable at all; DR-009 already bars ISO/IEC text from shipping).
  Unchanged from DR-008: substantiates only, queried after a Tier 1 or Tier
  2b hit, never a trigger source.
- **Tier 2b — DERIVED CRITERIA** (already mandated content-wise by DR-009 for
  licensing reasons). This is a NEW, THIRD trigger path, additive to Tier 1's
  existing trigger authority, and it is NOT a retrieval path. A criterion
  ("AI systems affecting individuals require documented human oversight") is
  a checkable proposition an utterance either does or does not satisfy;
  DR-008's failure mode — a nearest-neighbour chunk always exists in a large
  generic corpus — does not apply to evaluating an utterance against a small,
  fixed set of discrete propositions. That is the argument for why this path
  can trigger without reproducing DR-008's noise.

**Where the noise relocates — the control is NOT free.** The mechanism that
replaced similarity thresholding is criteria SPECIFICITY and COUNT: an
over-broad or overlong criteria set fires on most boardroom utterances just
as surely as bulk-text retrieval did, by a different route. This is
testable — a fire-rate measurement of the criteria set against a transcript
corpus — but no fire-rate bar is fixed here. Per WAYS_OF_WORKING §7, the bar
must be fixed BEFORE that experiment is run, not after. This ruling licenses
the experiment; it does not pre-empt its result.

**What this adds to SEED §8 q1, and what it leaves open.** SEED §8 q1 ("C3
trigger mechanics... the core product question") is NOT closed by this entry
and is not to be treated as closed. What this ruling adds: there are now
THREE trigger paths, not two (Tier 1 alignment-mismatch/policy-breach, Tier
2b criteria evaluation, and invitation/direct-question), and Tier 2b's
criteria are the mechanism by which a Tier-1-precedent-free proposal can
still be caught. What remains open, explicitly, because this ruling does not
settle it:
  1. **Cost.** A criteria set is a stable prefix, so DR-013 G1's cache-hit
     regime (0.249 s delta prefill for +200 tokens) favours holding it
     resident — but it consumes `num_ctx` capacity DR-013(b) already flags
     as overflowing a real meeting in 30-45 minutes. Both directions are
     live; neither is resolved here.
  2. **Whether evaluation belongs in C3 or C2.** SEED §2 states C3 is "a
     fast, cheap gate... not deep reasoning: the expensive thinking is C2's."
     Whether per-criterion evaluation fits C3's gate budget or belongs to
     C2's reasoning pass is a latency question nobody has measured, and DR-006
     already makes C3's etiquette (hand-up-then-speak) the PRIMARY latency
     mitigation — Tier 2b evaluation must fit inside that budget or it
     undermines the mitigation DR-006 relies on. UNDECIDED.
  3. **How criteria are derived, and by whom.** Under DR-002's Gate A,
     frontier-assisted derivation of criteria from standards text is
     permitted as a development artefact (the boundary is the shipped
     PRODUCT making no runtime frontier calls, which criteria-as-static-text
     does not violate). But derivation is not purely an engineering choice:
     a criterion derived too close to the source standard's own wording risks
     being a derivative work, which is a legal judgement, not an engineering
     one, and is NOT settled by this entry. Who signs off that a derived
     criterion is sufficiently transformed is open.

**Consequence for SEED.** `SEED_jester-1.0.md` §8 q2 is annotated (not
rewritten, per its own resolved-in-place convention) with a pointer to this
entry, since its "never a trigger source on its own" phrasing is now narrowed
for Tier 2b specifically. Filed as a jesterai touch; see that repo's entry.

### DR-030 — ISOLATION IS THE STATED DATA-HANDLING POSTURE FOR ALL DOCUMENT CLASSES; ITS CONSEQUENCES ARE RULED AS INTENT WITH AN EXPLICIT, UNBUILT GAP — NOT AS AN IMPLEMENTED CONTROL (2026-09-07)

**RULING.** Private and sensitive documents supplied to Jester (employee
records, legal advice, financial forecasts, board material, anything else a
board chooses to supply) receive no special per-document handling. The
control is isolation, not classification: Jester is a standalone box, session
material is contained on the USB volume, and the box is purged of residual
session material between sessions unless something is deliberately written
out to a `Jester_OUT` volume. This is recorded so it is not re-litigated the
next time a sensitive document class comes up.

**This ruling is of INTENT. It is explicitly NOT a statement that the
posture is implemented.** Its consequences are load-bearing and testable,
and are recorded here precisely so they can be tested rather than assumed:

1. **The purge between sessions must actually occur and must be verifiable.**
   "Verifiable" means an enumerable list of retention surfaces plus a
   checked-empty-at-session-start record — a purge that cannot be checked is
   not a control, only an intention.
2. **"The box" covers, at minimum: model KV cache/loaded weights, the vector
   store, logs and transcripts, and any temporary files.** Each is a distinct
   surface with a distinct current state (below).
3. **Anything written to `Jester_OUT` is a deliberate act with its own
   controls**, separate from the purge boundary above. Those controls are not
   designed in this session.

**Current state, checked this session, stated plainly rather than assumed:**

- **Purge mechanism: DOES NOT EXIST.** No script, service, or documented
  procedure purges the box between sessions. This is a gap, not a
  deprioritised nicety.
- **Logs/transcripts: PERSIST, unpurged.** `jester-1.0/logs/` and
  `logs_1.0.10_backup/` exist in the working tree on the box. They are
  git-ignored (`.gitignore`: `logs/`, `logs_*_backup/`) so they do not persist
  in the repo's committed history, but they persist on disk, uncontrolled, in
  the working tree — which is the surface the purge boundary above must
  actually cover.
- **Model KV cache / loaded weights: PERSIST, by design, unrelated to this
  posture.** `ollama.service` is an enabled, currently-running systemd unit
  (`systemctl is-enabled ollama` → enabled), i.e. a persistent server whose
  process and any cached state outlive any single session. Whether ollama's
  own cache retains content specific to a prior session's utterances was not
  established this session and is carried forward as an open question, not
  assumed clean.
- **Vector store: does not yet exist.** No retrieval has been built (this is
  a pre-D1 session by design). The surface is empty by ABSENCE of the
  component, not by any control over it — recorded so it is not mistaken for
  a designed-empty state once C2 retrieval lands.
- **Residue from other streams, found on this box outside either repo, at
  session start:** `/home/jester/corpus_files/`, `/home/jester/models/`,
  `/home/jester/bakeoff/`, `/home/jester/backup-demo-input-2026-08-25T004252/`.
  These are 2.x-stream artefacts, not Jester 1.x session material, but they
  are concrete evidence that untracked material accumulates on this shared
  box across streams and sessions with no existing removal mechanism — the
  exact class of gap a purge would need to close. Not touched this session
  (write-no-application-code, box-state changes deferred per machine-authority
  convention).

**Filed here rather than jesterai** because Task 3 was assessed to straddle:
the posture itself is 1.x product/data-handling state, but the purge
mechanism, once built, is box-level per `PORTFOLIO.md` §6 (it must cover
residue from all streams sharing the box, as the found residue above
demonstrates). This entry rules the posture and records the gap; the
box-level purge-mechanism work itself is not designed here and is
cross-referenced from jesterai's entry as future box-level work.

### DR-031 — TIER ASSIGNMENT IS PER-DOCUMENT AT INGEST, ON PROVENANCE/AUTHORITY, NOT ON VOLUME OR SENSITIVITY; SAFE DEFAULT IS NON-TRIGGERING; A REJECT PATH IS REQUIRED, NOT ONLY A TIER FIELD (2026-09-07)

**Why tier cannot be a volume property.** `Jester_IN` is the single read
volume for both 1.x and 2.x; its contents are whatever a board chooses to
supply — legislation, counsel advice, forecasts, agendas, minutes, employee
records, anything, undifferentiated on the medium. Tier assignment is
therefore necessarily a per-document decision made at ingest, not an
inherited property of where a file came from.

**RULING — the discriminating test is provenance/authority, not topic or
sensitivity.** The question an ingest step must answer per document is: is
this an instrument of THIS COMPANY'S OWN governance (Tier 1), or does it
carry general legal/normative force without being company-specific (Tier
2a/2b, per DR-029)? This is derivable directly from DR-008's own Tier 1 list
(board pack, prior minutes and resolutions, policies, risk register,
articles, delegation-of-authority matrix, material contract obligations,
open regulatory correspondence) — note DR-008 already contains the edge case
that proves the test is provenance and not "internal-facing": open regulatory
correspondence is externally directed yet is Tier 1, because it is an
instrument of this company's own position.

Tier assignment is explicitly NOT a sensitivity classification — DR-030
already rules that sensitivity gets uniform isolation handling regardless of
tier. The two axes are independent: employee records are Tier 1 by
provenance (the company's own material) despite being of near-zero value as
a trigger source, and counsel advice is company-specific yet typically holds
no precedent-setting force the way a board resolution does. DR-008's own
priority note (minutes/resolutions rank above legislation) already implies
an internal value ranking within Tier 1 that provenance alone does not
capture. Flagged here as a real texture in the data, not resolved — inventing
a Tier 1a/1b split is explicitly out of scope for this entry.

**Safe default for an ambiguous or unassigned document: NON-TRIGGERING,
flagged for review — never default to Tier 1.** Reasoning from DR-008's own
stated value: Tier 1 is the ONLY trigger source, so defaulting an
unclassified document into Tier 1 makes it a trigger source by default,
i.e. manufactures exactly the noise DR-008 was written to prevent, against a
product whose value is knowing when to stay silent. Defaulting an ambiguous
document to non-triggering (available for retrieval/substantiation once
tiered, but inert until then) fails safe.

**A reject path is required, separate from the tier field.** DR-009 already
means raw ISO/IEC standards text must not be on the volume at all — an
ingest step therefore needs three outcomes, not two: assign-Tier-1,
assign-Tier-2(a/b), or REJECT (redistribution status prohibits shipping this
text in any tier). Tier field alone cannot express "this document may not be
retained."

**What a future ingest session needs, to classify the carried-over DHI
corpus.** The volume was not mounted this session (`mount | grep jester`
returned nothing), so DHI's contents were not inspected and are not
classified here, per this session's write-no-application-code and
machine-state-deferred posture. A future ingest session needs, per document:
provenance (authored by whom, for whom, and under what authority),
document type and whether it is a governance instrument vs. a reference
text, date/version and supersession status (is this superseded by a later
board resolution or a later standard revision), and licensing/redistribution
status (to route the reject path per DR-009). Without these four, per-
document tiering cannot proceed safely and the DHI corpus should be treated
as unassigned/non-triggering under this entry's safe default until it is.

### DR-032 — C2's RETRIEVAL INTERFACE IS SHAPED FOR SHARED USE (1.x SPOKEN AND 2.x CHAT) FROM THE OUTSET; THIS IS AN INTERFACE-SHAPE RULING ONLY, NOT A SHARED-DEPLOYMENT, SHARED-CORPUS, OR SHARED-CODE-OWNERSHIP COMMITMENT (2026-09-07)

**Observation.** Jester 1.x (conversational audio) and 2.x's "chat with AI"
function are the same retrieve-then-reason engine behind different
transports (voice turn-taking vs. a chat window).

**RULING — shape C2's retrieval interface for shared use from the outset.**
Supporting argument, anchored in this stream's own already-filed
constraints, not asserted fresh:

- SEED §3/§7 already commit C2 to speaking HTTP on env-configured addresses,
  even co-located — "no in-process shortcuts... never assumed co-located." A
  chat client is simply another caller of that same interface; no new
  transport commitment is created by this ruling.
- SEED §7's own stated rationale — skipping the discipline "turns the later
  hardware port from a one-day exercise into a one-month rewrite" — applies
  identically to retrofitting a second caller's shape onto an interface
  designed around one.
- The cost now is small and specific, not open-ended: C2's request carries a
  `corpus_id` and a `mode` field rather than assuming a meeting transcript,
  and retrieval sits behind an interface rather than inlined into C2's
  request-handling.

**The cost, named honestly, not waved away.** At D0, `corpus_id` and `mode`
each have exactly one live value — there is no second caller yet. Dead
parameters are a real cost: they can be mis-set with nothing to catch it
until a second caller exists to disagree. This is accepted here as a
DELIBERATE, NARROW exception to the no-premature-abstraction default — two
fields and one interface boundary, not a plugin system or a generalised
corpus framework — justified specifically by SEED §7's one-day-vs-one-month
argument, which is a stronger justification than "might be reused someday."

**Binding technical carry-over, not just a portability nicety.** DR-013(a)
already established, as a measured constraint: retrieved evidence must be
APPENDED AFTER the rolling transcript, never prepended, or the cached
prefix invalidates and first-audio latency returns to the 5-11s regime. A
chat-mode caller has no rolling transcript to append after. The interface
must express this ordering discipline mode-independently (e.g. "stable
context first, evidence appended last, query/turn last of all") rather than
assuming a transcript-shaped stable prefix — this is the one place the
shared shape carries a technical requirement, not only an architectural
preference.

**Reconciled against `PORTFOLIO.md` §5 — this ruling does not cut across
it.** §5 governs CODE ARTEFACTS: "zero shared code by default,"
copy-then-diverge with provenance hashing, and package extraction "deferred
until the same fix lands in two repos more than once (expected: never)."
This entry rules the SHAPE of an interface inside 1.x's own C2 codebase; it
grants NO license to extract a shared package, share a deployment, or share
a corpus between 1.x and 2.x. A future reader must not read "shared shape"
as "shared package" — §5 continues to forbid the latter. What is shared is
the discipline that a second caller, if one is ever built, calls a
`/respond`-like endpoint that already has a place for `corpus_id` and `mode`
to go, nothing more.

**Explicitly NOT decided by this entry:** whether a 2.x chat caller will
ever actually be built against this interface; whether 1.x and 2.x would
ever share a corpus (DR-008/DR-009's corpus content is 1.x-specific and nothing
here changes that); and code ownership, which stays governed by §5 as
written.

### DR-033 — VECTOR STORE AND EMBEDDING POSTURE ACROSS STREAMS: SAME TECHNOLOGY, SAME EMBEDDING MODEL, PINNED BY DIGEST — SEPARATE PERSISTENT DIRECTORIES, NO SHARED COLLECTIONS; INGEST-CODE REUSE IS COPY-THEN-DIVERGE, NOT SHARED (2026-09-07)

**Why this follows DR-032, filed alongside it in the same home.** DR-032
rules C2's retrieval interface shared-shaped from the outset but does not
say what sits behind that interface. 2.x already runs ChromaDB with
`nomic-embed-text` on this box; 1.x needs a store. "Reuse ChromaDB" collapses
three genuinely separate propositions, and only some are safe. Each is ruled
separately, deliberately, so a future reader cannot flatten them back
together:

**(a) REUSE THE TECHNOLOGY — RULED YES.** Both streams use Chroma as the
vector-store engine. This is a technology choice, not a data-sharing
decision, and carries none of DR-008's risk on its own — an engine is not a
corpus.

**(b) REUSE THE STORE — RULED NO. Separate persistent directories per
stream; no shared collections, ever.** Reasoning, tested against what is
actually filed rather than asserted fresh:
  - **Concurrency is not the risk.** DR-004 already rules 1.x and 2.x
    mutually exclusive on this box — "switchable... NEVER running
    concurrently" — so nothing contends for a store at the storage-engine
    level. A shared store would not corrupt from concurrent writers, because
    there are none. That is not the argument for separation.
  - **The actual risk is DR-008's, and DR-008 as filed supports this reading
    directly, not by extension.** DR-008 states the two-tier corpus "must
    NOT be blended into one index" and structures Tier 1/Tier 2 as "two
    separate collections with two retrieval paths" — verified against
    DR-008's text in `jesterai/DECISIONS.md`, not assumed. That ruling is
    about 1.x's OWN internal tiers; a shared store between 1.x and 2.x is
    the same failure mode one level up. A shared Chroma instance turns
    "2.x's audit corpus must never surface in a 1.x board meeting" from an
    IMPOSSIBILITY (separate stores, nothing to misconfigure) into a
    CONFIGURATION ERROR (one store, a wrong or missing collection filter).
    DR-008's own rationale — a large, generic, lexically-overlapping corpus
    always returns a nearest-neighbour chunk, and that is what turned 4 of 6
    correctly-Absent 2.x records into false positives — applies with equal
    or greater force to 2.x's entire audit corpus leaking into a 1.x
    retrieval call by way of a shared collection.
  - **It cuts against this session's own DR-030.** DR-030 rules isolation —
    box purged between sessions, session material contained — as the
    data-handling posture. A vector store that persists across streams and
    sessions is a standing exception to "the box is purged between
    sessions" by construction: if session material lives on in a store that
    survives the session that created it, DR-030's isolation claim is not
    true of that surface. Separate per-stream directories at least confine
    the exception to a named, inspectable location rather than one shared
    store neither stream fully owns.
  - **The cost of separation is close to free.** One environment variable
    (a `CHROMA_PERSIST_DIR`-shaped setting) pointing 1.x's store at its own
    directory, distinct from 2.x's. Against DR-008's measured failure mode
    and DR-030's isolation claim, this is not a real tradeoff.

**(c) REUSE THE INGEST CODE — RULED: COPY-THEN-DIVERGE, NOT SHARED, NOT
EXTRACTED.** 2.x's existing document-conversion pipeline (pdfplumber,
python-docx, python-pptx, openpyxl, beautifulsoup4, olefile, pytesseract) is
a real, working asset and re-implementing it from scratch for 1.x would be
wasted effort for no safety gain — none of DR-008's or DR-030's risk lives
in the ingest/conversion step, only in the store and the trigger logic
downstream of it. Reconciled directly against `PORTFOLIO.md` §5 and
`WAYS_OF_WORKING.md` §12, already the standing cross-stream code-sharing
rule and not cut across here: "copy-then-diverge, provenance-hashed" —
1.x takes a COPY of 2.x's ingest code, records a fork-commit provenance
hash, and diverges from there; it is not a shared package, not a live
dependency on `jester-2.1`, and not a newly-extracted common library. §5's
own stated position — "shared-package extraction is deferred until the same
fix lands in two repos more than once (expected: never)" — is not
overridden by this entry. DR-012 already established this exact pattern for
any 2.x asset 1.x reuses ("copy-then-diverge with a provenance hash — never
shared"); this entry applies that established pattern to the ingest
pipeline specifically rather than inventing a new one.

**THE EMBEDDING PIN — the non-obvious failure mode, ruled explicitly.** The
embedding model must be IDENTICAL, and pinned by DIGEST rather than a
mutable tag, across any store that may ever be compared or merged — this is
DR-020's tag-and-digest principle (a mutable `:latest` tag can silently move
underneath a pinned deployment) applied to embeddings rather than to the
reasoning model. The failure mode is worse here than DR-020's original case:
if `nomic-embed-text:latest` moves to a new checkpoint after a store already
has vectors written against the old one, every existing vector is silently
invalidated — there is no error at write time (Chroma has no way to know the
embedding function changed) and no error at read time (similarity search
still returns SOME nearest neighbour, just against a corrupted space) DR-008's
own "there is ALWAYS a nearest-neighbour chunk" applies here too: the
failure is invisible precisely because the system keeps answering.

Digest recorded, as currently pulled on this box: `ollama show --modelfile
nomic-embed-text:latest` resolves to blob
`sha256-970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6`
(the same blob-vs-registry-manifest digest distinction DR-020 already
established for the reasoning model applies here too — `ollama list` shows a
separate, shorter registry-manifest identifier, `0a109f422b47`, for the same
tag; the blob digest above is the one that identifies the actual weights and
is the one to pin).

**RULED: any vector store built for either stream records the embedding
model digest it was built with** (e.g. as store metadata or a sidecar file
next to the persistence directory), so a mismatch between a store's recorded
digest and the currently-pinned embedding model is DETECTABLE at
store-open time, rather than silently returning corrupted similarity
results. The mechanism for this check is not designed in this entry — only
that one must exist before a store is trusted across a model-tag change.

**What this entry does NOT decide.** It does not choose the embedding model
on its merits. `nomic-embed-text` is the INCUMBENT already pulled and in use
by 2.x on this box — adopted here for convenience of not introducing a
second embedding model alongside a second vector-store technology, not
because it has been evaluated against alternatives for 1.x's retrieval
task. `SEED_jester-1.0.md` §8 q2 already carries "the embedding-model and
vector-store choices also remain open" and that remains true after this
entry — (a) above settles the STORE TECHNOLOGY only (Chroma), not the
embedding model's fitness. Stated plainly so convenience is not later
misread as evaluation: revisiting the embedding-model choice on its merits
is still open work, not foreclosed by adopting the incumbent now.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

### DR-034 — D1 INGEST BUILT AND RUN: TIER-ASSIGNMENT HEURISTIC, CHUNKING STRATEGY, AND DR-028 NUMBERING NON-GAP (2026-09-07)

**DR-028 numbering check (thread 1.0.13 Task 1).** DR-027 is followed by
DR-029 in `DECISIONS.md`'s prose ordering, which read as a possible gap in
the numbering. Checked: DR-028 EXISTS, filed in full at this file's own
line ~825 ("Preamble-leak defect found and fixed..."), and is cross-referenced
throughout `BACKLOG.md` and `RELAY.md`. There is no gap. No note is filed for
a non-gap; recorded here only because the checking was asked for explicitly.

**Ingest pipeline built per DR-033(c).** `c2_reason/src/c2_reason/ingest/`
(new): `converters.py` (pptx + image, COPY-THEN-DIVERGE from
`jester-2.1/ingest/conv_pptx.py` and `conv_img.py`), `ocr.py`
(COPY-THEN-DIVERGE from `jester-2.1/ingest/ocr.py`), `tiering.py` (new, DR-031
implementation), `chunking.py` (new), `store.py` (new, DR-033(b) Chroma
store + digest-mismatch guard), `ingest_config.py` (new, env-var config
following `config.py`'s DR-020 fail-loudly convention), `run.py` (new,
orchestrator with structured JSON logging to stderr).

**Scoping divergence from the 2.x reference, named explicitly.** Only pptx
and image converters were copied: the Jester_IN survey (Task 2, this thread)
found no pdf/docx/xlsx/msg/html/eml files on the volume, so those
converters were not ported. 2.x's `ConversionResult`/`_version_meta`/manifest
apparatus (built for the 2.x assessor's `evidence_strength` scoring) was not
carried across either — 1.x's retrieval-and-trigger use case does not need
per-document approval-date/confidence metadata, so this is a smaller,
purpose-built module, not a partial port. This is a divergence decision, not
an oversight, and is recorded so a future reader does not read the missing
converters as an incomplete copy.

**Tier-assignment heuristic (RULED, not merely implemented).** `tiering.py`
classifies each document by matching its path against DR-008's own Tier-1
list (board pack, minutes, resolutions, policy, risk register, articles,
delegation-of-authority, material contract obligations, regulatory
correspondence) as keyword stems, with every non-match defaulting to
UNASSIGNED (non-triggering) per DR-031's safe default — never guessed into
Tier 1. This is explicitly a first-pass, hand-auditable heuristic sized to a
~46-document corpus, not a durable tiering mechanism; every assignment logs
its matched evidence so a human can audit or correct it. Carried to
`BACKLOG.md` as work a larger corpus will require replacing.

**Chunking strategy (RULED).** Chunk on the converters' own natural section
boundary (`## Slide N:`, from `converters.convert_pptx`) when present;
fall back to a fixed 220-word window with 40-word overlap for text with no
natural boundary (OCR output has none). Chosen because the corpus is
uniformly short-per-unit (slide decks, single OCR'd photos) — no chunk in
this run needed sub-splitting except as a safety cap on the rare oversized
slide. Not represented as a generally-correct strategy for a different
corpus shape (e.g. long-form prose).

**Run result (Task 4), summarised — full figures in this thread's RELAY.md
STOP report:** 46 documents seen (48 minus 2 excluded — see below), 46
processed, 0 rejected, 0 unprocessed, 0 degraded, 622 chunks written, 5
documents tiered TIER1, 41 UNASSIGNED (non-triggering), 0 into any Tier-2
sub-collection (no legislation/standards text found on the volume — DR-009's
reject path exists in `tiering.py` but fired zero times, not exercised by
real data this run). Elapsed 240.42s. Retrieval verified against 5
representative queries — returned relevant chunks in every case — but this
is a searchability sanity check, not a quality evaluation; no fire-rate or
precision figure is claimed.

**Two exclusions from ingest, decisions not oversights.** (1) `engagement/`
is a byte-identical duplicate mirror of the top-level `DHI-*/` and
`_cross-entity/` trees (verified by md5sum on a sample, not assumed) —
ingesting it would double-count every document, so it is skipped by name.
(2) `charter_dhi.json` / `.old` are the 2.x assessor's OWN engagement-scoping
config (role, criteria edition, org boundary) — not a DHI document — and are
excluded as tooling artefact, not corpus content.

**What this does NOT do, stated plainly (Task 5).** Retrieval is not wired
into C2's request path; no C3 trigger logic reads from either collection;
DR-013's `num_ctx` 8192 constraint is untouched and unmeasured against
retrieved-evidence-plus-transcript token pressure. Carried to `BACKLOG.md`.

**Scope tension disclosed, not hidden.** This session's writable scope named
jester-2.1 as "read-only HEAD check only," and separately named DR-033(c)'s
copy-then-diverge requirement, which is impossible to satisfy without
reading jester-2.1's actual converter source. This session read
`ingest/conv_pptx.py`, `ingest/conv_img.py`, `ingest/ocr.py`, `CLAUDE.md`,
and `requirements.txt` from jester-2.1 to do that — a file-content read, not
a HEAD-only check. No write was made to jester-2.1 at any point: confirmed
by `git -C jester-2.1 status --porcelain` returning empty and HEAD
unchanged at c41dc92fd121dafaae39a50d68e7aa91e73f9756 across the session.
Flagged here as a disagreement between two instructions in the same prompt,
resolved in favour of the more specific, later-cited requirement
(DR-033(c)'s copy-then-diverge), not silently.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

## 2026-09-07 — Thread 1.0.14: D1 retrieval wired into C2

### DR-035 — D1 RETRIEVAL WIRED INTO C2: INTERFACE SHAPE AS BUILT, AND A THIRD READ PATH OVER THE UNASSIGNED COLLECTION RULED IN FOR QUESTION-ANSWERING ONLY (DR-008'S TIER-1 RESTRICTION IS TRIGGER-SCOPED, AND IS PRESERVED, NOT RELAXED) (2026-09-07)

**Built, per DR-032's interface-shape ruling.** New module
`c2_reason/src/c2_reason/retrieval.py`: a `Retriever` protocol with a
`ChromaRetriever` implementation and a `NullRetriever`, called from
`main.respond()` behind that interface rather than inlined.
`RetrievalRequest` carries `corpus_id`, `mode`, `query` and `intent`;
`RespondRequest` gains the same fields and C5 sends them explicitly rather
than relying on C2's defaults at both ends.

**DR-032's dead-parameter cost is mitigated, not merely accepted.** DR-032
named the cost honestly — the two fields "can be mis-set with nothing to
catch it until a second caller exists to disagree." `ChromaRetriever._validate`
rejects a `corpus_id` that does not match C2's configured corpus and an
unimplemented `mode`, following `config.py`'s own fail-loudly convention
(DR-020). `MODE_CHAT` exists as a named constant and raises
`UnsupportedModeError`: an unimplemented mode that fails loudly is honest,
one that silently behaves like the other is not. Covered by
`tests/test_retrieval.py`.

**DR-008's separate paths, built as three named paths over four separate
collections, never one blended index.** Path 1 queries `tier1`. Path 3
queries `tier2a`/`tier2b` ONLY when Path 1 returned at least one candidate
— DR-008's "Queried ONLY after Tier 1 has flagged a candidate, to confirm
and cite. NEVER a trigger source on its own" — and is asserted in both
directions by test. Both Tier 2 collections are empty on this box (DR-034:
zero documents tiered into either), so Path 3 is exercised by the code and
returns nothing from real data. Recorded in DR-034's own language: the path
exists, it is not exercised by real data, and no claim is made that it works
untested.

**THE RULING THAT NEEDED MAKING — Path 2, the unassigned collection.**
DR-034 tiered 5 of 46 documents TIER1 and 41 UNASSIGNED. Had retrieval
queried Tier 1 alone, Jester could answer from 5 of 46 documents and this
thread's twenty-turn spoken run would have measured a system that mostly
retrieves nothing. The discriminating question is whether DR-008's Tier-1
restriction is scoped to TRIGGERING or to ALL RETRIEVAL. Checked against
DR-008's own text rather than assumed: "THIS IS THE ONLY TRIGGER SOURCE.
C3 fires off Tier 1." That is trigger-scoped. DR-031's safe default for an
unassigned document is "non-triggering," not "unreadable."

RULED: the unassigned collection is readable on an EXPLICIT USER QUESTION,
as a separately named path against its own collection, gated on
`intent == "question_answering"`, and never blended into the Tier 1 query.
This grants C3 nothing whatsoever — a trigger-scanning caller carries a
different intent and is rejected before the path is reached, which is
asserted by test (`test_unassigned_path_is_gated_on_question_answering_intent`).
DR-008's measured rationale is preserved exactly: its finding is that a
large generic corpus makes Jester a chatterbox by always yielding a
nearest-neighbour chunk to FIRE ON. Answering a question a human actually
asked is not firing. This entry does not revisit tier assignment, which is
deferred to the C3 thread by operator ruling.

**The ordering question DR-032 raised, answered explicitly.** DR-032 asked
that the ordering discipline be expressed mode-independently, illustrated
by "stable context first, evidence appended last, query/turn last of all."
That phrasing is an `e.g.`, not a mandate to move the current turn's text
after the evidence. The shape built keeps the question inside the
transcript region: transcript-including-the-question -> evidence ->
recency reminder -> Gemma turn-close markers. Moving the question after the
evidence would change the accumulation invariant that DR-027's preamble-leak
mitigation and the entire existing Bar B baseline were measured against, for
no measured benefit. Recorded so a future reader does not read the
divergence from DR-032's illustration as an oversight.

**One incidental defect found and fixed.** `ingest/store.py` imported
`IngestConfig` and never used it. `IngestConfig` reads required env vars at
class-definition time, so the unused import made merely IMPORTING the store
module fail unless the INGEST environment was set — which broke C2's
serving path the moment it read the same store. Import removed; every value
the module needs was already passed in by its caller.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

### DR-036 — DR-013(b)'s CONTEXT PROBLEM MEASURED, NOT DECIDED: RETRIEVAL ADDS A CONSTANT ~794-TOKEN OFFSET RATHER THAN A GROWING ONE, COSTING ~4 MINUTES OF THE MEETING WINDOW; THE OVERFLOW FAILURE KILLS THE WHOLE RUN RATHER THAN DEGRADING ONE TURN — A TRUNCATION POLICY IS STILL THE OPERATOR'S DECISION AND IS NOT INVENTED HERE (2026-09-07)

**This entry deliberately does NOT decide a truncation policy.** DR-013(b)
left it UNDECIDED and called it a design question, not a tuning detail.
This thread was instructed to either propose a policy with its reasoning or
state plainly that it needs an operator decision, and to record the
evidence either way. It states the latter, and records the evidence. The
tool that produced these figures is committed as
`c2_reason/context_budget.py` so they can be re-derived, not taken on trust.

**FINDING 1 — the structural point, and it is not the one the framing
anticipated. Retrieval adds a CONSTANT offset, not a growing one.**
Retrieved evidence is rebuilt fresh every turn from that turn's query and is
never written back into the rolling transcript
(`tests/test_prompt_ordering.py::test_evidence_is_never_accumulated_into_the_transcript`
asserts this directly, because the accumulating version of this bug would
diverge the cached prefix every turn with nothing raised). The prompt at
turn N is therefore preamble + transcript(1..N) + evidence_N, where only
the transcript term grows. Retrieval brings the overflow point closer by a
fixed amount; it does not make the meeting fill the window faster. Naive
worry — "retrieved documents joining a rolling transcript compound" — does
not hold for this design, and the reason it does not hold is a property
worth protecting deliberately.

**FINDING 2 — how many tokens a typical retrieval adds, measured against
the live store.** Ten realistic board questions spanning both populated
collections, `top_k` 3 per path (6 chunks per query: 3 Tier 1, 3
unassigned, 0 Tier 2). Estimated evidence tokens (this repo's chars/4
estimator): median 794, min 636, max 1653. Measured at other settings for
the operator's benefit: `top_k` 1 gives median 302 (max 674), `top_k` 2
gives median 549 (max 1018). Live turns in this thread's smoke run appended
702–1010 evidence tokens against Ollama-reported total prompts of 867–1163
tokens — i.e. evidence is roughly 80% of the entire prompt at D0
transcript lengths.

**FINDING 3 — how close a realistic session comes to the limit.** Two
different projections, kept separate because they answer different
questions and one of them is nearly worthless on its own:
  - From this repo's OWN measured Bar B runs (`prompt_eval_count` deltas in
    `logs/run_20260907T095156Z` and `logs_1.0.10_backup`): 9–14 transcript
    tokens per turn, giving 633 turns to overflow at median evidence versus
    702 without retrieval. This figure is NOT to be relied on: Bar B turns
    are short prompted calibration utterances, not continuous meeting
    speech, and they understate real pressure by roughly an order of
    magnitude. Recorded so nobody re-derives it later and mistakes it for
    reassurance.
  - Projected to continuous meeting speech at 190 transcript tokens per
    minute (~130–160 words/min; STATED ASSUMPTION, the one un-measured
    input in this entry and flagged as such in the tool's own output):
    42.8 minutes to overflow without retrieval, 38.6 minutes at median
    evidence, 34.1 minutes at maximum observed evidence. **Retrieval costs
    roughly 4 minutes of meeting window at the current `top_k`.** The
    without-retrieval figure of 42.8 minutes lands inside DR-013(b)'s own
    independently-stated "30-45 minutes," which is a useful cross-check on
    the assumption rather than a coincidence to lean on.

**FINDING 4 — what the failure actually looks like, and it is worse than
"it raises loudly."** Traced through the live call path, not inferred:
`PromptBuilder.build()` raises `PromptOverflowError`, which propagates out
of `main.respond()` as a FastAPI 500, which
`c5_orchestrator.main.run_turn`'s `respond_resp.raise_for_status()` turns
into an exception that nothing catches — neither `run_turn` nor `main()`'s
turn loop. **An overflow does not degrade one turn; it terminates the
entire run.** In a real meeting that is Jester going permanently silent
mid-session with a stack trace on a terminal nobody is watching. This is
recorded as a finding, not fixed here: making C5 swallow the error would be
a truncation-adjacent behaviour change of exactly the kind DR-013(b)
reserves to the operator, and the honest fix depends on which policy is
chosen.

**WHAT THE OPERATOR IS BEING ASKED TO DECIDE, and the evidence for each
option** (recorded so the decision does not need this analysis re-run):
  - (a) Drop evidence first when the window is tight. Cheapest — evidence
    is a constant, droppable term and dropping it costs no transcript
    history. Degrades Jester to a no-corpus assistant exactly when a long
    meeting has accumulated the most context worth citing.
  - (b) Truncate the transcript from the front, keeping the preamble. This
    is the one that interacts with G1/DR-013(a): removing text from the
    START of the prefix invalidates the cached prefix on the turn it
    happens, so a full cold prefill is paid once per truncation. G1
    measured cold prefill at 599 tokens/s, so a single ~8k truncation event
    costs on the order of 10 seconds of first-audio latency on that turn —
    one turn well past DR-017's 8-second kill switch, then back to normal.
    Whether one such spike per ~35 minutes is acceptable is a product
    decision, not a technical one.
  - (c) Raise `num_ctx` above 8192. Untested on this box, changes the
    memory profile against the 16 GiB carve, and is not free at D0.
  - (d) Lower `top_k`. Buys back only ~4 minutes total (Finding 3) at a
    direct cost in answer quality. It is a tuning knob, not a solution to
    the window problem, and should not be mistaken for one.
None of (a)-(d) is adopted here.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

### DR-037 — RETRIEVAL'S MEASURED COST AT THE C2 STAGE: THE EMBED+QUERY STAGE IS ~3% OF IT AND THE EVIDENCE-TOKEN PREFILL IS ~97%; THE BAR B DECOMPOSITION IS RE-ANCHORED SO THIS CANNOT HIDE (2026-09-07)

**Why the stage boundary had to move before anything was measured.** Bar B
computes `c2_prefill_s` as `prefill_done_monotonic_ts -
prefill_start.monotonic_ts`, and `prefill_start` was the first statement in
`main.respond()`. Any retrieval placed after that log line would have had
its entire cost absorbed into `c2_prefill_s`, with the new retrieval stage
reading as zero and nothing raising. `retrieval_start` is now the first
statement in the handler and `prefill_start` is logged only after
`retrieval_done`; `retrieval_s` is a full member of
`bar_b_harness._PARTITION_STAGES`, not a footnote. Both retrieval events are
emitted on EVERY turn including when retrieval is disabled or returns
nothing, because `decompose_turn` drops any turn missing a required event
and conditional logging would have biased the sample toward turns that
happened to retrieve. Verified on the smoke run rather than assumed: no
turn showed more than 50 ms of unattributed time between `retrieval_done`
and `prefill_start`, and the pre-retrieval baseline logs re-decompose with
`partition_gap_median_s` 0.0057 s.

**MEASURED, like-for-like on the SAME BUILD.** `C2_RETRIEVAL_ENABLED`
exists precisely so the with- and without-retrieval figures are not two
different commits. Same four turns, same model
(`gemma4-e4b-bakeoff:latest`, blob digest
`sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`),
same embedding model (`nomic-embed-text:latest`, blob digest
`sha256-970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6`,
reverified on this box this session and matching DR-033's recorded value),
live 16 GiB carve:

  - retrieval stage (embed + Chroma query): 0.0001 s OFF, **0.028–0.074 s
    ON** (embed ~0.022–0.044 s, query ~0.0045–0.038 s).
  - C2 prefill: **0.210–0.294 s OFF, 1.480–1.980 s ON.**
  - Ollama `prompt_eval_count`: 125–167 OFF, 867–1163 ON.

**THE FINDING: retrieval costs about +1.4 s per turn at C2, and only ~3% of
that is the retrieval stage itself.** The embed-and-query work everyone
would naturally call "the retrieval cost" is ~40 ms. The other ~1.4 s is
prefilling the ~800 evidence tokens appended to the prompt, and it lands in
`c2_prefill_s`, not in `retrieval_s`. Anyone optimising the vector search
here would be optimising 3% of the problem.

**WHY THE CACHED PREFIX SAVES SO LITTLE AT D0, AND WHY THIS IS NOT A
DR-013(a) VIOLATION.** DR-013(a) is honoured exactly — evidence is appended
strictly after the transcript, proven by test and by live micro-check, and
the shared literal prefix holds turn over turn. But G1 measured a ~5,000-token
stable prefix with ~200 tokens appended. D0 has the INVERSE ratio: a
~110-token stable prefix (preamble plus a short rolling transcript) with
~800–1,000 tokens of fresh evidence appended every turn. The cache hits;
there is simply almost nothing in it worth hitting. **The value of
DR-013(a)'s constraint grows with transcript length, and D0's transcripts
are short.** This does not weaken the constraint — violating it would still
force a full cold prefill and is still the 5-11 s regime — but it does mean
the constraint is not, on its own, buying back what retrieval costs at this
stage of the build. Recorded because the natural misreading of a good
prefill number would be that evidence is cheap, and at D0 it is not.

**What this entry does NOT yet contain.** The end-to-end T_ttfa median and
p90 with retrieval, against DR-026's D0 anchor and DR-017's 8 s kill
switch. That needs the operator on the headset for a twenty-turn spoken
run, prepared and handed over by this thread and not driven from chat
(relaying prompts through a turn-based channel distorts the measurement).
The figure lands as its own entry on the operator's return. Projecting from
the +1.4 s C2 delta alone would put the median near 4.5 s against an 8 s
kill switch — that is an ARITHMETIC EXPECTATION, explicitly not a
measurement, and it is recorded here only so a surprise in either direction
is visible as a surprise.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.

## 2026-09-07 — Thread 1.0.14 (continued): Bar B re-measured with retrieval wired in

### DR-038 — BAR B WITH RETRIEVAL: T_ttfa MEDIAN 4.035 s / p90 4.763 s AT THE LIVE 16 GiB CARVE. DR-017'S KILL SWITCH DID NOT FIRE. RETRIEVAL COSTS ~1.19 s OF WHICH THE VECTOR SEARCH IS 0.030 s; THE p90 COMPARISON AGAINST D0 IS REPORTED BUT NOT RELIED ON (2026-09-07)

**Run identity, recorded with the figure per DR-020's standing convention.**
Twenty spoken turns over the bonded headset on HFP/mSBC, driven by the
operator in their own SSH terminal (not from chat), logs in
`logs/run_20260907T140308Z`. Live UMA carve 17,179,869,184 bytes = 16.00
GiB, read from sysfs by the harness at compute time, not assumed. Kernel
`7.0.0-31-generic`. Reasoning model `gemma4-e4b-bakeoff:latest`, blob digest
`sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`.
Embedding model `nomic-embed-text:latest`, blob digest
`sha256-970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6`.
Both digests read from the run's own structured logs, which C2 emits per
turn, rather than from the environment afterwards. 20 of 20 turns produced
complete stage logs; none was excluded.

**THE FIGURE. T_ttfa median 4.035 s, p90 4.763 s.** Decomposition (medians):
ASR tail 0.816 s, **retrieval 0.030 s**, C2 prefill 1.588 s, C2 generate
0.846 s, TTS 0.790 s. Partition integrity `partition_gap_median_s` 0.0068 s
and `partition_gap_max_s` 0.0202 s — the re-anchored partition (DR-037)
adds up, so the retrieval stage is neither double-counted nor hidden.
Post-T_ttfa playout 3.198 s, reported separately and never inside the
partition. Retrieval volume: 6 chunks and 710 estimated evidence tokens per
turn at the median, against Ollama-reported prompts of 1,020 tokens.

**DR-017'S KILL SWITCH DID NOT FIRE.** The bar is median > 8 s; the measured
median is 4.035 s. Recorded as a pass on that specific bar and nothing more
— no other Bar B criterion is claimed as met by this entry.

**AGAINST D0'S ANCHOR, stated plainly as this thread was instructed to.**
D0's anchor is 3.076 s median / 4.959 s p90. Median moves 3.076 -> 4.035,
i.e. **retrieval costs +0.959 s, a 31% increase in median first-audio
latency.** That is the headline cost and it is real.

**The p90 comparison is reported and then explicitly NOT relied on.** p90
moves 4.959 -> 4.763, i.e. this run's p90 is 0.196 s BETTER than the
no-retrieval anchor. It would be convenient to present that as retrieval
being free at the tail and it is not offered that way. Three reasons for
distrusting it, recorded rather than glossed: (1) DR-028 held the anchor
run's figure PROVISIONAL pending a clean re-run, and that clean re-run has
still not happened, so the p90 being compared against is itself unsettled;
(2) re-decomposing `logs/run_20260907T095156Z` with this session's harness
yields 2.705 s / 4.987 s rather than 3.076 s / 4.959 s, and this session
could not determine from the logs alone which run the anchor came from —
the discrepancy is flagged, not silently reconciled, and the instructed
anchor was used for the comparison above; (3) p90 over 20 samples is the
second-largest value and is dominated by whichever single turn happened to
be slowest. **The median comparison is the one to carry forward. The p90
comparison should be re-made after DR-028's clean baseline re-run exists.**

**WHERE THE COST ACTUALLY IS, now measured on a real spoken run rather than
a smoke test.** Regressing per-turn C2 prefill on per-turn evidence tokens
across the 20 turns: **r = 0.965**, slope **1.634 ms per evidence token**
(~612 evidence tokens/s), intercept 0.388 s. So the median 710 evidence
tokens cost **~1.16 s of prefill**, and the retrieval stage proper — embed
plus Chroma query — costs **0.030 s**. Total retrieval cost ~1.19 s, of
which the vector search is **2.5%**. This confirms DR-037's smoke-test
finding on live spoken data and at higher confidence: anyone tuning the
vector search here would be tuning 2.5% of the problem, and the lever that
matters is the number of evidence tokens appended.

**AN ACCIDENTAL IN-RUN CONTROL, worth more than a deliberate one.** Turn 5
transcribed to ZERO characters (the operator's speech was not captured;
turn_id `9fe09dbf-a3fa-4feb-ae87-71ca653fd32f`). C2's empty-query guard
behaved exactly as designed — retrieval returned nothing, 0 chunks, 0
evidence tokens, retrieval stage 0.0000 s — and that turn's prefill was
**0.297 s against a 1.588 s median for the retrieval turns.** That single
turn is an unplanned zero-evidence control inside the same run, same model
load, same carve, and it sits close to the 0.388 s regression intercept
derived independently from the other nineteen. Two independent estimates of
"prefill without evidence" agreeing is stronger evidence for the ~1.2 s
retrieval cost than either alone.

**TWO OBSERVATIONS RECORDED, NEITHER FIXED HERE.**
  - **DR-028's degenerate-repetition behaviour recurred, and grounding did
    not prevent it.** Twelve of twenty replies opened "It sounds like",
    and seven contained "circling back"/"circle back". DR-028 explained
    this as benign D0 behaviour under a repetitive Bar B transcript rather
    than a defect; that explanation is not overturned here, but it is now
    observed WITH corpus evidence in the prompt, which is new information:
    retrieved grounding did not pull the model out of the pattern. Carried
    to `BACKLOG.md`. It does not affect the latency figure, which is what
    this entry measures.
  - **A zero-character transcript still consumed a full turn.** C1 returned
    an empty transcript and C5 drove the whole C2/C4/playout path anyway,
    so Jester spoke ("It sounds like there's a spirited debate happening.")
    in response to silence. Harmless at D0 and useful here as a control,
    but a real deployment must not answer nothing. Carried to `BACKLOG.md`.

**CLEAN ON EVERY OTHER AXIS SWEPT.** Zero preamble leaks (DR-027/DR-028's
mitigation held for twenty turns with evidence appended), zero prompt
overflows (DR-036's arithmetic said twenty turns was nowhere near the 8192
ceiling and it was), `retrieval_enabled` true on every turn (so this is not
a baseline run mislabelled), Tier 2 consulted on 19 of 20 turns and
returning nothing every time because 2a/2b are empty, and **zero bracketed
citation markers or source filenames reached the spoken output** — the risk
this thread flagged against `c4_speech/text_filter.py`, which strips
emoji/stage-directions/control-markers but NOT `[source #N]` brackets, did
not materialise this run. That is one clean run, not a fix; the gap in
`text_filter` is real and remains carried in `BACKLOG.md`.

This entry is an append; no prior entry above is edited, per the append-only rule for
this file.
