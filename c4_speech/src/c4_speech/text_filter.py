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

DR-044 (thread 1.0.16): also strips BRACKETED CITATION MARKERS of the form
`[<source_path> #<chunk_index>]`, which `c2_reason.retrieval.format_evidence`
puts on every retrieved chunk. DR-038 recorded this gap as real but
unrealised on one clean run; DR-044 makes cited flags routine, so it is
closed here. The citation itself is NOT lost -- C3 renders it as prose from
structured fields (see `_CITATION_MARKER_RE`'s comment).

DR-027: also refuses to synthesize text matching C2's own system preamble.
Reproduced live (thread 1.0.11) that raw-mode generation can, particularly
after a run of short/repetitive filler turns, fall into copying the
preamble verbatim (truncated by the 40-token cap) instead of replying;
`c2_reason.main` already detects and replaces this at the source, but this
module carries its own independent copy of the detection signature as a
second, C2-independent line of defense -- components communicate over
HTTP only (project-structure discipline), so this is duplicated rather
than imported.
"""
import re

# Kept in sync by hand with c2_reason.prompt.PREAMBLE_LEAK_SIGNATURE.
_PREAMBLE_LEAK_SIGNATURE = "you are jester, a meeting assistant"

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

# DR-044 / DR-038's open gap, closed. `c2_reason.retrieval.format_evidence`
# renders every retrieved chunk as `[<source_path> #<chunk_index>]`, and a
# model that quotes its evidence can carry that marker straight into the
# reply. Kokoro would then voice "open bracket board minutes dot pptx hash
# three close bracket" aloud.
#
# DR-038 flagged this against one clean run that emitted no markers -- "one
# clean run, not a fix" -- and carried it in BACKLOG.md. DR-044 makes cited
# flags ROUTINE rather than rare, so it is fixed here rather than left.
#
# READ THIS BEFORE ASSUMING THE CITATION IS LOST. DR-044 requires Jester to
# NAME the source it conflicts with. That requirement is met on the OTHER
# side: C3's `policy.merge` composes the citation as PROSE from the
# candidate's structured `source`/`authority` fields ("per
# board-minutes.pptx, which is binding company policy"), which contains no
# brackets and is not touched by this filter. The two halves are coupled --
# stripping markers WITHOUT the prose rendering would delete the very
# citation DR-044 exists to require.
#
# Bounded to a single line and to a plausible citation shape rather than
# `\[.*?\]` across the whole string: a greedy multi-line strip could eat
# real speech between two unrelated brackets.
_CITATION_MARKER_RE = re.compile(r"\[[^\]\n]{0,200}?#\s*-?\d+\s*\]")
# A source-path-shaped bracket with no `#index` (e.g. `[minutes.pptx]`) --
# a file extension is required so ordinary bracketed prose survives.
_SOURCE_BRACKET_RE = re.compile(
    r"\[[^\]\n]{0,200}?\.[A-Za-z0-9]{1,5}(?:\s*#\s*-?\d+)?\s*\]"
)
# An evidence section header from `format_evidence` ("-- Company record --").
_EVIDENCE_HEADER_RE = re.compile(r"^\s*--\s*[^\n-][^\n]*?\s*--\s*$", re.MULTILINE)

# Complete Gemma turn-control markers, plus a token-cap-truncated prefix of
# one trailing at the very end of the string (generation can be cut off by
# num_predict before the closing '>' is emitted -- DR-020 turn 18).
_CONTROL_MARKER_RE = re.compile(r"<(?:start|end)_of_turn>")
_TRUNCATED_CONTROL_MARKER_RE = re.compile(r"<[a-z_]*$")

_WHITESPACE_RE = re.compile(r"[ \t]{2,}")


def is_preamble_leak(text: str) -> bool:
    """True if `text` is (the start of) C2's own system preamble rather
    than a reply -- a truncated leak always starts with the signature
    phrase even when cut short by the token cap, so this checks a prefix
    match, not equality."""
    normalized = " ".join(text.lower().split())
    return normalized.startswith(_PREAMBLE_LEAK_SIGNATURE)


def strip_unspeakable(text: str) -> str:
    """Remove emoji, asterisked stage directions, parenthetical narration,
    and leaked Gemma control markers before TTS. Collapses the resulting
    double-spaces but does not otherwise reflow the text. If the text IS a
    leaked system preamble (see `is_preamble_leak`), returns "" -- there is
    no speakable reply content to salvage from it."""
    if is_preamble_leak(text):
        return ""
    result = _CONTROL_MARKER_RE.sub("", text)
    result = _TRUNCATED_CONTROL_MARKER_RE.sub("", result)
    # Citation markers first: a `[source.pptx #3]` marker contains a dot
    # and digits, and running the narration/emoji passes over it first
    # would leave a mangled fragment behind rather than removing it whole.
    result = _EVIDENCE_HEADER_RE.sub("", result)
    result = _CITATION_MARKER_RE.sub("", result)
    result = _SOURCE_BRACKET_RE.sub("", result)
    result = _ASTERISK_STAGE_DIRECTION_RE.sub("", result)
    result = _PAREN_NARRATION_RE.sub("", result)
    result = _EMOJI_RE.sub("", result)
    result = _WHITESPACE_RE.sub(" ", result)
    # A stripped marker can leave " ," or " ." behind.
    result = re.sub(r"\s+([,.;:])", r"\1", result)
    return result.strip()
