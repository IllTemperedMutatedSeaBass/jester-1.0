"""Env-driven config for C5. Pure client/driver -- no HOST/PORT of its own
(thread-1.0.6 ruling: C5 is a driver, not an HTTP listener)."""
import os


class Config:
    C1_HOST = os.environ.get("C1_HOST", "127.0.0.1")
    C1_PORT = int(os.environ.get("C1_PORT", "8001"))
    C2_HOST = os.environ.get("C2_HOST", "127.0.0.1")
    C2_PORT = int(os.environ.get("C2_PORT", "8002"))
    C3_HOST = os.environ.get("C3_HOST", "127.0.0.1")
    C3_PORT = int(os.environ.get("C3_PORT", "8003"))
    C4_HOST = os.environ.get("C4_HOST", "127.0.0.1")
    C4_PORT = int(os.environ.get("C4_PORT", "8004"))
    # C3 is in the D0 path from thread 1.0.16. Set to 0 to reproduce the
    # pre-C3 baseline on this same build -- the same reversibility posture
    # C2_RETRIEVAL_ENABLED takes, and for the same reason: "before C3" and
    # "after C3" must not be two different commits, or the Bar B
    # comparison is not like-for-like.
    C3_ENABLED = os.environ.get("C5_C3_ENABLED", "1") == "1"
    # Silence observed since the utterance ended, handed to C3 as its
    # opportunity signal. At D0 the loop is sequential and prompt-driven,
    # so there is no real inter-utterance silence to measure: this is the
    # value C5 reports, and it is a CONFIGURED STAND-IN, not a
    # measurement. Wiring C1's endpointer to report the true gap is
    # carried in BACKLOG.md.
    C3_ASSUMED_GAP_S = float(os.environ.get("C5_C3_ASSUMED_GAP_S", "2.0"))
    # Generous: C3's own call to C2 is an Ollama generate, and C3's
    # default conflict-check timeout is 60 s.
    C3_OBSERVE_TIMEOUT_S = float(os.environ.get("C5_C3_OBSERVE_TIMEOUT_S", "90"))
    TURN_COUNT = int(os.environ.get("C5_TURN_COUNT", "10"))
    # DR-032: the caller declares the corpus it is asking about. Same env
    # var C2 reads, so a divergence is a misconfiguration of one variable
    # rather than two independently-wrong values.
    CORPUS_ID = os.environ.get("C2_CORPUS_ID", "dhi")
    # Per-turn wait for C1's /transcribe to return, i.e. how long a human
    # has to notice the "SPEAK NOW" prompt and speak before C5 gives up on
    # the turn. C1's own VAD wait is unbounded (capture.py: wait_for_utterance
    # blocks until speech starts), so this is the only real ceiling on a
    # spoken turn. Raised from a 120s default (thread 1.0.10: the previous
    # attempt's stall was a buffering bug, not this value, but 120s leaves
    # little margin for a human reading a freshly-visible prompt over SSH).
    TRANSCRIBE_TIMEOUT_S = float(os.environ.get("C5_TRANSCRIBE_TIMEOUT_S", "300"))

    @property
    def c1_base_url(self) -> str:
        return f"http://{self.C1_HOST}:{self.C1_PORT}"

    @property
    def c2_base_url(self) -> str:
        return f"http://{self.C2_HOST}:{self.C2_PORT}"

    @property
    def c3_base_url(self) -> str:
        return f"http://{self.C3_HOST}:{self.C3_PORT}"

    @property
    def c4_base_url(self) -> str:
        return f"http://{self.C4_HOST}:{self.C4_PORT}"
