"""Engine-agnostic TTS interface (DR-018, binding on the build).

Nothing upstream of C4 may know which engine is behind this interface.
Swapping engines is a config change (C4_TTS_ENGINE), never a code change.
The interface carries sample_rate explicitly rather than assuming it,
because Glow-TTS (22050 Hz) and Kokoro (24000 Hz) disagree -- DR-018 item 2.
"""
from abc import ABC, abstractmethod

import numpy as np


class TTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice: str) -> tuple[np.ndarray, int]:
        """Return (pcm_samples, sample_rate). Whole-utterance, no assumption
        of incremental output (DR-013 G2 finding)."""
        raise NotImplementedError
