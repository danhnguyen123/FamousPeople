"""The stages, each reading and writing files in the project folder.

plan -> search -> select -> download -> timeline -> render
A stage is skipped when its output exists, unless forced (which also redoes
every later stage), so a rerun after a manual fix only redoes what changed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import llm
from .config import Settings
from .download import assign_images, write_reports
from .languages import get_language
from .models import Cue, GroupSearch, GroupSelection, Plan, PlannedScene, SceneImage
from .project import Project
from .render import render
from .search import build_sources, merge, search_queries
from .select import select_all
from .timeline import build_timeline

log = logging.getLogger(__name__)

STAGES = ["plan", "search", "select", "download", "timeline", "render"]
OUTPUTS = {
    "plan": "plan.json",
    "search": "search.json",
    "select": "select.json",
    "download": "images.json",
    "timeline": "timeline.json",
}


def check_plan(plan: Plan, cues: list[Cue]) -> Plan:
    """Make every cue belong to exactly one scene, in order, with at most 2 cues per scene."""
    known = {c.index for c in cues}
    groups = {g.group for g in plan.groups}
    scenes: list[PlannedScene] = []
    covered: set[int] = set()
    last = 0
    for scene in plan.scenes:
        ids = sorted(i for i in scene.cues if i in known and i > last and i not in covered)
        if not ids:
            continue
        group = scene.group if scene.group in groups else (scenes[-1].group if scenes else plan.groups[0].group)
        if group != scene.group:
            log.warning("scene with cues %s: unknown group %d, using %d", ids, scene.group, group)
        for i in range(last + 1, ids[0]):  # skipped cues become their own scenes
            if i in known:
                log.warning("cue %d was not in any scene: added with group %d", i, group)
                scenes.append(PlannedScene(cues=[i], group=scenes[-1].group if scenes else group))
                covered.add(i)
        for k in range(0, len(ids), 2):
            if k == 2:
                log.warning("scene with cues %s had more than 2 cues: split", ids)
            scenes.append(PlannedScene(cues=ids[k : k + 2], group=group))
        covered.update(ids)
        last = ids[-1]
    for i in sorted(known - covered):
        log.warning("cue %d was not in any scene: added to the end", i)
        scenes.append(PlannedScene(cues=[i], group=scenes[-1].group if scenes else plan.groups[0].group))
    plan.scenes = scenes
    return plan


def stage_plan(p: Project) -> Plan:
    cues = p.cues()
    plan = check_plan(llm.plan_srt(cues, p.language), cues)
    p.save("plan.json", plan)
    if not p.meta.title:
        p.meta.title = plan.title
        p.save_meta()
    log.info("plan: %d cues, %d scenes, %d groups", len(cues), len(plan.scenes), len(plan.groups))
    return plan


def _sources(p: Project, settings: Settings):
    return build_sources(settings, get_language(p.language), p.path("cache"))


def _save_searches(p: Project, searches: dict[int, GroupSearch]) -> None:
    p.save("search.json", list(searches.values()))


def _load_searches(p: Project) -> dict[int, GroupSearch]:
    return {s.group: s for s in p.load("search.json", list[GroupSearch])}


def stage_search(p: Project, settings: Settings) -> None:
    """Each group's first keyword on every source."""
    plan = p.load("plan.json", Plan)
    first = {g.group: (g.keywords or [g.subject])[0] for g in plan.groups}
    results = search_queries(_sources(p, settings), list(first.values()))
    searches = {}
    for g in plan.groups:
        query = first[g.group]
        hits = merge(results.get(query, {}), settings.candidates_per_source, settings.blocked_domains)
        searches[g.group] = GroupSearch(group=g.group, queries=[query], hits=hits)
    _save_searches(p, searches)
    log.info("search: %d results for %d groups", sum(len(s.hits) for s in searches.values()), len(searches))


def stage_select(p: Project, settings: Settings) -> None:
    searches = _load_searches(p)
    selections = select_all(
        p.load("plan.json", Plan), searches, _sources(p, settings), settings,
        save_searches=lambda: _save_searches(p, searches),
    )
    p.save("select.json", list(selections.values()))


def stage_download(p: Project, settings: Settings) -> None:
    plan, cues = p.load("plan.json", Plan), p.cues()
    searches = _load_searches(p)
    selections = {s.group: s for s in p.load("select.json", list[GroupSelection])}
    images = assign_images(p, plan, searches, selections, settings)
    p.save("images.json", images)
    write_reports(p, plan, cues, searches, selections, images)
    missing = sum(1 for i in images if i.file is None)
    log.info("download: %d scenes, %d reused, %d without image (review plan.csv)",
             len(images), sum(i.reused for i in images), missing)


def stage_timeline(p: Project, settings: Settings, captions: bool) -> Path:
    timeline = build_timeline(p, p.load("plan.json", Plan), p.cues(), p.load("images.json", list[SceneImage]),
                              settings, show_captions=captions)
    return p.save("timeline.json", timeline)


def stage_render(p: Project, settings: Settings) -> Path:
    out = p.path(f"out/{p.slug}-{p.language}.mp4")
    out.parent.mkdir(exist_ok=True)
    return render(p.path("timeline.json"), out, settings)


def run(p: Project, settings: Settings, *, until: str = "render", force: set[str] | None = None,
        captions: bool = False) -> None:
    force = force or set()
    if force:  # forcing a stage redoes everything after it
        force = set(STAGES[min(STAGES.index(s) for s in force):])
    for stage in STAGES[: STAGES.index(until) + 1]:
        output = OUTPUTS.get(stage)
        if output and p.has(output) and stage not in force:
            log.info("skip %s (%s exists)", stage, output)
            continue
        log.info("stage %s", stage)
        if stage == "plan":
            stage_plan(p)
        elif stage == "search":
            stage_search(p, settings)
        elif stage == "select":
            stage_select(p, settings)
        elif stage == "download":
            stage_download(p, settings)
        elif stage == "timeline":
            stage_timeline(p, settings, captions)
        elif stage == "render":
            stage_render(p, settings)
