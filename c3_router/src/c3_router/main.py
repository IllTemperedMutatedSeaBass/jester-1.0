"""C3 HTTP surface: STUB, not wired into the D0 loop.

Per the thread-1.0.6 ruling, D0's path is C1 -> C5 -> C2 -> C4 only. C3
exists as a standing service with no interjection logic yet -- it always
signals "speak now" -- so the package and its HTTP surface exist without
committing to any routing behaviour before there is retrieval or
diarisation to route on.
"""
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

from .config import Config

config = Config()
app = FastAPI()


class DecideResponse(BaseModel):
    turn_id: str
    decision: str


@app.post("/decide", response_model=DecideResponse)
def decide() -> DecideResponse:
    return DecideResponse(turn_id=str(uuid.uuid4()), decision="speak_now")


def run():
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    run()
