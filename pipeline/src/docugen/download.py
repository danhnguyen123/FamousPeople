"""Stage download: give every scene an image from its group's accepted pool.

Each scene takes the next unused image of its group, in Claude's order. When the
pool is used up the group's images come back, never twice in a row and, when
possible, not within DOCUGEN_REUSE_GAP seconds. A file in manual/ named
scene_007.jpg (any image extension) replaces scene 7's image.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

import imagehash
from PIL import Image

from .config import Settings
from .http import client
from .models import Cue, GroupSearch, GroupSelection, ImageHit, Plan, SceneImage
from .project import Project

log = logging.getLogger(__name__)

MAX_LONG_SIDE = 2560
DUPLICATE_DISTANCE = 6  # perceptual hash distance under which two images are "the same"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def manual_file(project: Project, scene: int) -> Path | None:
    folder = project.path("manual")
    if not folder.exists():
        return None
    for path in sorted(folder.iterdir()):
        if path.stem == f"scene_{scene:03d}" and path.suffix.lower() in IMAGE_EXTS:
            return path
    return None


class Downloader:
    def __init__(self, project: Project, settings: Settings):
        self.project = project
        self.settings = settings
        self.ok: dict[str, str] = {}  # image id -> file relative to the project
        self.bad: set[str] = set()
        self.hashes: list[tuple[str, imagehash.ImageHash]] = []

    def get(self, h: ImageHit) -> str | None:
        """Download once; None if it fails, is too small or duplicates another image."""
        if h.id in self.ok:
            return self.ok[h.id]
        if h.id in self.bad:
            return None
        target = self.project.path(f"assets/{h.id}.jpg")
        try:
            image = Image.open(target) if target.exists() else self._download(h, target)
        except Exception as exc:
            log.debug("download failed %s: %s", h.image_url, exc)
            self.bad.add(h.id)
            return None
        if min(image.size) < self.settings.min_side:
            log.debug("too small %s: %s", h.image_url, image.size)
            self.bad.add(h.id)
            return None
        phash = imagehash.phash(image)
        if any(phash - other < DUPLICATE_DISTANCE for _, other in self.hashes):
            self.bad.add(h.id)  # same photo from another site, or a crop of one already used
            return None
        self.hashes.append((h.id, phash))
        self.ok[h.id] = str(target.relative_to(self.project.root))
        return self.ok[h.id]

    def _download(self, h: ImageHit, target: Path) -> Image.Image:
        # Many sites refuse hotlinks without their page as Referer.
        headers = {"Referer": h.page_url} if h.page_url else None
        response = client().get(h.image_url, headers=headers, timeout=30)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise ValueError(f"not an image ({content_type or 'no content-type'})")
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        if min(image.size) >= self.settings.min_side:
            image.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE))
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, "JPEG", quality=90)
        return image


def assign_images(
    project: Project,
    plan: Plan,
    cues: list[Cue],
    searches: dict[int, GroupSearch],
    selections: dict[int, GroupSelection],
    settings: Settings,
) -> list[SceneImage]:
    start = {c.index: c.start for c in cues}
    hits = {gid: {h.id: h for h in s.hits} for gid, s in searches.items()}
    pools = {gid: [p.id for p in sel.accepted] for gid, sel in selections.items()}
    main_groups = [g.group for g in plan.groups if g.subject == plan.main_subject]
    dl = Downloader(project, settings)
    used: set[str] = set()
    last_used: dict[str, float] = {}
    out: list[SceneImage] = []
    prev: str | None = None

    def fresh(gid: int) -> str | None:
        for image_id in pools.get(gid, []):
            if image_id not in used and dl.get(hits[gid][image_id]):
                return image_id
        return None

    def reuse(gid: int, now: float) -> str | None:
        options = [i for i in pools.get(gid, []) if i in dl.ok and i != prev]
        if not options:
            return None
        spaced = [i for i in options if now - last_used.get(i, -1e9) >= settings.reuse_gap]
        return min(spaced or options, key=lambda i: last_used.get(i, -1e9))

    for n, scene in enumerate(plan.scenes, start=1):
        now = start.get(scene.cues[0], 0.0)
        manual = manual_file(project, n)
        if manual is not None:
            out.append(SceneImage(scene=n, group=scene.group, file=str(manual.relative_to(project.root)),
                                  manual=True))
            prev = None
            continue

        image_id, gid, reused = fresh(scene.group), scene.group, False
        if image_id is None:
            image_id, reused = reuse(scene.group, now), True
        if image_id is None:  # nothing usable in this group: fall back to the main person
            for mg in main_groups:
                image_id, gid = fresh(mg) or reuse(mg, now), mg
                if image_id:
                    break
        if image_id is None:
            log.warning("scene %d (group %d): no image, holding the previous one", n, scene.group)
            out.append(SceneImage(scene=n, group=scene.group, file=None))
            continue

        h = hits[gid][image_id]
        used.add(image_id)
        last_used[image_id] = now
        prev = image_id
        out.append(SceneImage(scene=n, group=scene.group, file=dl.ok[image_id], image_id=image_id,
                              source=h.source, page_url=h.page_url, reused=reused or gid != scene.group))
    return out


def write_reports(
    project: Project,
    plan: Plan,
    cues: list[Cue],
    searches: dict[int, GroupSearch],
    selections: dict[int, GroupSelection],
    images: list[SceneImage],
) -> None:
    """plan.csv (one row per scene) and candidates.csv (every result with Claude's verdict)."""
    groups = {g.group: g for g in plan.groups}
    cue = {c.index: c for c in cues}
    notes = {p.id: p.note for sel in selections.values() for p in sel.accepted}

    with project.path("plan.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Scene", "Start", "Cues", "Text", "Group", "Subject", "Context", "Keywords",
                    "Image file", "Source", "Reused", "Note", "Page URL"])
        for scene, img in zip(plan.scenes, images):
            g = groups[scene.group]
            w.writerow([
                img.scene, f"{cue[scene.cues[0]].start:.2f}", "+".join(map(str, scene.cues)),
                " ".join(cue[i].text for i in scene.cues), g.group, g.subject, g.context,
                " | ".join(g.keywords), img.file or "(hold previous)", img.source or "",
                "yes" if img.reused else "", "manual" if img.manual else notes.get(img.image_id or "", ""),
                img.page_url or "",
            ])

    with project.path("candidates.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Group", "Subject", "Id", "Source", "Query", "Verdict", "Note", "Title", "Size",
                    "Page URL", "Image URL"])
        for gid, s in searches.items():
            sel = selections.get(gid)
            verdict = {p.id: (p.match, p.note) for p in sel.accepted} if sel else {}
            verdict.update({r.id: ("rejected", r.reason) for r in sel.rejected} if sel else {})
            for h in s.hits:
                v, note = verdict.get(h.id, ("", ""))
                size = f"{h.width}x{h.height}" if h.width and h.height else ""
                w.writerow([gid, groups[gid].subject, h.id, h.source, h.query, v, note, h.title, size,
                            h.page_url or "", h.image_url])
