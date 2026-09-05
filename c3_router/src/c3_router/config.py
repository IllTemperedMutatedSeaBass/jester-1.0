"""Env-driven config for C3."""
import os


class Config:
    HOST = os.environ.get("C3_HOST", "127.0.0.1")
    PORT = int(os.environ.get("C3_PORT", "8003"))
