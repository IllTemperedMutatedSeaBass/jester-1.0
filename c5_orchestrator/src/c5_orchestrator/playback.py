"""WAV playback to the headset sink via sounddevice.

Logs playout_start at first-frame-write time -- that is the T_ttfa
endpoint for Bar B (VAD end-of-speech -> first PCM frame written to the
headset sink).
"""
import io
import wave

import numpy as np
import sounddevice as sd

from .logging_util import log_event


def play_wav_bytes(wav_bytes: bytes, turn_id: str) -> None:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        n_frames = wav_file.getnframes()
        raw = wav_file.readframes(n_frames)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0

    log_event("C5", "playout_start", turn_id, sample_rate=sample_rate)
    sd.play(samples, sample_rate, blocking=True)
    log_event("C5", "playout_done", turn_id)
