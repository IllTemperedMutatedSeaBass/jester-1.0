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
