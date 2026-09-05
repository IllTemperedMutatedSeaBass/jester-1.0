"""C1 HTTP surface: batch-per-turn capture + transcription.

POST /transcribe blocks on the mic until VAD declares end-of-speech, then
runs faster-whisper on that utterance and returns the transcript, turn id,
and the monotonic endpoint timestamp Bar B's T_ttfa clock starts from.
"""
import uuid

from fastapi import FastAPI
from faster_whisper import WhisperModel
from pydantic import BaseModel

from .capture import Endpointer
from .config import Config
from .logging_util import log_event

config = Config()
app = FastAPI()
endpointer = Endpointer(config)
whisper_model: WhisperModel | None = None


class TranscribeResponse(BaseModel):
    turn_id: str
    transcript: str
    endpoint_monotonic_ts: float


@app.on_event("startup")
def _startup():
    global whisper_model
    whisper_model = WhisperModel(
        config.WHISPER_MODEL, compute_type=config.WHISPER_COMPUTE_TYPE
    )
    endpointer.start()


@app.on_event("shutdown")
def _shutdown():
    endpointer.stop()


@app.post("/transcribe", response_model=TranscribeResponse)
def transcribe() -> TranscribeResponse:
    turn_id = str(uuid.uuid4())
    log_event("C1", "capture_wait_start", turn_id)

    audio, endpoint_ts = endpointer.wait_for_utterance()
    log_event("C1", "endpoint_declared", turn_id, endpoint_monotonic_ts=endpoint_ts)

    segments, _info = whisper_model.transcribe(audio, language="en")
    transcript = " ".join(seg.text.strip() for seg in segments)
    log_event("C1", "asr_done", turn_id, transcript_chars=len(transcript))

    return TranscribeResponse(
        turn_id=turn_id,
        transcript=transcript,
        endpoint_monotonic_ts=endpoint_ts,
    )


def run():
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    run()
