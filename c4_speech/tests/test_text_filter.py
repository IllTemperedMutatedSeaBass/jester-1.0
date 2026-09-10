"""Unit tests for text_filter.strip_unspeakable (DR-027).

Cases are drawn from DECISIONS.md's DR-020 anomaly record: the four
emoji/stage-direction strings that measured 52-104% synthesis-time
inflation on Kokoro, and turn 9's leaked `<end_of_turn>` marker (DR-024).
A truncated-marker case is added because DR-020 also recorded a turn
hitting the 40-token generation cap mid-output.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from c4_speech.text_filter import is_preamble_leak, strip_unspeakable

# Verbatim (and truncated) preamble text observed leaking live, thread
# 1.0.11 (turns 6/9 of the operator's 20-turn run; reproduced again in a
# direct C2 investigation call).
_LEAKED_PREAMBLE_FULL = (
    "You are Jester, a meeting assistant. Respond briefly and naturally "
    "to the ongoing conversation below. Your reply is spoken aloud, not "
    "read: never include emoji, asterisked stage directions"
)
_LEAKED_PREAMBLE_TRUNCATED = (
    "You are Jester, a meeting assistant. Respond briefly and naturally "
    "to the ongoing conversation below. Your reply is spoken aloud, not "
    "read; never include emoji, asterisked stage directions, or parenth"
)


def test_plain_text_untouched():
    text = "Sure, happy to help with that today."
    assert strip_unspeakable(text) == text


def test_strips_asterisk_stage_direction():
    text = "Sure, happy to help with that today. *Giggles softly*"
    result = strip_unspeakable(text)
    assert "*" not in result
    assert "Giggles" not in result
    assert result.startswith("Sure, happy to help with that today.")


def test_strips_single_emoji():
    text = "Sure, happy to help with that today. ✨"
    result = strip_unspeakable(text)
    assert "✨" not in result
    assert result == "Sure, happy to help with that today."


def test_strips_theatrical_mask_emoji():
    text = "Sure, happy to help with that today. 🎭"
    result = strip_unspeakable(text)
    assert "🎭" not in result
    assert result == "Sure, happy to help with that today."


def test_strips_complete_end_of_turn_marker():
    text = "Here's the summary you asked for.<end_of_turn>"
    result = strip_unspeakable(text)
    assert "<end_of_turn>" not in result
    assert "end_of_turn" not in result
    assert result == "Here's the summary you asked for."


def test_strips_truncated_end_of_turn_marker():
    # Simulates a 40-token cap cutting generation off mid-marker.
    text = "Here's the summary you asked for.<end_of_tur"
    result = strip_unspeakable(text)
    assert "<" not in result
    assert result == "Here's the summary you asked for."


def test_strips_parenthetical_narration():
    text = "Sure, I can do that. (pauses thoughtfully)"
    result = strip_unspeakable(text)
    assert "(" not in result and ")" not in result
    assert result == "Sure, I can do that."


def test_strips_multiple_combined_in_one_reply():
    text = "Sure! 🎭 *laughs* (winks) Happy to help.<end_of_turn>"
    result = strip_unspeakable(text)
    assert "🎭" not in result
    assert "*" not in result
    assert "(" not in result
    assert "<" not in result
    assert result == "Sure! Happy to help."


def test_does_not_strip_normal_punctuation_or_parens_free_text():
    text = "It's 3:30 -- let's start now."
    assert strip_unspeakable(text) == text


def test_control_marker_regex_does_not_eat_stray_less_than_mid_sentence():
    # A bare '<' not part of a control marker and not at end-of-string
    # should survive -- only a truncated marker AT THE END is stripped.
    text = "x < y is true, by the way."
    assert strip_unspeakable(text) == text


def test_detects_full_leaked_preamble():
    assert is_preamble_leak(_LEAKED_PREAMBLE_FULL)


def test_detects_cap_truncated_leaked_preamble():
    assert is_preamble_leak(_LEAKED_PREAMBLE_TRUNCATED)


def test_strips_leaked_preamble_to_empty():
    assert strip_unspeakable(_LEAKED_PREAMBLE_FULL) == ""
    assert strip_unspeakable(_LEAKED_PREAMBLE_TRUNCATED) == ""


def test_does_not_flag_a_genuine_reply_as_a_leak():
    assert not is_preamble_leak("Sure, happy to help with that today.")
    assert not is_preamble_leak("I am here.")
    assert not is_preamble_leak(
        "You are right, that meeting does start at nine."
    )  # starts with "you are" but not the full signature phrase


# --------- DR-044 / DR-038: bracketed citation markers ------------------
# DR-038 recorded the gap as real but unrealised on one clean run -- "one
# clean run, not a fix". DR-044 makes cited flags routine, so it is closed
# and covered here.

def test_bracketed_citation_marker_is_stripped():
    """`retrieval.format_evidence` renders every chunk as
    `[<source_path> #<chunk_index>]`. Kokoro would voice that aloud."""
    assert strip_unspeakable("The board approved it [minutes.pptx #3] last March.") == (
        "The board approved it last March."
    )


def test_citation_marker_with_a_directory_path_is_stripped():
    text = strip_unspeakable("Per [DHI-2026/board/minutes.pptx #12] the answer is no.")
    assert "[" not in text and "]" not in text
    assert "minutes.pptx" not in text
    assert text.startswith("Per") and "the answer is no." in text


def test_source_bracket_without_an_index_is_stripped():
    assert "[" not in strip_unspeakable("See [docs/board-minutes.pptx] for detail.")


def test_evidence_section_header_is_stripped():
    """`format_evidence` emits '-- Company record --' section headers."""
    assert strip_unspeakable(
        "-- Company record --\nThe board approved phase 2."
    ) == "The board approved phase 2."


def test_the_dr044_prose_citation_survives_the_filter():
    """THE COUPLED HALF. DR-044 requires the source to be NAMED aloud, and
    C3's merge step renders it as prose from structured fields. Stripping
    brackets must not touch it -- if this test fails, the filter is
    deleting the citation DR-044 exists to require."""
    spoken = (
        "One thing before you move on: that contradicts the delegated "
        "authority matrix, per board-minutes.pptx, which is binding "
        "company policy."
    )
    assert strip_unspeakable(spoken) == spoken


def test_ordinary_bracketed_prose_is_not_stripped():
    """The strip is bounded to citation SHAPES, not to every bracket: a
    greedy `\\[.*?\\]` would eat real speech."""
    assert strip_unspeakable("He said [sic] it was fine.") == "He said [sic] it was fine."
    assert strip_unspeakable("Revenue rose [see chart].") == "Revenue rose [see chart]."


def test_a_stripped_marker_does_not_leave_a_dangling_space_before_punctuation():
    assert strip_unspeakable("That was resolved [minutes.pptx #1].") == (
        "That was resolved."
    )
