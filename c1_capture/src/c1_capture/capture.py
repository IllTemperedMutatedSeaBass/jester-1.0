"""Continuous mic capture with an energy-based VAD/endpointer.

D0 scope only: batch-per-turn (DR ruling, thread 1.0.6), not streaming ASR.
C1 holds the mic continuously; each call to wait_for_utterance() blocks
until VAD declares end-of-speech and returns the raw audio for that one
utterance, plus the monotonic endpoint timestamp.
"""
import queue
import time

import numpy as np
import sounddevice as sd

from .config import Config


class Endpointer:
    def __init__(self, config: Config):
        self.config = config
        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )

    def _callback(self, indata, frames, time_info, status):
        self._q.put(indata.copy())

    def start(self):
        self._stream.start()

    def stop(self):
        self._stream.stop()
        self._stream.close()

    def wait_for_utterance(self) -> tuple[np.ndarray, float]:
        """Block until VAD declares end-of-speech.

        Returns (audio_samples, endpoint_monotonic_ts).
        """
        cfg = self.config
        block_ms = 20
        block_samples = int(cfg.SAMPLE_RATE * block_ms / 1000)
        silence_blocks_needed = max(1, cfg.VAD_SILENCE_MS // block_ms)
        min_speech_blocks = max(1, cfg.VAD_MIN_SPEECH_MS // block_ms)

        speech_started = False
        speech_blocks = 0
        silence_run = 0
        buffered: list[np.ndarray] = []
        leftover = np.empty((0,), dtype="float32")

        while True:
            chunk = self._q.get()
            chunk = np.concatenate([leftover, chunk.reshape(-1)])
            while len(chunk) >= block_samples:
                block, chunk = chunk[:block_samples], chunk[block_samples:]
                rms = float(np.sqrt(np.mean(block.astype("float64") ** 2)))
                is_speech = rms >= cfg.VAD_RMS_THRESHOLD

                if is_speech:
                    speech_started = True
                    speech_blocks += 1
                    silence_run = 0
                    buffered.append(block)
                elif speech_started:
                    silence_run += 1
                    buffered.append(block)
                    if (
                        silence_run >= silence_blocks_needed
                        and speech_blocks >= min_speech_blocks
                    ):
                        endpoint_ts = time.monotonic()
                        audio = np.concatenate(buffered)
                        return audio, endpoint_ts
            leftover = chunk
