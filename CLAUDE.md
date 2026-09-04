# CLAUDE.md — Jester 1.0 operational conventions

This file carries the operational conventions a Claude Code (CC) session
reads automatically at session start, so prompts don't need to restate them.
It is sourced from `jesterai/WAYS_OF_WORKING.md` §1/§3/§4, which remains
canonical — when conventions change there, this file is updated to match.
Product/architecture context lives in `jesterai/SEED_jester-1.0.md`, not here.

## Default working directories

- **Jester box (SSH):** `/home/jester/jester-1.0`
- **Windows laptop:** `D:\github\jester-1.0`

## Git discipline

Pull first → edits → single logical commit per repo (or clearly separated
commits if the change genuinely spans concerns) → push. Never start work on
a stale checkout.

## Branch authority

The branch named in the prompt always wins over a session-harness-assigned
branch (e.g. `claude/<something>`). When provisioned onto a harness branch
and the prompt names a different one, check out and work on the prompt's
branch. Never push to a harness branch. The conflict is never silent: every
STOP report where this fires records the harness-assigned branch, the
branch named in the prompt, which was used, and what was done with the
other one.

## Machine authority

Every prompt names its target machine; every session verifies at start that
it is actually running there (hostname, working directory, and any mounts
or services the work depends on). Where they diverge, the divergence is
reported **before** any work begins, and the session proceeds only with
work that is machine-independent. Any change targeting machine-specific
state (systemd units, mount paths, provisioning, anything reading live
mounts or the live working set) is deferred rather than written blind, and
the divergence plus what was deferred are both recorded in the STOP report.

## Proof-of-push

Every STOP report from a session that commits work must include:

- a `git log` excerpt with real commit hashes, verified against `origin`
- **in addition**, the full 40-character commit SHA stated as a plain
  sentence in running prose — not inside a code fence, not inside backticks
  — e.g. "Commit 7ebbbfb427d1a383c60473310a267a846606d772 is on
  origin/main."
- a prose statement that the hash was read from `origin` after an
  independent `git fetch`, naming the ref checked

A fenced code block alone does **not** satisfy this rule: fenced output does
not reliably survive copy-paste out of a terminal into a chat, and the
evidence evaporates with it. A session's own claim of "done" is not
evidence.

## STOP report convention

Every file-changing session ends by appending its STOP report to
`RELAY.md`, committing, and pushing. `RELAY.md` is append-only: entries are
never edited after the fact; corrections are new entries.

## Manual steps remaining

Every file-changing session ends by printing a block listing the Claude.ai
UI actions CC cannot perform itself:

- **Sync now** on affected project(s)
- **project-knowledge allowlist** additions, if new files should sync
- **chat rename** check (thread number + short descriptive title)

## Append-only files

`DECISIONS.md` and `RELAY.md` are append-only. Entries are never edited or
renumbered after the fact; corrections are new entries.

## DR numbering

This repo's DR series **continues from DR-016** — it does not restart at
DR-001. DR-002 through DR-015 were filed in `jesterai/DECISIONS.md` before
this repo existed, remain frozen there, and are never renumbered or copied
here. Always check the highest DR number across **both** `DECISIONS.md`
(this repo) and `jesterai/DECISIONS.md` before assigning a new one.

## Project-structure discipline (day one, non-negotiable)

Per `jesterai/SEED_jester-1.0.md` §7:

- **Five separate Python packages**, each with its own `pyproject.toml` and
  venv (`c1_capture`, `c2_reason`, `c3_router`, `c4_speech`,
  `c5_orchestrator`).
- **HTTP between components even on localhost** — no in-process shortcuts.
- **All addresses, ports and credentials in environment variables** — never
  hardcoded, never assumed co-located.
- **Structured JSON logging** across all components.

Skipping this turns the later hardware port from a one-day exercise into a
one-month rewrite: components are only free to move between machines if
that property is built in from the start.
