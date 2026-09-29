"""Stage 6: pick and download the images for each scene, avoiding repeats."""

from __future__ import annotations

import io
import logging
import math
from pathlib import Path

import imagehash
from PIL import Image

from .http import client
from .models import NarrationTrack, SceneFootage
from .project import Project

log = logging.getLogger(__name__)

MAX_LONG_SIDE = 2560
DUPLICATE_DISTANCE = 6  # perceptual hash distance under which two images are "the same"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def shots_needed(duration: float, max_shot: float) -> int:
    return max(1, math.ceil(duration / max_shot - 0.15))


def _download(url: str, target: Path) -> Image.Image:
    response = client().get(url)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content))
    image = image.convert("RGB")
    image.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE))
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "JPEG", quality=90)
    return image


def manual_files(project: Project, scene_index: int) -> list[Path]:
    folder = project.path("manual")
    if not folder.exists():
        return []
    prefix = f"scene_{scene_index:03d}"
    return sorted(p for p in folder.iterdir() if p.name.startswith(prefix) and p.suffix.lower() in IMAGE_EXTS)


def select_images(
    project: Project,
    footage: list[SceneFootage],
    narration: NarrationTrack,
    max_shot: float = 6.0,
) -> list[SceneFootage]:
    durations = {t.scene_index: t.end - t.start for t in narration.scenes}
    used_hashes: list[imagehash.ImageHash] = []
    used_ids: set[str] = set()

    for scene in footage:
        scene.chosen, scene.local_files, scene.manual = [], {}, False

        manual = manual_files(project, scene.scene_index)
        if manual:
            scene.manual = True
            for i, path in enumerate(manual):
                key = f"manual-{i}"
                scene.chosen.append(key)
                scene.local_files[key] = str(path.relative_to(project.root))
            continue

        need = shots_needed(durations.get(scene.scene_index, max_shot), max_shot)
        for scored in scene.ranked:
            if len(scene.chosen) >= need:
                break
            cand = scored.candidate
            if cand.id in used_ids:
                continue
            target = project.path(f"assets/{scene.scene_index:03d}_{cand.id}.jpg")
            try:
                image = Image.open(target) if target.exists() else _download(cand.image_url, target)
            except Exception as exc:
                log.warning("scene %d: download failed %s: %s", scene.scene_index, cand.image_url, exc)
                continue
            phash = imagehash.phash(image)
            if any(phash - h < DUPLICATE_DISTANCE for h in used_hashes):
                continue  # same photo from another source, or a crop of one already used
            used_hashes.append(phash)
            used_ids.add(cand.id)
            scene.chosen.append(cand.id)
            scene.local_files[cand.id] = str(target.relative_to(project.root))

        if not scene.chosen and scene.ranked:
            # Everything relevant is already used: reuse the best one rather than show nothing.
            best = scene.ranked[0].candidate
            for other in footage:
                if best.id in other.local_files:
                    scene.chosen.append(best.id)
                    scene.local_files[best.id] = other.local_files[best.id]
                    break
        if not scene.chosen:
            log.warning("scene %d has no image; the previous shot will be held", scene.scene_index)
    return footage
