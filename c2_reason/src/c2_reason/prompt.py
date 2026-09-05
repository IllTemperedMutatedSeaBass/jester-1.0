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
"""


class PromptOverflowError(RuntimeError):
    pass


STABLE_PREAMBLE = (
    "You are Jester, a meeting assistant. Respond briefly and naturally "
    "to the ongoing conversation below.\n\n"
)


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
        """Stable prefix first, evidence appended AFTER it (DR-013a)."""
        prompt = self._stable_prefix()
        if evidence:
            prompt = prompt + "\n\n[Evidence]\n" + evidence

        est_tokens = len(prompt) / self._chars_per_token_estimate
        if est_tokens >= self.num_ctx:
            raise PromptOverflowError(
                f"Estimated prompt tokens ({est_tokens:.0f}) at or over "
                f"num_ctx ({self.num_ctx}). Transcript truncation is "
                f"UNDECIDED (DR-013b) -- failing loudly rather than "
                f"inventing a truncation policy."
            )
        return prompt
