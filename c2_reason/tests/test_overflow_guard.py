"""DR-039 OVERFLOW GUARD. Proves the guard by FORCING the condition, not
by inspection.

The defect being fixed: before this, an assembled prompt over num_ctx
raised out of `respond()` as a FastAPI 500, `c5_orchestrator`'s
`raise_for_status()` was caught by nothing, and the ENTIRE RUN
terminated. Mid-meeting that is Jester stopping dead.

The guard is NOT a truncation policy and these tests are written to keep
it from quietly becoming one: nothing here asserts that a too-long
transcript is trimmed, and `test_transcript_is_not_silently_trimmed`
asserts the opposite.
"""
import os

os.environ.setdefault("OLLAMA_MODEL", "test-model")
os.environ.setdefault("OLLAMA_MODEL_DIGEST", "sha256-test")
os.environ["C2_RETRIEVAL_ENABLED"] = "0"   # no store needed for these
os.environ["C2_NUM_CTX"] = "2048"
os.environ["C2_CONTEXT_GUARD_MARGIN_TOKENS"] = "512"

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from fastapi.testclient import TestClient

from c2_reason import main as c2_main
from c2_reason.prompt import PromptBuilder, PromptOverflowError


# ---------------------------------------------------------------- builder

def test_guard_fires_BEFORE_num_ctx_not_at_it():
    """Ollama does not error at num_ctx -- it silently truncates to about
    num_ctx/2 and returns HTTP 200 (verified live on this box). So a guard
    that fires AT num_ctx fires too late to prevent silent truncation."""
    builder = PromptBuilder(num_ctx=2048, guard_margin_tokens=512)
    # ~1700 estimated tokens: under num_ctx, but over the 1536 budget.
    builder.append_transcript_line("human", "x" * 6800)
    with pytest.raises(PromptOverflowError) as exc:
        builder.build()
    assert "guarded budget" in str(exc.value)
    assert "1536" in str(exc.value)


def test_guard_does_not_fire_below_the_budget():
    builder = PromptBuilder(num_ctx=2048, guard_margin_tokens=512)
    builder.append_transcript_line("human", "x" * 1000)
    assert builder.build()  # no raise


# ------------------------------------------------------------- HTTP shape

@pytest.fixture(autouse=True)
def _reset_state():
    c2_main._OverflowState.announced = False
    c2_main.prompt_builder._transcript_lines.clear()
    yield


def _client():
    return TestClient(c2_main.app)


def _overflowing_turn(client, turn_id):
    return client.post("/respond", json={
        "turn_id": turn_id, "speaker": "human", "text": "y" * 9000,
    })


def test_overflow_returns_200_not_500():
    """THE regression. A 500 here is what killed the whole run."""
    response = _overflowing_turn(_client(), "t1")
    assert response.status_code == 200, (
        "context overflow returned a non-200; C5's raise_for_status() "
        "would terminate the entire run, which is exactly the defect "
        "DR-039 exists to fix."
    )
    assert response.json()["status"] == "context_exhausted"


def test_first_overflow_speaks_once_then_stays_silent():
    """Argued in DR-039: repeating an apology every turn would be worse
    than silence, because once the window is exhausted the transcript only
    grows and EVERY subsequent turn overflows."""
    client = _client()
    first = _overflowing_turn(client, "t1").json()
    assert first["text"] == c2_main.CONTEXT_EXHAUSTED_NOTICE

    for i in range(5):
        later = _overflowing_turn(client, f"t{i + 2}").json()
        assert later["status"] == "context_exhausted"
        assert later["text"] == "", (
            "Jester announced context exhaustion more than once -- with a "
            "twenty-turn meeting that is twenty identical apologies."
        )


def test_transcript_is_not_silently_trimmed():
    """The guard must not become a truncation policy by the back door.
    DR-013(b) reserves that decision to the operator."""
    client = _client()
    before = len(c2_main.prompt_builder._transcript_lines)
    _overflowing_turn(client, "t1")
    after = len(c2_main.prompt_builder._transcript_lines)
    assert after == before + 1, (
        "the overflow turn's transcript line was dropped -- that is a "
        "truncation policy, which DR-013(b) does not permit inventing here."
    )
