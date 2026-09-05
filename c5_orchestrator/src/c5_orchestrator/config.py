"""Env-driven config for C5. Pure client/driver -- no HOST/PORT of its own
(thread-1.0.6 ruling: C5 is a driver, not an HTTP listener)."""
import os


class Config:
    C1_HOST = os.environ.get("C1_HOST", "127.0.0.1")
    C1_PORT = int(os.environ.get("C1_PORT", "8001"))
    C2_HOST = os.environ.get("C2_HOST", "127.0.0.1")
    C2_PORT = int(os.environ.get("C2_PORT", "8002"))
    C4_HOST = os.environ.get("C4_HOST", "127.0.0.1")
    C4_PORT = int(os.environ.get("C4_PORT", "8004"))
    TURN_COUNT = int(os.environ.get("C5_TURN_COUNT", "10"))

    @property
    def c1_base_url(self) -> str:
        return f"http://{self.C1_HOST}:{self.C1_PORT}"

    @property
    def c2_base_url(self) -> str:
        return f"http://{self.C2_HOST}:{self.C2_PORT}"

    @property
    def c4_base_url(self) -> str:
        return f"http://{self.C4_HOST}:{self.C4_PORT}"
