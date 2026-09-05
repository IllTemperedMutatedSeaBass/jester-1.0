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
