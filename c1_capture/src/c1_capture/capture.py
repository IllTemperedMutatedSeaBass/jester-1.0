"""Continuous mic capture with an energy-based VAD/endpointer.

D0 scope only: batch-per-turn (DR ruling, thread 1.0.6), not streaming ASR.
C1 holds the mic continuously; each call to wait_for_utterance() blocks
until VAD declares end-of-speech and returns the raw audio for that one
utterance, plus the monotonic endpoint timestamp.
"""
import queue
import threading
import time
import wave

import numpy as np
import sounddevice as sd

from .config import Config


class Endpointer:
    def __init__(self, config: Config):
        self.config = config
        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._file_thread: threading.Thread | None = None
        self._file_stop = threading.Event()
        if config.CAPTURE_WAV:
            self._stream = None
        else:
            self._stream = sd.InputStream(
                samplerate=config.SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self._callback,
            )

    def _callback(self, indata, frames, time_info, status):
        self._q.put(indata.copy())

    def _file_feed_loop(self):
        block_ms = 20
        block_samples = int(self.config.SAMPLE_RATE * block_ms / 1000)
        with wave.open(self.config.CAPTURE_WAV, "rb") as w:
            assert w.getframerate() == self.config.SAMPLE_RATE
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2
            while not self._file_stop.is_set():
                raw = w.readframes(block_samples)
                if len(raw) == 0:
                    w.rewind()
                    continue
                pcm16 = np.frombuffer(raw, dtype="<i2")
                block = (pcm16.astype("float32") / 32768.0).reshape(-1, 1)
                self._q.put(block)
                time.sleep(block_ms / 1000)

    def start(self):
        if self.config.CAPTURE_WAV:
            self._file_thread = threading.Thread(
                target=self._file_feed_loop, daemon=True
            )
            self._file_thread.start()
        else:
            self._stream.start()

    def stop(self):
        if self._file_thread is not None:
            self._file_stop.set()
            self._file_thread.join(timeout=2.0)
        else:
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
