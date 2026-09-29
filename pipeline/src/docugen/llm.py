"""Claude calls: identify the documentary subject and write per-scene visual briefs."""

from __future__ import annotations

import json
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from .config import get_settings
from .languages import get_language
from .models import BriefBatch, DocumentSubject, EntityInfo, Scene, VisualBrief

T = TypeVar("T", bound=BaseModel)

BRIEF_BATCH_SIZE = 25

SUBJECT_SYSTEM = """You read documentary narration scripts about famous people and identify \
who the documentary is about. Scripts can be in English, French, German, Italian, Polish or Dutch. \
Always return the canonical English name as used on English Wikipedia."""

BRIEF_SYSTEM = """You are the footage agent of an automated documentary editor. For every \
narration scene you decide what picture should be on screen and write image search queries \
that will find a real photo of it.

How to think about a scene:
- Work from what is spoken. Ignore stage directions.
- Be entity first. If the scene is about a named person, the image must show that person, so \
the query must contain their full name. Faces cannot be verified reliably, so the name in the \
image metadata is what proves identity.
- Anchor queries in time and events. "Winona Ryder 1994" is weak; "Winona Ryder Little Women \
premiere 1994" or "Winona Ryder 66th Academy Awards" is strong, because an event produces many \
captioned photos with the name, year and venue in the metadata.
- Use the facts provided about the subject (birth year, notable works) to infer the year and \
event when the narration only implies them ("at 22 she ..." means birth year + 22).
- Never use the narration sentence as a query. Queries are 2 to 6 words, like a photo caption.
- Order specific_queries from most specific to least. broad_queries are fallbacks that still \
fit the scene (the person in that decade, or the place, or the work).
- For scenes that are about a feeling, a general situation or a place with no named entity, \
use visual_type "generic" and write stock photo style queries (no names).
- If a scene refers back to someone ("she", "the actor"), resolve who it is from context.
- Queries are in English because archive metadata is mostly English. native_queries may add \
one or two in the script language when a local archive might caption the photo that way.
- clip_prompt is one plain English sentence describing the ideal frame (composition, era, \
setting) used to rank candidate images visually. Do not include the person's name in it."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _parse(system: str, user: str, output: type[T], max_tokens: int = 16000) -> T:
    settings = get_settings()
    response = _client().beta.messages.parse(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        # Retries a policy-declined request on a fallback model inside the same call.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium"},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=output,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Claude hit max_tokens; lower BRIEF_BATCH_SIZE")
    parsed = response.parsed_output
    if parsed is None:
        raise RuntimeError("Claude returned no structured output")
    return parsed


def identify_subject(script: str, language: str) -> DocumentSubject:
    lang = get_language(language)
    user = (
        f"Script language: {lang.name}. Documentary title must be in {lang.name}.\n\n"
        f"<script>\n{script}\n</script>"
    )
    return _parse(SUBJECT_SYSTEM, user, DocumentSubject, max_tokens=4000)


def _facts(entities: list[EntityInfo]) -> str:
    rows = []
    for e in entities:
        rows.append(
            {
                "name": e.name,
                "description": e.description,
                "born": e.birth_year,
                "died": e.death_year,
                "aliases": e.aliases[:8],
                "notable_works": e.notable_works[:25],
            }
        )
    return json.dumps(rows, ensure_ascii=False, indent=2)


def write_briefs(
    scenes: list[Scene],
    subject: DocumentSubject,
    entities: list[EntityInfo],
    language: str,
) -> list[VisualBrief]:
    lang = get_language(language)
    full_script = "\n".join(f"[{s.index}] {s.text}" for s in scenes)
    # The whole script goes in the (cached) system prompt so every batch sees
    # the full context for pronouns and dates, and only the batch varies.
    system = (
        f"{BRIEF_SYSTEM}\n\nDocumentary subject: {subject.main_person}\n"
        f"Known facts:\n{_facts(entities)}\n\n"
        f"Full script ({lang.name}), one scene per line:\n<script>\n{full_script}\n</script>"
    )

    briefs: list[VisualBrief] = []
    for start in range(0, len(scenes), BRIEF_BATCH_SIZE):
        batch = scenes[start : start + BRIEF_BATCH_SIZE]
        wanted = ", ".join(str(s.index) for s in batch)
        user = (
            f"Write one visual brief for each of these scenes: {wanted}. "
            "Return them in scene order with the matching scene_index."
        )
        result = _parse(system, user, BriefBatch)
        by_index = {b.scene_index: b for b in result.briefs}
        for scene in batch:
            brief = by_index.get(scene.index)
            if brief is None:
                raise RuntimeError(f"Claude skipped scene {scene.index}")
            briefs.append(brief)
    return briefs
