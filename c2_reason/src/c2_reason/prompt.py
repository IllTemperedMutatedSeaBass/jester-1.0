"""Stable-prefix-plus-append prompt builder (exercises G1 prefix reuse).

DR-013's two carried constraints, both enforced here:
  (a) Retrieved evidence, when it exists, must be appended AFTER the rolling
      transcript, never inserted before it -- prepending invalidates the
      cached prefix and returns first-audio latency to the 5-11s regime.
  (b) num_ctx is 8192 with transcript truncation UNDECIDED (D0 design
      question, not a tuning detail). This module does not invent a
      truncation policy: PromptOverflowError is raised loudly instead, so
      the failure is visible rather than silently masked by an ad-hoc cut.

There is no retrieval yet at D0 (C3 is a stub, no interjection logic), so
evidence is always empty here -- the append-after-transcript seam exists
and is exercised by the signature, not by live content.

Per DR-024, the stable prefix and any appended evidence are wrapped in a
single hand-rendered Gemma user/model turn (`<start_of_turn>user\\n ...
<end_of_turn>\\n<start_of_turn>model\\n`) and sent to Ollama's
`/api/generate` with `raw: true` (see `ollama_client.generate`). This
bypasses the pinned Modelfile's server-side chat renderer, which DR-024
measured as putting the model into an unbounded "thinking" mode that
consumes the entire token cap before any final content -- with the hand
-rendered turn markers, the model responds directly instead. The closing
markers are a fixed suffix after the (evidence-extended) transcript, so
they do not change DR-013a's append-after-transcript ordering or the
cached-prefix property G1 measured.

DR-027 investigation (thread 1.0.11, live Bar B run): turns 6 and 9 of that
run synthesized a truncated (40-token-cap) copy of `STABLE_PREAMBLE`
instead of a reply. Reproduced live (repo not included -- this docstring
records the finding): sending Ollama's raw-mode `/api/generate` a growing,
largely repetitive transcript (short filler lines, no substantive new
content, which is exactly what a timing-calibration Bar B script looks
like) makes the model progressively more likely to fall into degenerate
completion -- first repeating near-identical short replies, then
eventually copying nearby prompt text verbatim, including the preamble
sitting at the very top of the same prompt. `raw: true` gives no chat
-template-enforced turn boundary, and the `stop: ["<end_of_turn>"]` added
this session only catches the LITERAL string if the model happens to emit
it -- it does not stop a degenerate continuation that never attempts to
close the turn, so generation runs to the 40-token cap instead. `_REMINDER`
below is a recency-placed mitigation (the closer an instruction sits to
the generation point, the more weight raw-mode completion tends to give
it) placed after the transcript/evidence and before the closing markers,
not folded into `STABLE_PREAMBLE` itself, precisely so it stays close to
generation regardless of how long the transcript grows. `PREAMBLE_LEAK_SIGNATURE`
is exported so `respond()` can detect the failure mode when the mitigation
doesn't prevent it and log+strip it rather than return it as a valid
reply; `c4_speech.text_filter` carries its own independent copy of the
same signature as a second line of defense, since components are HTTP
-only and do not share code (project-structure discipline).
"""


class PromptOverflowError(RuntimeError):
    pass


STABLE_PREAMBLE = (
    "You are Jester, a meeting assistant. Respond briefly and naturally "
    "to the ongoing conversation below. Your reply is spoken aloud, not "
    "read: never include emoji, asterisked stage directions (e.g. "
    "*laughs*), or parenthetical narration -- write only the words to be "
    "spoken.\n\n"
)

# First few words of STABLE_PREAMBLE, normalized (lowercased, single
# spaces). A leaked/echoed preamble always starts here even when
# truncated by the token cap partway through, so this is what
# respond()/text_filter check for -- not an exact-match of the whole
# preamble, which a truncated leak would never satisfy.
PREAMBLE_LEAK_SIGNATURE = "you are jester, a meeting assistant"

# Recency-placed anti-echo reminder (DR-027): kept separate from
# STABLE_PREAMBLE and re-appended fresh every turn immediately before the
# model's turn starts, regardless of how long the transcript has grown.
_REMINDER = (
    "\n\n(Reply now with your own new words, addressing what was just "
    "said. Do not repeat or restate the instructions above.)"
)

_TURN_OPEN = "<start_of_turn>user\n"
_TURN_CLOSE = "<end_of_turn>\n<start_of_turn>model\n"


class PromptBuilder:
    """Owns the stable prefix (preamble + rolling transcript) and appends
    retrieved evidence (if any) strictly after it, never before."""

    def __init__(self, num_ctx: int, chars_per_token_estimate: float = 4.0):
        self.num_ctx = num_ctx
        self._chars_per_token_estimate = chars_per_token_estimate
        self._transcript_lines: list[str] = []

    def append_transcript_line(self, speaker: str, text: str) -> None:
        self._transcript_lines.append(f"{speaker}: {text}")

    def _stable_prefix(self) -> str:
        return STABLE_PREAMBLE + "\n".join(self._transcript_lines)

    def build(self, evidence: str | None = None) -> str:
        """Stable prefix first, evidence appended AFTER it (DR-013a), the
        whole turn wrapped for raw-mode `/api/generate` (DR-024)."""
        body = self._stable_prefix()
        if evidence:
            body = body + "\n\n[Evidence]\n" + evidence
        body = body + _REMINDER
        prompt = _TURN_OPEN + body + _TURN_CLOSE

        est_tokens = len(prompt) / self._chars_per_token_estimate
        if est_tokens >= self.num_ctx:
            raise PromptOverflowError(
                f"Estimated prompt tokens ({est_tokens:.0f}) at or over "
                f"num_ctx ({self.num_ctx}). Transcript truncation is "
                f"UNDECIDED (DR-013b) -- failing loudly rather than "
                f"inventing a truncation policy."
            )
        return prompt
