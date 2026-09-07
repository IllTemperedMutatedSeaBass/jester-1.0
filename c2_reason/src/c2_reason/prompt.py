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


# The single chars-per-token estimator used everywhere in this repo that
# needs a token count without calling the model. It is an ESTIMATE, named
# as one: the only exact figures come from Ollama's own
# `prompt_eval_count`, which C2 logs per turn (main.respond) precisely so
# the estimate can be checked against ground truth rather than trusted.
CHARS_PER_TOKEN_ESTIMATE = 4.0


def estimate_tokens(text: str, chars_per_token: float = CHARS_PER_TOKEN_ESTIMATE) -> int:
    return int(len(text or "") / chars_per_token)


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

    def __init__(
        self,
        num_ctx: int,
        chars_per_token_estimate: float = CHARS_PER_TOKEN_ESTIMATE,
        guard_margin_tokens: int = 512,
    ):
        self.num_ctx = num_ctx
        self._chars_per_token_estimate = chars_per_token_estimate
        # DR-039: the guard must fire BEFORE Ollama's own limit, not at it.
        # Ollama does not error when a prompt reaches num_ctx -- it
        # SILENTLY truncates to ~num_ctx/2 (keeping ~5 leading tokens plus
        # the tail) and returns HTTP 200, which would destroy the cached
        # prefix and discard transcript with nothing raised anywhere. The
        # margin covers error in the chars-per-token estimate, which is an
        # estimate and not a tokenizer.
        self.guard_margin_tokens = guard_margin_tokens
        self._transcript_lines: list[str] = []

    def append_transcript_line(self, speaker: str, text: str) -> None:
        self._transcript_lines.append(f"{speaker}: {text}")

    def stable_prefix(self) -> str:
        """The region that must remain a LITERAL PREFIX of every
        subsequent turn's prompt for G1/DR-013(a)'s KV-cache reuse to
        hold. Public because `tests/test_prompt_ordering.py` asserts that
        property directly against it -- retrieved evidence must never be
        written back into `_transcript_lines`, or this region diverges
        every turn and the cache is lost with no error raised."""
        return STABLE_PREAMBLE + "\n".join(self._transcript_lines)

    def build(self, evidence: str | None = None) -> str:
        """Stable prefix first, evidence appended AFTER it (DR-013a), the
        whole turn wrapped for raw-mode `/api/generate` (DR-024).

        Note the ordering DR-032 asked about explicitly: the current
        turn's own text is inside the transcript region (appended by
        `append_transcript_line` before this call), so the order is
        transcript-including-the-question -> evidence -> reminder ->
        turn-close markers. DR-032's "query/turn last of all" phrasing is
        an `e.g.` illustrating that the ordering be expressed
        mode-independently, not a mandate to move the question after the
        evidence; moving it would change the accumulation invariant that
        DR-027's leak mitigation and the whole existing Bar B baseline
        were measured against, for no measured benefit."""
        body = self.stable_prefix()
        if evidence:
            body = body + "\n\n[Evidence]\n" + evidence
        body = body + _REMINDER
        prompt = _TURN_OPEN + body + _TURN_CLOSE

        est_tokens = len(prompt) / self._chars_per_token_estimate
        budget = self.num_ctx - self.guard_margin_tokens
        if est_tokens >= budget:
            raise PromptOverflowError(
                f"Estimated prompt tokens ({est_tokens:.0f}) at or over the "
                f"guarded budget ({budget} = num_ctx {self.num_ctx} minus a "
                f"{self.guard_margin_tokens}-token margin); transcript region "
                f"{estimate_tokens(self.stable_prefix())} tokens, evidence "
                f"region {estimate_tokens(evidence or '')} tokens. "
                f"Transcript truncation is UNDECIDED (DR-013b) -- refusing "
                f"to call the model rather than inventing a truncation "
                f"policy, and refusing to let Ollama silently truncate."
            )
        return prompt
