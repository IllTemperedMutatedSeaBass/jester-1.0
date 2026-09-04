# Jester 1.0 — meeting intelligence appliance

A distributed, self-hosted meeting intelligence appliance: capture live
meeting audio, transcribe and diarize it, reason over it against a retrieved
knowledge base, and — the distinguishing feature — interject into the
meeting in real time with spoken output when it has something worth saying.

## Demo ladder

| Rung | Audio | People | Speaker handling | Scope |
|---|---|---|---|---|
| **D0** | Bluetooth headset | scripted 1-on-1 | none | Full loop end-to-end with hand-up etiquette. No diarisation, no far-field. |
| **D1** | USB conference speakerphone (hardware AEC) | 2–3 people in a room | speaker **CHANGE** detection only | Proves it survives a room. |
| **D2** | as D1 | live meeting | speaker **IDENTITY** diarisation | Attributed transcript, post-meeting record. Original target. |

## Five components

- **C1 — Capture / transcription.** Audio capture, transcription, diarization
  (VAD/endpointing and speaker-change detection at D1; speaker identity
  deferred to D2).
- **C2 — Reasoning / RAG.** Retrieval over the knowledge base plus LLM
  inference. The only component where hardware sizing carries real cost.
- **C3 — Interjection router.** Decides whether and when to interject; a
  tiny, cheap gate on a continuous stream. Stubbed — not in the D0 walking
  skeleton.
- **C4 — Speech synthesis.** Text-to-speech via Kokoro.
- **C5 — Orchestrator.** A plain Python state machine coordinating the loop.

## Methodology

Working conventions (git discipline, branch/machine authority, proof-of-push,
STOP reports, DR numbering) live in `CLAUDE.md`, sourced from the `jesterai`
meta repo (`WAYS_OF_WORKING.md`) — the methodology source of record. This
repo does not restate methodology beyond the operational summary in
`CLAUDE.md`.
