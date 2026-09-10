"""C3's interjection policy: budget, pending queue, staleness, merge.

CHEAP AND DETERMINISTIC BY DESIGN. NO MODEL RUNS IN C3. Every decision in
this module is arithmetic over timestamps and a list. The judgement -- "is
this actually a contradiction worth raising?" -- runs at C2 under the
DR-043 `conflict_check` intent, and `conflict.py` there records why.

That split is the point. DR-043(e) relocates the project's noise control
onto a reasoning gate plus DR-042's rate ceiling, and the ceiling is only
worth anything as a BACKSTOP if it cannot itself be reasoned with. A model
asked "may I speak?" can be persuaded; a rolling-window counter cannot.

WHAT LIVES HERE, AND WHICH RULING PUTS IT HERE:
  - `Budget`      -- DR-042(a): at most N interjections per rolling window.
  - `PendingQueue`-- DR-042(b): candidates are QUEUED, never spoken on
                     arrival, so that everything outstanding can be
                     delivered together.
  - `merge`       -- DR-042(b) + DR-044: N candidates become ONE utterance
                     that states each conflict and stops.
  - staleness     -- Task 5(f): a candidate that never gets an opportunity
                     expires rather than surfacing minutes late.

TIME IS INJECTED, NEVER READ FROM THE CLOCK INSIDE THE POLICY. Every method
takes `now`. A rolling-window rule tested against the real clock is either
a slow test or a flaky one, and DR-042's ceiling is exactly the kind of
rule that must be tested at the boundary (the 601st second) rather than
approximately.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Candidate:
    """One conflict C2 found. Structured, never prose (DR-044).

    `authority_phrase` is the spoken rendering of the authority weight,
    supplied by C2 from the retrieved chunk's tier metadata. C3 does not
    derive it and must not invent it: DR-043(d) makes authority a property
    Jester STATES, and DR-044 makes the citation the thing that makes an
    interjection checkable.
    """

    utterance: str
    conflicts_with: str
    source: str
    authority: str
    authority_phrase: str
    turn_id: str
    raised_at: float
    candidate_id: str = ""

    def as_dict(self) -> dict:
        """Complete record, including `turn_id`. Used where the candidate
        is nested inside another event (e.g. `interjection_spoken`)."""
        return {
            "candidate_id": self.candidate_id,
            "turn_id": self.turn_id,
            "utterance": self.utterance,
            "conflicts_with": self.conflicts_with,
            "source": self.source,
            "authority": self.authority,
            "raised_at": self.raised_at,
        }

    def log_fields(self) -> dict:
        """`as_dict()` WITHOUT `turn_id`, for splatting into `log_event`,
        whose third positional parameter is `turn_id` -- splatting the
        full dict there is a TypeError, and the candidate's own turn_id is
        already passed positionally at every such call site."""
        fields = self.as_dict()
        fields.pop("turn_id")
        return fields


class Budget:
    """DR-042(a). At most `max_interjections` per rolling `window_s`.

    A HARD CEILING: `allows()` is the only authority on whether an
    interjection may happen, and nothing in this codebase may bypass it.
    """

    def __init__(self, max_interjections: int, window_s: float):
        self.max_interjections = max_interjections
        self.window_s = window_s
        self._spoken_at: list[float] = []

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_s
        # Strictly greater-than: an interjection exactly `window_s` ago has
        # left the window. Chosen so the boundary is testable as an
        # equality rather than an approximation.
        self._spoken_at = [t for t in self._spoken_at if t > cutoff]

    def used(self, now: float) -> int:
        self._prune(now)
        return len(self._spoken_at)

    def remaining(self, now: float) -> int:
        return max(0, self.max_interjections - self.used(now))

    def allows(self, now: float) -> bool:
        return self.used(now) < self.max_interjections

    def record(self, now: float) -> None:
        """Records ONE interjection, however many candidates it carried.

        This is where DR-042(b)'s batching rule earns its keep: a merged
        utterance covering three conflicts costs ONE budget slot, because
        it is one interjection. Charging per candidate would make batching
        pointless and would reintroduce exactly the behaviour the rule
        forbids -- spending two slots on points that could be combined.
        """
        self._prune(now)
        self._spoken_at.append(now)

    def next_free_at(self, now: float) -> float | None:
        """When the ceiling next lifts, or None if it is not binding."""
        self._prune(now)
        if len(self._spoken_at) < self.max_interjections:
            return None
        return min(self._spoken_at) + self.window_s


@dataclass
class PendingQueue:
    """DR-042(b)'s pending candidate queue.

    Candidates are NOT spoken on arrival. This is the structural half of
    the batching rule: a decide-and-fire-per-utterance component cannot be
    made to batch later, because batching is a property of the data flow
    and not a filter on its output.
    """

    ttl_s: float
    max_queue: int
    items: list[Candidate] = field(default_factory=list)

    def add(self, candidate: Candidate) -> Candidate | None:
        """Queue a candidate. Returns an evicted candidate, if any."""
        self.items.append(candidate)
        if len(self.items) > self.max_queue:
            return self.items.pop(0)
        return None

    def expire(self, now: float) -> list[Candidate]:
        """Task 5(f). Drop candidates past their TTL and RETURN them, so
        the caller can log each expiry as its own event -- DR-045's scored
        run needs `expired` to be distinguishable from `suppressed by
        budget`, since they mean different things about the gate."""
        alive, expired = [], []
        for item in self.items:
            (expired if now - item.raised_at > self.ttl_s else alive).append(item)
        self.items = alive
        return expired

    def drain(self) -> list[Candidate]:
        """Take everything outstanding. DR-042(b): ALL outstanding points
        are delivered in one interjection, so this is all-or-nothing --
        there is deliberately no `take(n)`."""
        items, self.items = self.items, []
        return items

    def __len__(self) -> int:
        return len(self.items)


def merge(candidates: list[Candidate]) -> str:
    """DR-042(b) + DR-044: N candidates -> ONE utterance.

    FORM, per DR-044: state what was said, what it conflicts with, and the
    authority of that source -- then STOP. No resolution is proposed. A
    resolution may be given only if a human asks, which is the existing
    question-answering path and needs no mechanism here.

    The citation is rendered as PROSE ("... in board-minutes.pptx, which is
    binding company policy"), never as a `[source #N]` bracket marker.
    C4's text filter strips bracket markers before synthesis, so a
    bracketed citation here would be silently deleted on its way to the
    speaker -- removing the very citation DR-044 exists to require. The two
    halves are coupled and must stay that way.
    """
    if not candidates:
        return ""

    parts: list[str] = []
    for candidate in candidates:
        source = candidate.source.rsplit("/", 1)[-1] or candidate.source
        statement = candidate.conflicts_with.strip().rstrip(".")
        parts.append(f"{statement}, per {source}, which is {candidate.authority_phrase}.")

    if len(parts) == 1:
        return f"One thing before you move on: {parts[0]}"

    # A person with three things to say says them once, and says how many
    # are coming -- otherwise the room does not know when to stop waiting.
    numbered = " ".join(f"{i}. {part}" for i, part in enumerate(parts, 1))
    return f"{len(parts)} things before you move on: {numbered}"
