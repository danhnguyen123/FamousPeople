"""Stage 1: split the script into scenes (one visual per scene)."""

from __future__ import annotations

import re

import pysbd

from .models import Scene

# Lines like [SHOW BANK] or (CUT TO ...) are stage directions: the footage agent
# works from what is spoken, so they are removed from the narration.
_DIRECTION = re.compile(r"^\s*[\[(][^\])]*[\])]\s*$")
_INLINE_DIRECTION = re.compile(r"\[[^\]]*\]")


def normalize_script(raw: str) -> str:
    lines = [ln for ln in raw.splitlines() if not _DIRECTION.match(ln)]
    text = "\n".join(lines)
    text = _INLINE_DIRECTION.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str, language: str) -> list[str]:
    segmenter = pysbd.Segmenter(language=language, clean=False)
    sentences: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = " ".join(paragraph.split())
        if paragraph:
            sentences.extend(s.strip() for s in segmenter.segment(paragraph) if s.strip())
    return sentences


def segment_script(raw: str, language: str, min_chars: int = 60) -> list[Scene]:
    """Group sentences into scenes.

    Short sentences are merged with the next one so a keyframe is not on screen
    for one second only; long sentences stay alone (the timeline later splits
    long scenes into several shots).
    """
    sentences = split_sentences(normalize_script(raw), language)

    scenes: list[Scene] = []
    buffer: list[str] = []
    cursor = 0  # offset in narration_text(scenes)

    def flush() -> None:
        nonlocal cursor
        scene_text = " ".join(buffer)
        scenes.append(
            Scene(index=len(scenes), text=scene_text, sentences=list(buffer), char_start=cursor)
        )
        cursor += len(scene_text) + 1
        buffer.clear()

    for sentence in sentences:
        buffer.append(sentence)
        if len(" ".join(buffer)) >= min_chars:
            flush()
    if buffer:
        flush()
    return scenes


def narration_text(scenes: list[Scene]) -> str:
    """The exact text sent to TTS; Scene.char_start indexes into it."""
    return " ".join(s.text for s in scenes)
