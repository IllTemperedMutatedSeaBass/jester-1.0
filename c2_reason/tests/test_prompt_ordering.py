"""DR-013(a) ORDERING PROOF. This is the single most important test in
this repo and it guards a constraint that FAILS SILENTLY: if retrieved
evidence is ever placed before the rolling transcript, the KV-cache prefix
invalidates and first-audio latency returns to the 5-11 s regime. Nothing
raises. The Bar B figure simply gets worse and the cause is invisible.

WHAT IS ASSERTED, AND WHY IT IS NOT A STRING-ORDER CHECK. Asserting
`prompt.index(transcript) < prompt.index("[Evidence]")` is barely better
than reading the code -- it passes any change that keeps the labels in
order while breaking the property that actually makes the cache hit. The
property that makes the cache hit is:

    turn N+1's prompt has turn N's preamble-plus-transcript region as a
    LITERAL PREFIX (byte-for-byte, from position 0).

So these tests compute the longest common prefix of consecutive turns'
prompts and assert it covers the whole preamble-plus-transcript region.
That catches prepending, and it also catches any future change that
mutates the preamble or the transcript region per turn -- including the
specific accumulation bug that would happen if retrieved evidence were
ever written back into the transcript lines, which would diverge the
shared region every turn with nothing raised.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from c2_reason.prompt import (
    STABLE_PREAMBLE,
    PromptBuilder,
    PromptOverflowError,
)


def _longest_common_prefix(a: str, b: str) -> str:
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[i] == b[i]:
        i += 1
    return a[:i]


def _expected_stable_region(lines: list[tuple[str, str]]) -> str:
    """Built here from the test's OWN knowledge of what it fed in, not by
    calling the builder's internals -- otherwise the test would only be
    checking the implementation against itself."""
    return STABLE_PREAMBLE + "\n".join(f"{s}: {t}" for s, t in lines)


TURNS = [
    ("human", "What did the board resolve about the ERP programme?"),
    ("human", "And who was the delegated authority for that spend?"),
    ("human", "Does the risk register still carry it as open?"),
    ("human", "When is the next management review scheduled?"),
]

# Deliberately DIFFERENT evidence every turn, and of different lengths --
# identical evidence turn over turn could mask a prepending bug by
# accident, because the prepended region would itself be stable.
EVIDENCE = [
    "-- Company record --\n[minutes_2026Q1.pptx #3] The board approved phase 2.",
    "-- Company record --\n[doa_matrix.pptx #1] Spend above 250k needs board sign-off.\n"
    "[minutes_2026Q1.pptx #7] Delegated to the CFO within that limit.",
    "-- Company record --\n[risk_register.pptx #12] ERP delivery risk: OPEN, amber.",
    "",
]


def _prompts_across_turns(evidence_per_turn):
    builder = PromptBuilder(num_ctx=8192)
    prompts = []
    for (speaker, text), evidence in zip(TURNS, evidence_per_turn):
        builder.append_transcript_line(speaker, text)
        prompts.append(builder.build(evidence=evidence or None))
    return prompts


@pytest.mark.parametrize(
    "evidence_per_turn, label",
    [
        (["", "", "", ""], "no evidence"),
        (EVIDENCE, "evidence differing every turn"),
    ],
)
def test_shared_literal_prefix_survives_every_turn(evidence_per_turn, label):
    """THE constraint. Turn N's preamble+transcript region must still be a
    literal prefix of turn N+1's prompt, with and without evidence."""
    prompts = _prompts_across_turns(evidence_per_turn)

    for n in range(len(prompts) - 1):
        # The region that must be shared after turn N is the preamble plus
        # transcript lines 1..N+1 (turn N has already appended its own).
        expected_shared = _expected_stable_region(TURNS[: n + 1])
        common = _longest_common_prefix(prompts[n], prompts[n + 1])

        assert prompts[n].startswith("<start_of_turn>user\n" + STABLE_PREAMBLE), (
            f"[{label}] turn {n}: preamble is no longer at the very start "
            f"of the prompt -- the cached prefix cannot hold."
        )
        assert expected_shared in common, (
            f"[{label}] turn {n} -> {n + 1}: the preamble-plus-transcript "
            f"region is NOT a literal shared prefix of the next turn's "
            f"prompt. Shared prefix was {len(common)} chars; the region "
            f"that must be shared is {len(expected_shared)} chars. "
            f"Something was inserted BEFORE the transcript -- DR-013(a) "
            f"violated, first-audio latency returns to the 5-11 s regime."
        )


def test_evidence_lands_after_the_entire_transcript():
    """Complementary to the prefix test: evidence must sit after the LAST
    transcript line, not merely after the first."""
    prompts = _prompts_across_turns(EVIDENCE)
    prompt = prompts[1]
    evidence_at = prompt.index("[Evidence]")
    for speaker, text in TURNS[:2]:
        line_at = prompt.index(f"{speaker}: {text}")
        assert line_at < evidence_at, (
            f"transcript line {text!r} appears AFTER the evidence block -- "
            f"DR-013(a) requires evidence strictly after the transcript."
        )


def test_evidence_is_never_accumulated_into_the_transcript():
    """The silent-divergence bug: if retrieved evidence were written back
    into the transcript, the shared region would grow with evidence text
    and no longer match turn over turn. Asserted by checking that turn 2's
    stable region contains none of turn 1's evidence text."""
    builder = PromptBuilder(num_ctx=8192)
    builder.append_transcript_line(*TURNS[0])
    builder.build(evidence=EVIDENCE[0])
    builder.append_transcript_line(*TURNS[1])

    stable = builder.stable_prefix()
    assert "minutes_2026Q1.pptx" not in stable, (
        "turn 1's evidence has leaked into the stable transcript region. "
        "Every subsequent turn's cached prefix now diverges, with no error "
        "raised anywhere."
    )
    assert stable == _expected_stable_region(TURNS[:2])


def test_overflow_raises_rather_than_truncating_silently():
    """DR-013(b): truncation policy is UNDECIDED. The builder must refuse,
    not invent one. Also confirms the error names both regions, which is
    what makes the Task 3 arithmetic readable from a live failure."""
    builder = PromptBuilder(num_ctx=256)
    builder.append_transcript_line("human", "x" * 4000)
    with pytest.raises(PromptOverflowError) as exc:
        builder.build(evidence="y" * 4000)
    message = str(exc.value)
    assert "transcript region" in message and "evidence region" in message
