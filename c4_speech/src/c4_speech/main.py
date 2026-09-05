"""C4 HTTP surface: whole-utterance TTS behind the engine-agnostic interface.

POST /synthesize returns a WAV byte stream (PCM + sample rate folded into
one container) so C5 does not need to know the engine's native sample
rate out of band -- DR-018 item 2 (Glow-TTS 22050 Hz vs Kokoro 24000 Hz).
"""
import io
import uuid
import wave

import numpy as np
from fastapi import FastAPI, HTTPException, Response

from .config import Config
from .engines.base import TTSEngine
from .logging_util import log_event

config = Config()
app = FastAPI()
engine: TTSEngine | None = None


def _pcm_to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    int16 = np.clip(samples, -1.0, 1.0)
    int16 = (int16 * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(int16.tobytes())
    return buf.getvalue()


@app.on_event("startup")
def _startup():
    global engine
    if config.TTS_ENGINE == "kokoro":
        from .engines.kokoro_engine import KokoroEngine

        if not config.KOKORO_WEIGHTS_PATH or not config.KOKORO_VOICES_PATH:
            raise RuntimeError(
                "KOKORO_WEIGHTS_PATH / KOKORO_VOICES_PATH must be set when "
                "C4_TTS_ENGINE=kokoro."
            )
        engine = KokoroEngine(config.KOKORO_WEIGHTS_PATH, config.KOKORO_VOICES_PATH)
    else:
        raise RuntimeError(
            f"Unknown C4_TTS_ENGINE={config.TTS_ENGINE!r}. Only 'kokoro' is "
            f"wired for D0 (DR-018) -- HeathenS_Talkings is deferred to its "
            f"own gate."
        )


@app.post("/synthesize")
def synthesize(text: str, voice: str | None = None, turn_id: str | None = None):
    if engine is None:
        raise HTTPException(status_code=503, detail="TTS engine not initialised")

    turn_id = turn_id or str(uuid.uuid4())
    log_event("C4", "synthesize_start", turn_id, engine=config.TTS_ENGINE)

    samples, sample_rate = engine.synthesize(text, voice or config.DEFAULT_VOICE)

    log_event(
        "C4",
        "synthesize_done",
        turn_id,
        engine=config.TTS_ENGINE,
        sample_rate=sample_rate,
        num_samples=int(len(samples)),
    )

    wav_bytes = _pcm_to_wav_bytes(samples, sample_rate)
    return Response(content=wav_bytes, media_type="audio/wav")


def run():
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    run()
