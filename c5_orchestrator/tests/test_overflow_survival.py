"""DR-039: proves C5's TURN LOOP SURVIVES a context-exhausted response.

This is the test that matters. A C2-only test proves C2 returns the right
shape; it does NOT prove the run stops dying, because the death happened
in C5 -- `respond_resp.raise_for_status()` on a 500, uncaught in
`run_turn` and uncaught in `main()`'s loop. These tests drive the real
`run_turn` against a stub transport.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from c5_orchestrator.config import Config
from c5_orchestrator import main as c5_main


class _Resp:
    def __init__(self, payload=None, content=b"", status=200):
        self._payload, self.content, self.status_code = payload, content, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _StubClient:
    """Records which endpoints were called so the test can assert that a
    silent overflow turn produces NO audio."""

    def __init__(self, respond_payload, respond_status=200):
        self.respond_payload, self.respond_status = respond_payload, respond_status
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(url)
        if "/transcribe" in url:
            return _Resp({"turn_id": "T1", "transcript": "hello",
                          "endpoint_monotonic_ts": 1.0})
        if "/respond" in url:
            return _Resp(self.respond_payload, status=self.respond_status)
        if "/synthesize" in url:
            return _Resp(content=b"RIFFfake")
        raise AssertionError(url)


@pytest.fixture(autouse=True)
def _no_audio(monkeypatch):
    monkeypatch.setattr(c5_main, "play_wav_bytes", lambda *a, **k: None)


def test_silent_overflow_turn_does_not_kill_the_loop_and_makes_no_audio():
    client = _StubClient({"turn_id": "T1", "text": "", "max_tokens": 40,
                          "model": "m", "model_digest": "d",
                          "status": "context_exhausted"})
    c5_main.run_turn(Config(), client)   # must not raise
    assert not any("/synthesize" in c for c in client.calls), (
        "a silent context-exhausted turn still called C4 -- it would "
        "synthesise and play empty text."
    )


def test_first_overflow_turn_still_speaks_the_notice():
    client = _StubClient({"turn_id": "T1", "text": "I've reached the limit.",
                          "max_tokens": 40, "model": "m", "model_digest": "d",
                          "status": "context_exhausted"})
    c5_main.run_turn(Config(), client)
    assert any("/synthesize" in c for c in client.calls), (
        "the one-time spoken notice was not synthesised, so the humans in "
        "the room get no signal that Jester has stopped."
    )


def test_twenty_consecutive_overflow_turns_all_survive():
    """The real shape of the failure: once the window is exhausted, EVERY
    remaining turn overflows. The loop must survive all of them."""
    client = _StubClient({"turn_id": "T1", "text": "", "max_tokens": 40,
                          "model": "m", "model_digest": "d",
                          "status": "context_exhausted"})
    for _ in range(20):
        c5_main.run_turn(Config(), client)


def test_a_genuine_500_still_propagates():
    """The guard must not become a blanket swallow of C2 errors -- a real
    fault should still surface loudly."""
    client = _StubClient({}, respond_status=500)
    with pytest.raises(RuntimeError):
        c5_main.run_turn(Config(), client)
