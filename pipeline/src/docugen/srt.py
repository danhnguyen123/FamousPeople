"""SRT input: parse subtitle cues and group them into scenes with exact timings."""

from __future__ import annotations

import re

from .models import Cue, Scene

_TIME = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)
_TAGS = re.compile(r"<[^>]+>|\{\\[^}]*\}")
_SENTENCE_END = re.compile(r"[.!?…][\"'»”)\]]*$")


def _seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_srt(text: str) -> list[Cue]:
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        for i, line in enumerate(lines):
            match = _TIME.search(line)
            if not match:
                continue
            g = match.groups()
            body = " ".join(_TAGS.sub("", ln) for ln in lines[i + 1 :])
            body = " ".join(body.split())
            if body:
                cues.append(Cue(text=body, start=_seconds(*g[:4]), end=_seconds(*g[4:])))
            break
    return sorted(cues, key=lambda c: c.start)


def group_cues(cues: list[Cue], min_chars: int = 60, max_sec: float = 12.0) -> list[Scene]:
    """Merge consecutive cues into scenes.

    A scene closes once it has at least `min_chars` and its last cue ends a
    sentence, or when adding the next cue would make it longer than `max_sec`.
    """
    scenes: list[Scene] = []
    buffer: list[Cue] = []

    def flush() -> None:
        text = " ".join(c.text for c in buffer)
        scenes.append(
            Scene(
                index=len(scenes),
                text=text,
                sentences=[c.text for c in buffer],
                start=buffer[0].start,
                end=buffer[-1].end,
                cues=list(buffer),
            )
        )
        buffer.clear()

    for cue in cues:
        if buffer and cue.end - buffer[0].start > max_sec:
            flush()
        buffer.append(cue)
        length = len(" ".join(c.text for c in buffer))
        if length >= min_chars and _SENTENCE_END.search(cue.text):
            flush()
    if buffer:
        flush()
    return scenes


def srt_text(cues: list[Cue]) -> str:
    return " ".join(c.text for c in cues)
