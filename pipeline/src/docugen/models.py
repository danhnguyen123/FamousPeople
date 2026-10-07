"""Data models shared by the stages. Every stage output is JSON on disk."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Cue(BaseModel):
    """One SRT block, numbered 1..n in time order."""

    index: int
    start: float
    end: float
    text: str


# plan.json: written by Claude from the full SRT (prompts/keyword_planner.md)


class Group(BaseModel):
    group: int = Field(description="Group number, from 1 in order of first appearance")
    subject: str = Field(description="Full name of the person, or full original title of the work or place")
    context: str = Field(description="What makes this group's pictures specific: life stage, year, event")
    keywords: list[str] = Field(
        description="2 or 3 image search queries, most specific first; the first in the script "
        "language, at least one in English"
    )


class PlannedScene(BaseModel):
    cues: list[int] = Field(description="1 or 2 consecutive cue numbers")
    group: int


class Plan(BaseModel):
    main_subject: str = Field(description="Full name of the documentary's main person")
    title: str = Field(description="Documentary title in the script language")
    groups: list[Group]
    scenes: list[PlannedScene]


# search.json: raw results per group, merged from every source


class ImageHit(BaseModel):
    id: str  # stable hash of the image URL
    source: str  # dataforseo | google | bing | brave
    image_url: str
    page_url: str | None = None
    title: str = ""
    domain: str | None = None
    width: int | None = None
    height: int | None = None
    query: str = ""
    rank: int = 0


class GroupSearch(BaseModel):
    group: int
    queries: list[str] = []  # keywords already searched, in order
    hits: list[ImageHit] = []


# select.json: Claude's verdict on each group's hits (prompts/image_selector.md)


class Verdict(BaseModel):
    """Claude's answer: only the candidates to use, by their number in the list (1 = first)."""

    accepted: list[int] = Field(description="Numbers of the candidates to use, best first")


class GroupSelection(BaseModel):
    group: int
    accepted: list[str] = []  # image ids, best first: the group's pool
    rejected: list[str] = []  # image ids Claude left out (or never judged)


# images.json: the image finally shown in each scene


class SceneImage(BaseModel):
    scene: int  # 1-based position in plan.scenes
    group: int
    file: str | None  # path relative to the project, None when the previous image is held
    image_id: str | None = None
    source: str | None = None
    page_url: str | None = None
    reused: bool = False
    manual: bool = False
