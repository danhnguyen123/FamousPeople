"""Stage timeline: build the Remotion props (video/src/schema.ts).

A scene's image runs from its first cue's start to the next scene's start, so
pauses between cues never show a black frame. Captions follow the cues exactly.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .config import Settings
from .models import Cue, Plan, SceneImage
from .project import Project

MOTIONS = ["zoomIn", "panRight", "zoomOut", "panLeft", "zoomIn", "panUp", "zoomOut", "panDown"]
TAIL = 0.5  # seconds kept after the last cue


def build_timeline(
    project: Project,
    plan: Plan,
    cues: list[Cue],
    images: list[SceneImage],
    settings: Settings,
    show_captions: bool = False,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> dict:
    public_rel = Path("projects") / project.slug
    public_dir = settings.remotion_dir / "public" / public_rel
    if public_dir.exists():
        shutil.rmtree(public_dir)
    public_dir.mkdir(parents=True)

    def publish(rel_path: str) -> str:
        target = public_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project.root / rel_path, target)
        return (public_rel / rel_path).as_posix()

    start = {c.index: c.start for c in cues}
    duration = max(c.end for c in cues) + TAIL
    starts = [start[s.cues[0]] for s in plan.scenes] + [duration]

    shots: list[dict] = []
    for k, img in enumerate(images):
        begin, end = starts[k], starts[k + 1]
        if img.file is None:
            if shots:  # hold the previous image through this scene
                shots[-1]["endSec"] = round(end, 3)
            continue
        shots.append({
            "src": publish(img.file),
            "startSec": round(begin, 3),
            "endSec": round(end, 3),
            "motion": MOTIONS[len(shots) % len(MOTIONS)],
            "focusX": 0.5,
            "focusY": 0.4,
            "credit": None,
        })
    if shots:
        shots[0]["startSec"] = 0.0
        shots[-1]["endSec"] = round(duration, 3)

    return {
        "title": project.meta.title or plan.title or project.slug,
        "language": project.language,
        "fps": fps,
        "width": width,
        "height": height,
        "durationSec": round(duration, 3),
        "crossfadeSec": 0.6,
        "showCaptions": show_captions,
        "showCredits": False,
        "audio": [{"src": publish(project.meta.audio), "startSec": 0.0}] if project.meta.audio else [],
        "shots": shots,
        "captions": [
            {"text": c.text, "startSec": round(c.start, 3), "endSec": round(c.end, 3)} for c in cues
        ],
    }
