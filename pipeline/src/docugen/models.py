"""Data models shared by every pipeline stage. All stage outputs are JSON on disk."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, Field


class Cue(BaseModel):
    """One subtitle block from an SRT file."""

    text: str
    start: float
    end: float


class Scene(BaseModel):
    """One narration unit (1 to 3 sentences) that gets its own visual."""

    index: int
    text: str
    sentences: list[str]
    char_start: int = 0  # offset in the normalized script, used to map TTS timings
    # Set when the project comes from an SRT: exact timings, no TTS needed.
    start: float | None = None
    end: float | None = None
    cues: list[Cue] = []


VisualType = Literal[
    "person_portrait",  # the person, no specific event (a face shot works)
    "person_event",  # the person at a dated event: premiere, trial, concert, award
    "person_with_other",  # the person together with another named person
    "work",  # a film, album, book, product: poster, cover, still
    "place",  # a named location: city, venue, house, school
    "archival",  # a dated news event without the person in frame
    "generic",  # mood / b-roll: stock is fine (rain, city at night, courtroom)
]


class VisualBrief(BaseModel):
    """What the footage agent should look for in one scene."""

    scene_index: int
    visual_type: VisualType
    primary_entity: str | None = Field(
        description="Canonical English name of the person/work/place that must be in frame, or null"
    )
    other_entities: list[str]
    year_from: int | None
    year_to: int | None
    event_anchor: str | None = Field(
        description="A concrete, searchable event: 'Reality Bites premiere', '66th Academy Awards'"
    )
    location: str | None
    specific_queries: list[str] = Field(
        description="3 to 5 short English Google Images queries, most specific first"
    )
    broad_queries: list[str] = Field(description="1 to 2 fallback queries when specific ones fail")
    native_queries: list[str] = Field(
        description="0 to 2 queries in the script language, for sources with local captions"
    )
    clip_prompt: str = Field(description="One English sentence describing the ideal frame")


class BriefBatch(BaseModel):
    briefs: list[VisualBrief]


class PersonFacts(BaseModel):
    """What Claude knows about a person, used to anchor queries and check image titles."""

    name: str = Field(description="Canonical English name, as on English Wikipedia")
    aliases: list[str] = Field(description="Birth name, stage names, nicknames, spellings in other languages")
    birth_year: int | None
    death_year: int | None
    notable_works: list[str] = Field(
        description="Up to 25 films, albums, books or events with year, e.g. 'Beetlejuice (1988)'"
    )


class DocumentSubject(BaseModel):
    """The main person (and other recurring people) the documentary is about."""

    main_person: str = Field(description="Canonical English name, as on English Wikipedia")
    people: list[PersonFacts] = Field(
        description="The main person first, then up to 8 other people who appear in the script"
    )
    era_from: int | None
    era_to: int | None
    title: str = Field(description="A short documentary title in the script language")


class EntityInfo(BaseModel):
    """Facts about a person used to disambiguate and anchor searches."""

    name: str
    qid: str | None = None
    description: str | None = None
    labels: dict[str, str] = {}
    aliases: list[str] = []
    birth_year: int | None = None
    death_year: int | None = None
    commons_category: str | None = None  # only used when the wikimedia provider is enabled
    notable_works: list[str] = []

    def names(self) -> list[str]:
        """Every known name for matching metadata, longest first."""
        seen: dict[str, None] = {}
        for n in [self.name, *self.labels.values(), *self.aliases]:
            if n and n.strip():
                seen.setdefault(n.strip(), None)
        return sorted(seen, key=len, reverse=True)


LicenseTier = Literal["cleared", "attribution", "review", "unknown"]


class Candidate(BaseModel):
    provider: str
    image_url: str
    thumb_url: str | None = None
    page_url: str | None = None
    title: str = ""
    description: str = ""
    tags: list[str] = []
    categories: list[str] = []
    author: str | None = None
    license: str | None = None
    license_url: str | None = None
    width: int | None = None
    height: int | None = None
    date: str | None = None
    query: str = ""
    source_domain: str | None = None

    @property
    def id(self) -> str:
        return hashlib.sha1(self.image_url.encode()).hexdigest()[:16]

    def text_blob(self) -> str:
        parts = [
            self.title,
            self.description,
            " ".join(self.tags),
            " ".join(self.categories),
            self.page_url or "",
            self.date or "",
        ]
        return " ".join(p for p in parts if p)


class ScoredCandidate(BaseModel):
    candidate: Candidate
    scores: dict[str, float]
    total: float
    license_tier: LicenseTier
    rejected_reason: str | None = None


class SceneFootage(BaseModel):
    scene_index: int
    ranked: list[ScoredCandidate]  # best first, rejected ones excluded
    chosen: list[str] = []  # candidate ids picked for the timeline (1+ shots)
    local_files: dict[str, str] = {}  # candidate id -> path relative to project dir
    manual: bool = False  # true when the user dropped a file in manual/


class SceneTiming(BaseModel):
    scene_index: int
    start: float
    end: float


class NarrationTrack(BaseModel):
    audio_files: list[tuple[str, float]]  # (path relative to project dir, start sec)
    scenes: list[SceneTiming]
    duration: float
    estimated: bool = False  # true when no TTS was used
