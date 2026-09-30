"""The stages, each reading and writing JSON in the project folder.

segment -> subject -> briefs -> search -> narrate -> select -> timeline -> render
Every stage is skipped when its output exists, unless forced, so a rerun
after a manual fix only redoes what changed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel
from rich.progress import track

from . import llm
from .clip_rank import load_ranker
from .config import Settings
from .footage import FootageSearch, build_providers
from .models import (
    DocumentSubject,
    EntityInfo,
    NarrationTrack,
    PersonFacts,
    Scene,
    SceneFootage,
    VisualBrief,
)
from .project import Project
from .render import render
from .review import write_credits, write_review
from .segment import segment_script
from .srt import group_cues, parse_srt
from .select_images import select_images
from .timeline import build_timeline
from .tts import estimate, make_continuous, synthesize

log = logging.getLogger(__name__)

STAGES = ["segment", "subject", "briefs", "search", "narrate", "select", "timeline", "render"]


class SubjectFile(BaseModel):
    subject: DocumentSubject
    entities: list[EntityInfo]


def stage_segment(p: Project) -> list[Scene]:
    if p.meta.source == "srt":
        scenes = group_cues(parse_srt(p.path("input.srt").read_text(encoding="utf-8")))
    else:
        scenes = segment_script(p.script(), p.language)
    p.save("scenes.json", scenes)
    return scenes


def to_entity(person: PersonFacts) -> EntityInfo:
    return EntityInfo(
        name=person.name,
        aliases=person.aliases,
        birth_year=person.birth_year,
        death_year=person.death_year,
        notable_works=person.notable_works,
    )


def stage_subject(p: Project) -> SubjectFile:
    subject = llm.identify_subject(p.script(), p.language)
    people = subject.people or [
        PersonFacts(name=subject.main_person, aliases=[], birth_year=None, death_year=None, notable_works=[])
    ]
    result = SubjectFile(subject=subject, entities=[to_entity(person) for person in people[:9]])
    p.save("subject.json", result)
    if not p.meta.title:
        p.meta.title = subject.title
        p.save_meta()
    return result


def stage_briefs(p: Project) -> list[VisualBrief]:
    scenes = p.load("scenes.json", list[Scene])
    sf = p.load("subject.json", SubjectFile)
    briefs = llm.write_briefs(scenes, sf.subject, sf.entities, p.language)
    p.save("briefs.json", briefs)
    return briefs


def stage_search(p: Project, settings: Settings) -> list[SceneFootage]:
    briefs = p.load("briefs.json", list[VisualBrief])
    sf = p.load("subject.json", SubjectFile)
    providers = build_providers(settings, language=p.language, cache_dir=p.path("cache/serpapi"))
    search = FootageSearch(settings, providers, sf.entities, load_ranker(settings.enable_clip))
    footage = [search.scene(b) for b in track(briefs, description="Searching footage")]
    p.save("footage.json", footage)
    return footage


SRT_TAIL = 0.5  # seconds kept after the last subtitle


def srt_narration(p: Project, scenes: list[Scene]) -> NarrationTrack:
    """Timings come straight from the subtitles; the audio is the file supplied with them."""
    duration = max(s.end or 0.0 for s in scenes) + SRT_TAIL
    times = [(s.index, s.start or 0.0, s.end or 0.0) for s in scenes]
    audio = [(p.meta.audio, 0.0)] if p.meta.audio else []
    return NarrationTrack(audio_files=audio, scenes=make_continuous(times, duration), duration=duration)


def stage_narrate(p: Project, settings: Settings, use_tts: bool) -> NarrationTrack:
    scenes = p.load("scenes.json", list[Scene])
    if p.meta.source == "srt":
        narration = srt_narration(p, scenes)
    else:
        narration = synthesize(p, scenes, settings) if use_tts else estimate(scenes, p.language)
    p.save("narration.json", narration)
    return narration


def stage_select(p: Project, max_shot: float) -> list[SceneFootage]:
    footage = p.load("footage.json", list[SceneFootage])
    narration = p.load("narration.json", NarrationTrack)
    footage = select_images(p, footage, narration, max_shot=max_shot)
    p.save("footage.json", footage)
    write_review(
        p,
        p.load("scenes.json", list[Scene]),
        p.load("briefs.json", list[VisualBrief]),
        footage,
        narration,
    )
    write_credits(p, footage)
    return footage


def stage_timeline(p: Project, settings: Settings, captions: bool) -> Path:
    timeline = build_timeline(
        p,
        p.load("scenes.json", list[Scene]),
        p.load("footage.json", list[SceneFootage]),
        p.load("narration.json", NarrationTrack),
        settings,
        title=p.meta.title or p.slug,
        show_captions=captions,
    )
    return p.save("timeline.json", timeline)


def stage_render(p: Project, settings: Settings) -> Path:
    out = p.path(f"out/{p.slug}-{p.language}.mp4")
    out.parent.mkdir(exist_ok=True)
    return render(p.path("timeline.json"), out, settings)


OUTPUTS = {
    "segment": "scenes.json",
    "subject": "subject.json",
    "briefs": "briefs.json",
    "search": "footage.json",
    "narrate": "narration.json",
}


def run(
    p: Project,
    settings: Settings,
    *,
    until: str = "render",
    force: set[str] | None = None,
    use_tts: bool = True,
    max_shot: float = 6.0,
    captions: bool = False,
) -> None:
    force = force or set()
    # Forcing a stage invalidates everything after it.
    if force:
        first = min(STAGES.index(s) for s in force)
        force = set(STAGES[first:])
    for stage in STAGES[: STAGES.index(until) + 1]:
        output = OUTPUTS.get(stage)
        if output and p.has(output) and stage not in force:
            log.info("skip %s (%s exists)", stage, output)
            continue
        log.info("stage %s", stage)
        if stage == "segment":
            stage_segment(p)
        elif stage == "subject":
            stage_subject(p)
        elif stage == "briefs":
            stage_briefs(p)
        elif stage == "search":
            stage_search(p, settings)
        elif stage == "narrate":
            stage_narrate(p, settings, use_tts)
        elif stage == "select":
            stage_select(p, max_shot)
        elif stage == "timeline":
            stage_timeline(p, settings, captions)
        elif stage == "render":
            stage_render(p, settings)
