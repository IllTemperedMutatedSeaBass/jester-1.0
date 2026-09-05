# BACKLOG.md — Jester 1.0

## Open

- **Walking skeleton: headset → Whisper → gemma → Kokoro → headset (DR-014).**
  No interjection logic, no retrieval, no diarisation. Purpose: the first
  honest first-audio figure under real HFP conditions.
  - Pass bar fixed before build, three parts (DR-017): binary build bar
    (Bar A), a measured T_ttfa figure with a kill-switch at median > 8 s
    with the cap in place (Bar B, no pass side otherwise), and a
    coexistence bar protecting the 2.x demo (Bar C). C4 engine direction
    is HeathenS_Talkings, with kokoro as the D0 measurement engine and C4
    built engine-agnostic (DR-018).

- **Two carried G1 constraints (DR-013), both binding on C2's design:**
  - Retrieved evidence must be appended AFTER the rolling transcript, never
    inserted before it — anything prepended invalidates the cached prefix and
    returns first-audio latency to the 5-11 s regime.
  - num_ctx is 8192; a real meeting overflows it in 30-45 minutes. How to
    truncate the transcript WITHOUT destroying the cached prefix is
    UNDECIDED.

## Done

(none yet)
