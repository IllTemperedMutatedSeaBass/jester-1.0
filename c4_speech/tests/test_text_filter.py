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

from c4_speech.text_filter import strip_unspeakable


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
