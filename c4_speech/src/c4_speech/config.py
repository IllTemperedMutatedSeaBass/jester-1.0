"""Env-driven config for C4."""
import os


class Config:
    HOST = os.environ.get("C4_HOST", "127.0.0.1")
    PORT = int(os.environ.get("C4_PORT", "8004"))
    TTS_ENGINE = os.environ.get("C4_TTS_ENGINE", "kokoro")
    KOKORO_WEIGHTS_PATH = os.environ.get("KOKORO_WEIGHTS_PATH")
    KOKORO_VOICES_PATH = os.environ.get("KOKORO_VOICES_PATH")
    DEFAULT_VOICE = os.environ.get("C4_DEFAULT_VOICE", "af_sarah")
