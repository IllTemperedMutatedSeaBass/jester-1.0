# RELAY.md — Jester 1.0 STOP report relay

> **Append-only**, same discipline as `DECISIONS.md`. Every CC session that
> commits work to this repo appends its STOP report here before closing,
> commits, and pushes. Entries are never edited after the fact; corrections
> are new entries. Old entries may be pruned like BACKLOG Done cards (git
> history preserves them). Convention defined in `jesterai/WAYS_OF_WORKING.md`
> §1.

---

## 2026-09-04 — Thread 1.0.4 (continued)

MODEL: Sonnet 5, thinking on — operator-declared, echoed verbatim as an
operator claim, not independently verified.

This repo's scaffold (all 17 files, root commit `3eabf08`) was created by a
prior run of this thread and found already correct and complete on
re-inspection this session; no changes were made here. This session's only
substantive work was in `jesterai` (DR-016) — see that repo's `RELAY.md`
for the full report.

**BLOCKER, unchanged from the prior run:** this repo still has no `origin`
remote. `git remote -v` returns nothing;
`git ls-remote git@github.com:IllTemperedMutatedSeaBass/jester-1.0.git`
returns "Repository not found." Nothing in this repo has ever reached a
remote, so no proof-of-push can be offered for it, and this entry itself
cannot be pushed — it is committed locally only, pending the GitHub repo's
creation (a MANUAL STEP, see `jesterai/RELAY.md`).

This is disclosed rather than papered over: this RELAY.md entry exists
only in the local working tree at commit time and will need to be pushed,
along with everything else in this repo, once the remote exists.

### Proof-of-push addendum (remote wired)

The `origin` remote has now been wired to
`git@github.com:IllTemperedMutatedSeaBass/jester-1.0.git`, and `main` has
been pushed successfully with upstream tracking set. Commit
36d3bfc9e157a2cbf715bae82b410ed3352e67bc is on origin/main. This hash was
read from origin after an independent `git fetch origin`, checking the
`origin/main` ref.

## 2026-09-05 — Thread 1.0.5: pass bar and C4 engine direction

MODEL: Sonnet 5, thinking on — operator-declared, echoed verbatim as an
operator claim, not independently verified.

**WHY THIS SESSION EXISTS.** A prior draft of this task directed two
stream-level decisions (the D0 walking-skeleton pass bar, and the C4 TTS
engine direction) to be filed in `jesterai/DECISIONS.md`. That was wrong
under `jesterai/DECISIONS.md` DR-016 (2026-09-04), which ruled that from
DR-017 onward, 1.x stream decisions are filed in `jester-1.0/DECISIONS.md`,
while `jesterai` retains only PORTFOLIO- and BOX-level decisions. The error
was caught by CC before any edit was made, and this session was run to
file the two entries in the correct repo. A companion session on
`jesterai` carries the box-level items these entries reference (the
Bluetooth transport UMA carve, HeathenS's model-cache/runtime-fetch
collision with DR-014, and the Glow-TTS/Kokoro sample-rate mismatch as
recorded there).

**MACHINE.** Ran on the Jester box over SSH as `jester`, interactive
session. `hostname` confirmed `jesterai`; `pwd` confirmed
`/home/jester/jester-1.0` at launch — no divergence to report.

**SCOPE.** Confined to `/home/jester/jester-1.0` for the entire session.
`jesterai`, `jester-2.1`, and any `HeathenS_Talkings` clone were not read,
written, or subject to any git command this session.

**BRANCH AUTHORITY.** Task named `main`; session was already on `main`
with no harness-assigned branch to reconcile.

**PULL BEFORE EDITING.** `git pull origin main` run before any edit;
repository was already up to date with `origin/main` and the working tree
was clean.

**FILES CHANGED.**

- `DECISIONS.md` — **appended**, under a new dated heading "## 2026-09-05
  — Thread 1.0.5: pass bar and C4 engine direction": DR-017 (D0
  walking-skeleton pass bar, Bars A/B/C) and DR-018 (C4 engine direction —
  HeathenS_Talkings long-term, kokoro for D0, engine-agnostic interface).
  No existing entry edited or renumbered.
- `BACKLOG.md` — **edited**: added two sub-bullets under the existing
  walking-skeleton item pointing at DR-017 and DR-018. Nothing else in the
  file changed.
- `RELAY.md` — **appended**: this entry.

**DR NUMBERING.** `DECISIONS.md` contained no DR entries in this repo
before this session (its header text, written before DR-016 was filed,
still read "the next free number in this repo is DR-016" — stale given the
DR-016 ruling that DR-016 itself lives in `jesterai/DECISIONS.md` and only
DR-017 onward move here). Per the task's instructed reading — no entries
present, so start at DR-017 and DR-018, continuing the shared cross-repo
number series while changing only the home — this session assigned
**DR-017** and **DR-018**. Prior highest confirmed DR number, per the
standing ruling given as context (`jesterai/DECISIONS.md` DR-016,
2026-09-04), was **DR-016**.

**CONFIRMATION.** `jesterai`, `jester-2.1`, and `HeathenS_Talkings` were
not touched — no read, write, or git operation against any of them this
session.

### Proof-of-push

Commit 01c10160aecedbc295422c9c2d43bf0e9dc93d57 is on origin/main. This
hash was read from origin after an independent `git fetch origin`,
checking the `origin/main` ref.

## 2026-09-05 — Thread 1.0.6 (Phase 1 recon + blocked at Stage 2): model-tag mismatch

MODEL: Sonnet 5, thinking on — operator-declared, echoed verbatim as an
operator claim, not independently verified.

**MACHINE.** Launched from `/home/jester` per the prompt. `hostname`
confirmed `jesterai`. `git fetch origin` + `git pull` run before any edit;
this repo was at `80d02c643828338e79094a71378aa84b16a727f5` on
`origin/main`, matching, working tree clean — no divergence.

**TWO-PHASE STRUCTURE.** Phase 1 was read-only recon, reported in full to
the operator and held for a "GO PHASE 2" confirmation, which was given.
Phase 2 began in stage order (Stage 1 — carve correction in `jesterai`;
Stage 2 — skeleton code in `jester-1.0`). Stage 1 completed in full (see
`jesterai/RELAY.md` this date). Stage 2 is **BLOCKED before any code was
written**, on the operator's own ruling 1: `ollama show
gemma4-e4b-bakeoff:latest` was required before pinning `OLLAMA_MODEL`, and
it resolved to Gemma 4 architecture (7.5B params), not Gemma 3n E4B. Per
the ruling, no substitute tag was picked; DR-019 (below) records the
finding and this session stops here to report rather than guess.

**FILES CHANGED THIS SESSION.**

- `DECISIONS.md` — **appended**: DR-019, "gemma4:e4b" never existed on this
  box; true anchor identity recorded" — the `ollama show`/`api/show` output
  for the closest-matching tag, and the explicit statement that
  `OLLAMA_MODEL` is not pinned by this session. No prior entry edited.
- `RELAY.md` — **appended**: this entry.
- No application code was written this session. Stage 2 (skeleton code)
  and Stage 3 (Bar B harness) have not started.

**WHY THIS SESSION STOPS HERE.** The operator's ruling was explicit:
"[i]f it does not [resolve to Gemma 3n E4B], stop and report — do not pick
another tag," citing G3(b)'s mis-specified-anchor failure as the precedent
not to repeat. Building C2 against a guessed model tag would be exactly
that repeat. The rest of the skeleton (C1, C3, C4, C5) does not strictly
require this decision, but Stage 2 as briefed treats the model pin as part
of one coherent build stage, and starting it in a half-configured state
risks the same class of silent-guess error the ruling exists to prevent.
Awaiting the operator's decision on which tag (if any) is the correct
`OLLAMA_MODEL` before resuming Stage 2.

**UNTOUCHED-REPO PROOF, `jester-2.1`.** Not read, written, or subject to
any git command this session. HEAD was not recorded at session start
(out of scope per the prompt: "Not to be touched, read, or subject to any
git command") — no before/after comparison is offered because none was
taken, consistent with never having run `git` against it.

**HeathenS_Talkings.** Confirmed absent from this box again this session
(`find /home/jester -maxdepth 2 -iname "*heathen*"` returned nothing,
both before and after this session's edits) — nothing to touch, nothing
changed.

### Proof-of-push

Commit fc7017ef929b6e7e880c9dbe8ca5b5ffb058a478 is on origin/main. This
hash was read from origin after an independent `git fetch origin`,
checking the `origin/main` ref.

## 2026-09-05 — Thread 1.0.6 (resumed): skeleton built, Bar B harness written, three findings filed

MODEL: Sonnet 5, thinking on — operator-declared, echoed verbatim as an
operator claim, not independently verified.

**RESUMPTION.** This continues the same thread-1.0.6 session whose first
half stopped before Stage 2 (see the entry immediately above) pending an
operator ruling on `OLLAMA_MODEL`. The operator ruled: pin
`gemma4-e4b-bakeoff:latest`, correcting DR-019's parameter-count reasoning
(E4B ≈4B *effective* params via per-layer-embedding offload, ~7.5–8B raw
checkpoint — 7.5B is consistent with E4B, not disproof of it), and
supplied cheap-evidence steps (a)/(b)/(c) to run before writing code.
Those ran first; results are in DR-020.

**CHEAP EVIDENCE RESULTS (DR-020).** (a) `ollama show --modelfile` FROM
line points at a local blob path, no upstream tag to cross-check. (b)
`jester-gen:latest` and `gemma4-e4b-bakeoff:latest` share the identical
blob digest `sha256-90ce98129eb3e8cc57e62433d500c97c624b1e3af1fcc85dd3b55ad7e0313e9f`
— confirmed alias pattern. (c) manifest mtime **NOT OBTAINED** —
`~/.ollama/models/manifests/` is owned by the `ollama` service account,
permission denied to `jester`, no sudo authorised. None of the three
settles whether this blob is what G1/G3/the 10.5s 2.x cycle actually
measured; DR-020 states that plainly as UNPROVEN rather than resolving it
by assertion.

**STAGE 2 — SKELETON CODE, written, not run end-to-end.** Five packages:
C1 (faster-whisper + energy-VAD endpointer, batch-per-turn per ruling —
`POST /transcribe` blocks until VAD declares end-of-speech), C3 (stub,
`POST /decide` always returns `speak_now`, NOT wired into the loop per
ruling), C2 (stable-prefix-plus-append `PromptBuilder`, evidence appended
strictly after the transcript per DR-013a, `PromptOverflowError` raised
loudly on num_ctx overflow rather than inventing a truncation policy per
DR-013b, prefill/generate split logged from Ollama's own
`prompt_eval_duration`/`eval_duration` — no separate probe needed), C4
(engine-agnostic `TTSEngine` interface per DR-018, `KokoroEngine`
implementation, WAV-encodes PCM+sample_rate so C5 doesn't need
out-of-band sample-rate knowledge), C5 (pure HTTP client/driver, no
listener, per ruling — drives C1→C2→C4 per turn, plays WAV via
`sounddevice`). `ops/run_d0.sh` is the one-command entry point: starts
C1/C2/C4 in the foreground, health-checks each, then runs C5 — no
systemd, no manual step between components, per Bar A/C. All five
packages have their own venv, installed cleanly from PyPI with no missing
Python dependency.

**SMOKE-TESTED, not the real loop:** C2's `/respond` against the real,
running Ollama with the pinned model (full prefill/generate log lines
emitted correctly) and C4's `/synthesize` against the real Kokoro weights
(WAV bytes returned, structured logs correct) both verified via
`TestClient`. C3 verified via `TestClient`. The Bar B harness's
decomposition math verified against hand-built synthetic log events. C1
and C5 could NOT be smoke-tested: `import sounddevice` raises `OSError:
PortAudio library not found` — `libportaudio2` is not installed on this
box, needs `sudo apt install libportaudio2`, not attempted (no sudo
authorised; reporting per the "stop rather than install
un-authorised things" instruction).

**A separate, unplanned finding surfaced while smoke-testing C2:** the
pinned model's completion text decoded to empty (`response: ""`) despite
`eval_count: 40` real tokens generated — the Modelfile's bare
`{{ .Prompt }}` template has no chat-turn wrapping for a model whose
tokenizer clearly expects turn markers (visible in the raw `context`
token ids). Recorded in `BACKLOG.md`, not investigated further —
prompt-template tuning is out of this session's scope (wiring, not
correctness of replies) — but flagged because an empty completion may
skew Bar B's T_ttfa via near-silent TTS output.

**STAGE 3 — BAR B HARNESS, written, NOT RUN (per explicit instruction).**
`c5_orchestrator.bar_b_harness`: reads the four components' JSONL stderr
logs (written by `run_d0.sh` to `logs/{c1,c2,c4,c5}.jsonl`), groups by
turn_id, computes per-turn ASR-tail/C2-prefill/C2-generate/TTS/playout
durations plus T_ttfa (VAD endpoint → playout_start), reports
median/p90, and refuses to run (raises rather than defaulting) if the
UMA carve can't be read from sysfs. All monotonic timestamps are
comparable across these processes because they share one host and one
`CLOCK_MONOTONIC` — noted in the module docstring as NOT true once any
component moves machines. The external-recorder click-calibration hook
exists (`run_calibration_click_hook`) and raises `NotImplementedError` —
not automated, not attempted, needs the operator physically present.

**Incidental finding while building the harness (DR-021): the live UMA
carve is NOT 16 GiB.** `cat /sys/class/drm/card0/device/mem_info_vram_total`
returned 2147483648 (2 GiB) against the documented "16 GiB (INTERIM)."
`journalctl -k`/`journalctl -u ollama` corroborate: a 2048M VRAM BAR plus
14600M GTT, Ollama consistently reporting `total="14.3 GiB"` compute
since the current boot (2026-09-04 ~18:02, no reboot since). Plausibly a
leftover from the same-day BIOS Auto/Specified exploration (thread
1.0.6's Stage 1), not confirmed. No BIOS change made or proposed — DR-021
flags this for the operator to check before trusting a real Bar B run's
carve figure.

**KOKORO WEIGHTS MOVED (per ruling).** `kokoro-v1.0.onnx` and
`voices-v1.0.bin` moved from `/tmp` to `/home/jester/models/kokoro/`
(outside both repos, nothing committed). SHA-256 verified identical
before and after: `7d5df8ec...36a6c5` (onnx) and `bca610b8...29f1fbf7d`
(voices bin). `.env.example`'s `KOKORO_WEIGHTS_PATH`/`KOKORO_VOICES_PATH`
point there now. `BACKLOG.md` notes provisioning into the D0 image is
still open per DR-014.

**FILES CHANGED, this half of the session.**

- `DECISIONS.md` — **appended**: DR-020 (model-tag correction, pin,
  cheap-evidence results, standing tag+digest convention) and DR-021
  (live carve discrepancy, flagged not acted on). No prior entry edited.
- `.env.example` — **edited**: `OLLAMA_MODEL`/`OLLAMA_MODEL_DIGEST` pinned
  per DR-020, `C2_MAX_TOKENS`, `C1_WHISPER_MODEL`/`COMPUTE_TYPE`,
  `C4_TTS_ENGINE`, Kokoro paths repointed to `/home/jester/models/kokoro/`,
  `C5_TURN_COUNT`/`C5_BAR_B_TURN_COUNT` added.
- `.gitignore` — **edited**: added `logs/` (structured-log output,
  Bar B harness input, not committed).
- `BACKLOG.md` — **edited** (not append-only per this repo's convention;
  BACKLOG.md is a working list, unlike DECISIONS.md/RELAY.md): restructured
  around what's built vs. what's blocking a real run; added the
  libportaudio2 and DR-021 blockers, the C2-empty-response finding, the
  Kokoro-provisioning-still-open note, and a Done section.
- Five packages' `pyproject.toml` — **edited**: dependencies declared.
- ~20 new source files across `c1_capture`, `c2_reason`, `c3_router`,
  `c4_speech`, `c5_orchestrator` — **created** (listed in the commit).
- `ops/run_d0.sh` — **created**: the one-command entry point.
- `RELAY.md` — **appended**: this entry.
- Outside git: five `.venv/` directories created and populated (gitignored);
  Kokoro weights moved as described above (outside both repos).

**MANUAL-STEPS / IMPLICIT INSTRUCTIONS NOT ACTED ON.** No systemd units,
no `ollama cp`/aliasing, no writes to `/run/jester` or `/var/log/jester`,
no sudo, no runtime weight fetch (Kokoro weights already on disk, just
relocated) — Bar C constraints observed throughout.

**UNTOUCHED-REPO PROOF.**

- `jester-2.1`: this session's explicit scope said "Not to be touched,
  read, or subject to any git command" — no `git` command was run against
  it, which means no HEAD SHA can be quoted for it without violating that
  same instruction. This is flagged as a genuine conflict between that
  scope rule and this stage's generic "quote HEAD SHA before/after for
  any such repo present" instruction: the more specific, explicit
  per-session scope rule was treated as controlling, and no git command
  was run. (jester-2.1 is present on the box, per Phase 1's `ls
  -d /home/jester/jester-2.1`, itself a filesystem check, not a git
  operation.)
- `HeathenS_Talkings`: confirmed absent from the box, again, this half of
  the session (`find /home/jester -maxdepth 2 -iname "*heathen*"`
  returned nothing) — nothing to touch, nothing changed, no git operation
  possible against a repo that doesn't exist.

### MANUAL STEPS REMAINING

- `sudo apt install libportaudio2` on the Jester box — blocks C1 and C5
  from running at all (`sounddevice` import fails without it). Not
  something CC can do this session (no sudo authorised).
- Confirm what the BIOS UMA carve is actually set to right now (DR-021
  found a live 2 GiB reading against a documented 16 GiB) and restore the
  intended value before a real Bar B run, if 2 GiB wasn't intentional.
- Copy `.env.example` to `.env` at the repo root before running
  `ops/run_d0.sh` (the script requires `.env` to exist).
- Run the actual Bar B measurement once the above two are resolved —
  needs the operator on the headset; not run this session per explicit
  instruction.
- **Sync now** on the jester-1.0 project for all files changed this
  session.
- Project-knowledge allowlist: the new package source files (under
  `c1_capture/src/`, `c2_reason/src/`, `c3_router/src/`, `c4_speech/src/`,
  `c5_orchestrator/src/`) and `ops/run_d0.sh` may need adding if the
  allowlist is per-file rather than per-directory.
- Chat rename check: confirm this chat is numbered 1.0.6 with a short
  descriptive title.

### Proof-of-push
