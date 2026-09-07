"""Chunking strategy for D1 ingest. RULING (recorded in DECISIONS.md): chunk
on the converters' own natural section boundary ("## Slide N: ...", produced
by converters.convert_pptx) when present, falling back to a fixed-size
word-window with overlap for text with no natural boundary (OCR output,
which has none). This is a deliberate, small choice, not a generic chunking
framework: the corpus is slide decks and OCR'd photos, both short per-unit,
so "one slide/one OCR block = one chunk, unless it's oversized" is enough --
a chunk this small never needs sub-splitting except as a safety cap.
"""
from __future__ import annotations

import re

_SLIDE_HEADING = re.compile(r"^## Slide \d+", re.MULTILINE)
_MAX_WORDS = 220
_OVERLAP_WORDS = 40


def _window(words: list[str], size: int, overlap: int) -> list[str]:
    if len(words) <= size:
        return [" ".join(words)] if words else []
    chunks = []
    step = size - overlap
    for start in range(0, len(words), step):
        window = words[start:start + size]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks


def chunk_text(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    if _SLIDE_HEADING.search(text):
        raw_sections = _SLIDE_HEADING.split(text)
        headings = _SLIDE_HEADING.findall(text)
        sections = []
        for heading, body in zip(headings, raw_sections[1:]):
            section = (heading + body).strip()
            if not section:
                continue
            words = section.split()
            if len(words) <= _MAX_WORDS:
                sections.append(section)
            else:
                sections.extend(_window(words, _MAX_WORDS, _OVERLAP_WORDS))
        return sections

    return _window(text.split(), _MAX_WORDS, _OVERLAP_WORDS)
