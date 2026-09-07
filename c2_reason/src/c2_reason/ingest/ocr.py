"""OCR module. COPY-THEN-DIVERGE from jester-2.1/ingest/ocr.py per DR-033(c)
(fork point: jester-2.1 commit history as of 2026-09-07, thread D1 ingest) --
not a shared import, not an extracted package. pytesseract (Apache-2.0)
wrapping the tesseract system binary, unchanged rationale: CPU, deterministic,
zero VRAM contention.

Divergence from 2.x: no `config.OCR_LANG` dependency (1.x's config module
carries no OCR settings); language is hardcoded to "eng" here since the DHI
corpus surveyed at ingest is English-only -- revisit if a non-English corpus
is ever supplied.
"""
from __future__ import annotations

import io
import shutil

import pytesseract
from PIL import Image

OCR_LANG = "eng"


def tesseract_missing() -> bool:
    return shutil.which("tesseract") is None


def run_ocr(image: "Image.Image | bytes") -> tuple[str, float | None]:
    """OCR one image. Returns (text, mean_word_confidence in [0,1] or None).
    Never raises: a missing binary or a tesseract failure both degrade to
    ("", None) rather than propagating."""
    if tesseract_missing():
        return "", None
    if isinstance(image, (bytes, bytearray)):
        image = Image.open(io.BytesIO(image))
    try:
        data = pytesseract.image_to_data(
            image, lang=OCR_LANG, output_type=pytesseract.Output.DICT,
        )
    except Exception:
        return "", None

    words: list[str] = []
    confidences: list[float] = []
    for text, conf in zip(data.get("text", []), data.get("conf", [])):
        text = (text or "").strip()
        if not text:
            continue
        words.append(text)
        try:
            c = float(conf)
        except (TypeError, ValueError):
            continue
        if c >= 0:
            confidences.append(c)

    ocr_text = " ".join(words)
    mean_confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else None
    return ocr_text, mean_confidence
