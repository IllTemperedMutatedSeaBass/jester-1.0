"""Env-driven config for C3.

Every policy constant here is CONFIGURABLE and every one of them is
PROVISIONAL. DR-042(c) fixed the interjection constants so work could
proceed against a bar, explicitly expecting them to be revised once
measured, and DR-045 records why no measurement was available to derive
them from. Treat a default in this file as a starting position, not as a
finding.
"""
import os


class Config:
    HOST = os.environ.get("C3_HOST", "127.0.0.1")
    PORT = int(os.environ.get("C3_PORT", "8003"))

    # C3 is an HTTP client of C2 (project-structure discipline: HTTP
    # between components even on localhost, no in-process shortcut).
    C2_HOST = os.environ.get("C2_HOST", "127.0.0.1")
    C2_PORT = int(os.environ.get("C2_PORT", "8002"))
    CORPUS_ID = os.environ.get("C2_CORPUS_ID", "dhi")

    # --- DR-042(a): the hard ceiling ----------------------------------
    # At most MAX_INTERJECTIONS in any BUDGET_WINDOW_S. Enforced in C3 by
    # arithmetic over a rolling window, deliberately NOT by a model: a
    # backstop that can be talked out of its answer is not a backstop.
    MAX_INTERJECTIONS = int(os.environ.get("C3_MAX_INTERJECTIONS", "2"))
    BUDGET_WINDOW_S = float(os.environ.get("C3_BUDGET_WINDOW_S", "600"))

    # --- DR-006: etiquette as the latency mitigation -------------------
    # A natural gap counts as an opportunity at this many seconds of
    # silence since the last utterance ended. Configurable because nobody
    # has measured what a real boardroom gap looks like -- 1.2 s is a
    # conversational-turn-taking figure, not a measured one from this
    # project.
    VAD_GAP_S = float(os.environ.get("C3_VAD_GAP_S", "1.2"))

    # DR-006 is explicit that the hand-up is LOAD-BEARING and must not be
    # optimised away: C2's work happens during the wait, which is what
    # buys back the latency this box costs. So a candidate raised on an
    # observation is NOT spoken on that same observation -- the hand goes
    # up, and the earliest it can be lowered is the next opportunity.
    # An INVITATION still bypasses the wait, because being invited to
    # speak is itself the opportunity (DR-006: "wait for invitation or a
    # natural gap").
    # Set to 1 only to collapse the wait for testing; doing so in a run
    # disables the mitigation DR-006 relies on.
    SPEAK_ON_SAME_OBSERVATION = (
        os.environ.get("C3_SPEAK_ON_SAME_OBSERVATION", "0") == "1"
    )

    # --- DR-042(b) staleness (Task 5(f)) -------------------------------
    # A queued candidate that never gets an opportunity EXPIRES rather than
    # surfacing minutes late.
    #
    # JUSTIFICATION, in one line as required: a conflict about what the
    # room was discussing five minutes ago is no longer about what the
    # room is discussing, and raising it then is worse than silence
    # because it derails the current topic to relitigate a closed one.
    #
    # Note the interaction, which is deliberate: TTL (300 s) is half the
    # budget window (600 s), so a candidate cannot sit through a whole
    # budget window waiting for a slot. If it did, an interjection could
    # be spent on the oldest thing in the queue rather than the most
    # current.
    CANDIDATE_TTL_S = float(os.environ.get("C3_CANDIDATE_TTL_S", "300"))

    # Bound on the queue itself, so a pathological run cannot grow it
    # without limit. On overflow the OLDEST candidate is dropped and the
    # drop is logged -- never silently.
    MAX_QUEUE = int(os.environ.get("C3_MAX_QUEUE", "16"))

    # Transcript window sent to C2 for context on a conflict check.
    # Bounded rather than "the whole meeting": DR-036 measured the
    # evidence-token prefill as ~97% of retrieval's cost, and this prompt
    # is built standalone (no cached prefix), so every character is paid
    # for on every check.
    TRANSCRIPT_WINDOW_CHARS = int(
        os.environ.get("C3_TRANSCRIPT_WINDOW_CHARS", "1200")
    )

    CONFLICT_CHECK_TIMEOUT_S = float(
        os.environ.get("C3_CONFLICT_CHECK_TIMEOUT_S", "60")
    )

    # DR-006's hand-up signal. GPIO is not wired at D0; the light is a
    # STUB and says so in its own log event (`hand_up_raised` carries
    # `gpio_stub: true`). Recorded rather than silently omitted, because
    # DR-006 makes the signal load-bearing and a reader must not assume a
    # physical light exists.
    HAND_UP_GPIO_ENABLED = os.environ.get("C3_HAND_UP_GPIO_ENABLED", "0") == "1"

    @property
    def c2_base_url(self) -> str:
        return f"http://{self.C2_HOST}:{self.C2_PORT}"
