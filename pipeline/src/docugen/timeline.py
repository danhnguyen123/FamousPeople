"""Stage 7: build the Remotion props (video/src/schema.ts) from all stage outputs."""

from __future__ import annotations

import shutil
from pathlib import Path

from .config import Settings
from .models import NarrationTrack, Scene, SceneFootage, ScoredCandidate
from .project import Project

MOTIONS = ["zoomIn", "panRight", "zoomOut", "panLeft", "zoomIn", "panUp", "zoomOut", "panDown"]
MAX_CREDIT = 90


def credit_line(scored: ScoredCandidate | None) -> str | None:
    """On-screen attribution for CC BY / CC BY-SA images."""
    if scored is None or scored.license_tier != "attribution":
        return None
    author = (scored.candidate.author or "Unknown").strip()
    text = f"Photo: {author} / {scored.candidate.license}"
    return text if len(text) <= MAX_CREDIT else text[: MAX_CREDIT - 1] + "…"


def caption_chunks(scene: Scene, start: float, end: float) -> list[dict]:
    """Split a scene's time between its sentences by character length."""
    total = sum(len(s) for s in scene.sentences) or 1
    out, cursor = [], start
    for sentence in scene.sentences:
        span = (end - start) * len(sentence) / total
        out.append({"text": sentence, "startSec": round(cursor, 3), "endSec": round(cursor + span, 3)})
        cursor += span
    return out


def build_timeline(
    project: Project,
    scenes: list[Scene],
    footage: list[SceneFootage],
    narration: NarrationTrack,
    settings: Settings,
    title: str,
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
        source = project.root / rel_path
        target = public_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return (public_rel / rel_path).as_posix()

    by_scene = {f.scene_index: f for f in footage}
    timings = {t.scene_index: t for t in narration.scenes}
    shots: list[dict] = []
    captions: list[dict] = []
    motion_i = 0

    for scene in scenes:
        timing = timings[scene.index]
        if scene.cues:  # SRT: keep the subtitle timings exactly
            captions.extend(
                {"text": c.text, "startSec": round(c.start, 3), "endSec": round(c.end, 3)}
                for c in scene.cues
            )
        else:
            captions.extend(caption_chunks(scene, timing.start, timing.end))
        scene_footage = by_scene.get(scene.index)
        chosen = scene_footage.chosen if scene_footage else []
        if not chosen:
            if shots:  # hold the previous image through this scene
                shots[-1]["endSec"] = round(timing.end, 3)
            continue
        scored_by_id = {s.candidate.id: s for s in scene_footage.ranked} if scene_footage else {}
        span = (timing.end - timing.start) / len(chosen)
        for k, cid in enumerate(chosen):
            shots.append(
                {
                    "src": publish(scene_footage.local_files[cid]),
                    "startSec": round(timing.start + k * span, 3),
                    "endSec": round(timing.start + (k + 1) * span, 3),
                    "motion": MOTIONS[motion_i % len(MOTIONS)],
                    "focusX": 0.5,
                    "focusY": 0.4,
                    "credit": credit_line(scored_by_id.get(cid)),
                }
            )
            motion_i += 1

    if shots:
        shots[0]["startSec"] = 0.0
        shots[-1]["endSec"] = round(narration.duration, 3)

    return {
        "title": title,
        "language": project.language,
        "fps": fps,
        "width": width,
        "height": height,
        "durationSec": round(narration.duration, 3),
        "crossfadeSec": 0.6,
        "showCaptions": show_captions,
        "showCredits": False,
        "audio": [{"src": publish(path), "startSec": round(start, 3)} for path, start in narration.audio_files],
        "shots": shots,
        "captions": captions,
    }
