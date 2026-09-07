"""Defensive pre-synthesis text filter (DR-027).

Independent of whatever C2's system prompt asks the model to avoid
(prompt.py's STABLE_PREAMBLE): Kokoro voices emoji and asterisk/parenthetical
stage directions aloud rather than dropping them silently (DR-020's
Anomaly 2 measured 52-104% synthesis-time inflation from a single emoji or
stage direction). This filter strips that class of text before it reaches
`engine.synthesize()`, as a second line of defense that holds even if a
future prompt change or a different model regresses C2's own output.

Also strips literal Gemma control-marker text that can leak into C2's
response when generation is cut short before a stop sequence is reached
(DR-024's turn-9 anomaly, `<end_of_turn>`) -- both the complete marker and a
token-cap-truncated prefix of it (e.g. `<end_of_tur`), since DR-020 recorded
one turn hitting the 40-token cap mid-generation.
"""
import re

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "]+"
)

_ASTERISK_STAGE_DIRECTION_RE = re.compile(r"\*[^*\n]+\*")
_PAREN_NARRATION_RE = re.compile(r"\([^)\n]*\)")

# Complete Gemma turn-control markers, plus a token-cap-truncated prefix of
# one trailing at the very end of the string (generation can be cut off by
# num_predict before the closing '>' is emitted -- DR-020 turn 18).
_CONTROL_MARKER_RE = re.compile(r"<(?:start|end)_of_turn>")
_TRUNCATED_CONTROL_MARKER_RE = re.compile(r"<[a-z_]*$")

_WHITESPACE_RE = re.compile(r"[ \t]{2,}")


def strip_unspeakable(text: str) -> str:
    """Remove emoji, asterisked stage directions, parenthetical narration,
    and leaked Gemma control markers before TTS. Collapses the resulting
    double-spaces but does not otherwise reflow the text."""
    result = _CONTROL_MARKER_RE.sub("", text)
    result = _TRUNCATED_CONTROL_MARKER_RE.sub("", result)
    result = _ASTERISK_STAGE_DIRECTION_RE.sub("", result)
    result = _PAREN_NARRATION_RE.sub("", result)
    result = _EMOJI_RE.sub("", result)
    result = _WHITESPACE_RE.sub(" ", result)
    return result.strip()
