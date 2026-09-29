"""Contact sheet (review.html) and attribution list (credits.txt).

Nothing is published without a human look: the contact sheet shows, per
scene, the chosen images, the next best alternatives and every score, so a
wrong face is caught before rendering. To override a
scene, save a file as manual/scene_007.jpg and rerun `docugen select`.
"""

from __future__ import annotations

import html
import os

from .models import NarrationTrack, Scene, SceneFootage, VisualBrief
from .project import Project

TIER_COLOR = {"cleared": "#1f9d55", "attribution": "#2b6cb0", "review": "#c05621", "unknown": "#c53030"}


def _img_src(project: Project, scored, footage: SceneFootage) -> str:
    local = footage.local_files.get(scored.candidate.id)
    if local:
        return local
    return scored.candidate.thumb_url or scored.candidate.image_url


def write_review(
    project: Project,
    scenes: list[Scene],
    briefs: list[VisualBrief],
    footage: list[SceneFootage],
    narration: NarrationTrack | None,
) -> str:
    esc = html.escape
    brief_by = {b.scene_index: b for b in briefs}
    foot_by = {f.scene_index: f for f in footage}
    time_by = {t.scene_index: t for t in narration.scenes} if narration else {}
    parts = [
        "<!doctype html><meta charset='utf-8'><title>Review: " + esc(project.slug) + "</title>",
        "<style>body{font:14px system-ui;margin:24px;background:#111;color:#eee}"
        ".scene{border-top:1px solid #333;padding:16px 0}.imgs{display:flex;gap:10px;flex-wrap:wrap}"
        ".c{width:230px;font-size:11px}.c img{width:230px;height:140px;object-fit:cover;background:#222}"
        ".chosen img{outline:3px solid #f6e05e}.q{color:#9ae6b4}.warn{color:#fc8181}"
        ".t{display:inline-block;padding:1px 6px;border-radius:4px;color:#fff}</style>",
        f"<h1>{esc(project.slug)} ({esc(project.language)})</h1>",
    ]
    for scene in scenes:
        brief = brief_by.get(scene.index)
        foot = foot_by.get(scene.index)
        timing = time_by.get(scene.index)
        when = f"{timing.start:.1f}s to {timing.end:.1f}s" if timing else ""
        parts.append(f"<div class='scene'><b>Scene {scene.index}</b> <small>{when}</small><p>{esc(scene.text)}</p>")
        if brief:
            parts.append(
                f"<div class='q'>{esc(brief.visual_type)} | {esc(brief.primary_entity or '')} | "
                f"{brief.year_from or ''}-{brief.year_to or ''} | {esc(brief.event_anchor or '')}<br>"
                f"queries: {esc(' ; '.join(brief.specific_queries + brief.broad_queries))}</div>"
            )
        if foot and foot.manual:
            parts.append("<div class='q'>manual override</div>")
        if not foot or not foot.chosen:
            parts.append("<p class='warn'>No image selected: add manual/scene_%03d.jpg</p>" % scene.index)
        parts.append("<div class='imgs'>")
        if foot:
            shown = [s for s in foot.ranked if s.candidate.id in foot.chosen]
            shown += [s for s in foot.ranked if s.candidate.id not in foot.chosen][:6]
            for s in shown:
                c = s.candidate
                cls = "c chosen" if c.id in foot.chosen else "c"
                score_text = " ".join(f"{k}:{v}" for k, v in s.scores.items())
                parts.append(
                    f"<div class='{cls}'><a href='{esc(c.page_url or c.image_url)}' target='_blank'>"
                    f"<img loading='lazy' src='{esc(_img_src(project, s, foot))}'></a><br>"
                    f"<span class='t' style='background:{TIER_COLOR[s.license_tier]}'>{s.license_tier}</span> "
                    f"<b>{s.total:.2f}</b> {esc(c.provider)} {esc(c.license or '')}<br>"
                    f"{esc(c.title[:90])}<br><small>{esc(score_text)}</small></div>"
                )
        parts.append("</div></div>")
    path = project.path("review.html")
    path.write_text("\n".join(parts), encoding="utf-8")
    return os.fspath(path)


def write_credits(project: Project, footage: list[SceneFootage]) -> str:
    """Attribution block for the video description."""
    lines = []
    seen: set[str] = set()
    for foot in footage:
        by_id = {s.candidate.id: s for s in foot.ranked}
        for cid in foot.chosen:
            s = by_id.get(cid)
            if s is None or cid in seen:
                continue
            seen.add(cid)
            c = s.candidate
            if s.license_tier in ("attribution", "cleared") and c.provider != "pexels":
                author = c.author or "Unknown author"
                lines.append(f"{c.title or 'Image'} by {author}, {c.license or ''} ({c.page_url or c.image_url})")
    out = ["IMAGE CREDITS", *lines]
    path = project.path("credits.txt")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return os.fspath(path)
