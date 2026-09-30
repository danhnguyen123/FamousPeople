"""Claude calls. The prompts live in prompts/*.md: edit them there, not here."""

from __future__ import annotations

import logging
import time
from functools import cache
from pathlib import Path
from typing import TypeVar

import anthropic
from anthropic.lib._parse._transform import transform_schema
from pydantic import BaseModel, TypeAdapter

from .config import get_settings
from .languages import get_language
from .models import Cue, Group, ImageHit, Plan, Verdict
from .srt import numbered

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

PROMPTS = Path(__file__).parent / "prompts"
# Retries a policy-declined request on a fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@cache
def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


@cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _system(name: str) -> list[dict]:
    return [{"type": "text", "text": prompt(name), "cache_control": {"type": "ephemeral"}}]


def _ask(model: str, system: str, user: str, output: type[T], effort: str, max_tokens: int) -> T:
    # Streaming, because the plan of a long SRT is a long answer.
    with _client().beta.messages.stream(
        model=model,
        max_tokens=max_tokens,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": effort},
        system=_system(system),
        messages=[{"role": "user", "content": user}],
        output_format=output,
    ) as stream:
        response = stream.get_final_message()
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError(f"Claude hit max_tokens ({max_tokens})")
    if response.parsed_output is None:
        raise RuntimeError("Claude returned no structured output")
    return response.parsed_output


def plan_srt(cues: list[Cue], language: str) -> Plan:
    lang = get_language(language)
    user = (
        f"Script language: {lang.name}. There are {len(cues)} cues, numbered 1 to {len(cues)}.\n\n"
        f"<srt>\n{numbered(cues)}\n</srt>"
    )
    return _ask(get_settings().model, "keyword_planner", user, Plan, effort="high", max_tokens=64000)


def _selector_message(group: Group, main_subject: str, lines: list[str], hits: list[ImageHit]) -> str:
    rows = []
    for h in hits:
        size = f"{h.width}x{h.height}" if h.width and h.height else "?"
        page = (h.page_url or "")[:160]
        rows.append(f"{h.id} | {h.source} | {size} | {h.domain or '?'} | {h.title[:160]} | {page}")
    narration = "\n".join(f"- {line}" for line in lines)
    return (
        f"Documentary about: {main_subject}\n"
        f"Group subject: {group.subject}\n"
        f"Group context: {group.context}\n\n"
        f"Narration shown over this group's images:\n{narration}\n\n"
        f"Candidates (id | source | size | site | title | page URL):\n" + "\n".join(rows)
    )


def select_images(group: Group, main_subject: str, lines: list[str], hits: list[ImageHit]) -> Verdict:
    user = _selector_message(group, main_subject, lines, hits)
    return _ask(get_settings().select_model, "image_selector", user, Verdict, effort="medium",
                max_tokens=16000)


def select_images_batch(jobs: dict[int, tuple[Group, str, list[str], list[ImageHit]]]) -> dict[int, Verdict]:
    """Same as select_images for many groups through the Batches API (half price, a few minutes).

    Server-side fallbacks are not available on the Batches API, so a declined group
    just comes back without a verdict and is logged.
    """
    settings = get_settings()
    schema = transform_schema(TypeAdapter(Verdict).json_schema())
    requests = [
        {
            "custom_id": f"group-{gid}",
            "params": {
                "model": settings.select_model,
                "max_tokens": 16000,
                "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
                "system": _system("image_selector"),
                "messages": [{"role": "user", "content": _selector_message(*job)}],
            },
        }
        for gid, job in jobs.items()
    ]
    batch = _client().messages.batches.create(requests=requests)
    log.info("select batch %s: %d groups", batch.id, len(requests))
    while _client().messages.batches.retrieve(batch.id).processing_status != "ended":
        time.sleep(20)
    out: dict[int, Verdict] = {}
    for result in _client().messages.batches.results(batch.id):
        gid = int(result.custom_id.removeprefix("group-"))
        if result.result.type != "succeeded":
            log.warning("group %d: batch request %s", gid, result.result.type)
            continue
        message = result.result.message
        if message.stop_reason != "end_turn":
            log.warning("group %d: stopped with %s", gid, message.stop_reason)
            continue
        text = next((b.text for b in message.content if b.type == "text"), "")
        out[gid] = Verdict.model_validate_json(text)
    return out
