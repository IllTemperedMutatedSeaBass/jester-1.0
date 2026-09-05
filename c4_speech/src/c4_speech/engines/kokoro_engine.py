"""Kokoro implementation of the engine-agnostic TTS interface (D0, DR-018).

Called whole-utterance: kokoro-onnx 0.4.7's create_stream yields exactly
one chunk on this box (G2, DR-013), so there is no incremental-output
behaviour to preserve here -- .create() is used directly.
"""
import numpy as np
from kokoro_onnx import Kokoro

from .base import TTSEngine

KOKORO_SAMPLE_RATE = 24000


class KokoroEngine(TTSEngine):
    def __init__(self, weights_path: str, voices_path: str):
        self._kokoro = Kokoro(weights_path, voices_path)

    def synthesize(self, text: str, voice: str) -> tuple[np.ndarray, int]:
        samples, sample_rate = self._kokoro.create(text, voice=voice)
        return samples, sample_rate
