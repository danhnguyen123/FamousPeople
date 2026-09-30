"""Parse an SRT file into cues, keeping the cue numbers Claude refers to."""

from __future__ import annotations

import re

from .models import Cue

_TIME = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)
_TAGS = re.compile(r"<[^>]+>|\{\\[^}]*\}")


def _seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def _timestamp(sec: float) -> str:
    ms = round(sec * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def parse_srt(text: str) -> list[Cue]:
    """Cues sorted by time and renumbered 1..n, so gaps in the file's numbering never matter."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    found: list[tuple[float, float, str]] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        for i, line in enumerate(lines):
            match = _TIME.search(line)
            if not match:
                continue
            g = match.groups()
            body = " ".join(" ".join(_TAGS.sub("", ln) for ln in lines[i + 1 :]).split())
            if body:
                found.append((_seconds(*g[:4]), _seconds(*g[4:]), body))
            break
    found.sort(key=lambda c: c[0])
    return [Cue(index=i, start=s, end=e, text=t) for i, (s, e, t) in enumerate(found, start=1)]


def numbered(cues: list[Cue]) -> str:
    """The SRT as Claude reads it: one cue per line with its number, timing and length."""
    return "\n".join(
        f"[{c.index}] {_timestamp(c.start)} --> {_timestamp(c.end)} ({c.end - c.start:.1f}s) {c.text}"
        for c in cues
    )
