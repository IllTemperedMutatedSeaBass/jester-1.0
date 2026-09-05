"""Env-driven config for C1. No hardcoded addresses/paths (CLAUDE.md)."""
import os


class Config:
    HOST = os.environ.get("C1_HOST", "127.0.0.1")
    PORT = int(os.environ.get("C1_PORT", "8001"))
    WHISPER_MODEL = os.environ.get("C1_WHISPER_MODEL", "small")
    WHISPER_COMPUTE_TYPE = os.environ.get("C1_WHISPER_COMPUTE_TYPE", "int8")
    SAMPLE_RATE = int(os.environ.get("C1_SAMPLE_RATE", "16000"))
    # Energy-based VAD thresholds (D0 walking-skeleton scope; not tuned).
    VAD_RMS_THRESHOLD = float(os.environ.get("C1_VAD_RMS_THRESHOLD", "0.02"))
    VAD_SILENCE_MS = int(os.environ.get("C1_VAD_SILENCE_MS", "800"))
    VAD_MIN_SPEECH_MS = int(os.environ.get("C1_VAD_MIN_SPEECH_MS", "250"))
