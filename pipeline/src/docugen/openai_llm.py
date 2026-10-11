"""The select step through the OpenAI API (DOCUGEN_SELECT_PROVIDER=openai).

Same prompt (prompts/image_selector.md), same message and same Verdict as the
Claude path in llm.py, so the two are interchangeable. Calls go through
docugen.http, so a dry run can mock them with set_client.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from .config import get_settings
from .http import client, request_json
from .llm import _selector_message, prompt
from .models import Group, ImageHit, Verdict

log = logging.getLogger(__name__)

API = "https://api.openai.com/v1"
ENDPOINT = "/v1/chat/completions"
DONE = ("completed", "failed", "expired", "cancelled")


def _headers() -> dict[str, str]:
    key = get_settings().openai_api_key
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set (needed for DOCUGEN_SELECT_PROVIDER=openai)")
    return {"Authorization": f"Bearer {key}"}


def _schema() -> dict[str, Any]:
    # Strict structured outputs want every object closed and every property required.
    schema = Verdict.model_json_schema()
    schema["additionalProperties"] = False
    schema["required"] = list(schema["properties"])
    return schema


def _body(job: tuple[Group, str, list[ImageHit]]) -> dict[str, Any]:
    settings = get_settings()
    return {
        "model": settings.openai_model,
        "reasoning_effort": settings.select_effort,
        "max_completion_tokens": 16000,
        "messages": [
            {"role": "system", "content": prompt("image_selector")},
            {"role": "user", "content": _selector_message(*job)},
        ],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "verdict", "strict": True, "schema": _schema()}},
    }


def _verdict(gid: int, body: dict[str, Any]) -> Verdict | None:
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    if message.get("refusal"):
        log.warning("group %d: declined: %s", gid, message["refusal"])
        return None
    if choice.get("finish_reason") != "stop":
        log.warning("group %d: stopped with %s", gid, choice.get("finish_reason"))
        return None
    return Verdict.model_validate_json(message.get("content") or "")


def select_images(group: Group, main_subject: str, hits: list[ImageHit]) -> Verdict:
    body = request_json("POST", API + "/chat/completions", headers=_headers(),
                        json=_body((group, main_subject, hits)))
    u = body.get("usage") or {}
    log.info("image_selector (openai): %d input tokens, %d output tokens",
             u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
    verdict = _verdict(group.group, body)
    if verdict is None:
        raise RuntimeError("no usable answer")
    return verdict


def select_images_batch(jobs: dict[int, tuple[Group, str, list[ImageHit]]]) -> dict[int, Verdict]:
    """Same as select_images for many groups through the Batch API (half price, minutes to hours)."""
    lines = [
        json.dumps({"custom_id": f"group-{gid}", "method": "POST", "url": ENDPOINT, "body": _body(job)},
                   ensure_ascii=False)
        for gid, job in jobs.items()
    ]
    upload = client().post(API + "/files", headers=_headers(), data={"purpose": "batch"},
                           files={"file": ("select.jsonl", "\n".join(lines).encode("utf-8"), "application/jsonl")})
    upload.raise_for_status()
    batch = request_json("POST", API + "/batches", headers=_headers(), json={
        "input_file_id": upload.json()["id"], "endpoint": ENDPOINT, "completion_window": "24h",
    })
    log.info("select batch %s (openai %s): %d groups", batch["id"], get_settings().openai_model, len(lines))
    while batch["status"] not in DONE:
        time.sleep(20)
        batch = request_json("GET", f"{API}/batches/{batch['id']}", headers=_headers())
    if batch["status"] != "completed":
        log.warning("select batch %s ended as %s: %s", batch["id"], batch["status"], batch.get("errors"))
    out: dict[int, Verdict] = {}
    tokens_in = tokens_out = 0
    for file_key in ("output_file_id", "error_file_id"):
        if not batch.get(file_key):
            continue
        response = client().get(f"{API}/files/{batch[file_key]}/content", headers=_headers())
        response.raise_for_status()
        for line in response.text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            gid = int(row["custom_id"].removeprefix("group-"))
            result = row.get("response") or {}
            if row.get("error") or result.get("status_code") != 200:
                log.warning("group %d: batch request failed: %s", gid, row.get("error") or result.get("body"))
                continue
            body = result["body"]
            u = body.get("usage") or {}
            tokens_in += u.get("prompt_tokens", 0)
            tokens_out += u.get("completion_tokens", 0)
            try:
                verdict = _verdict(gid, body)
            except ValueError as exc:
                log.warning("group %d: unreadable answer: %s", gid, exc)
                continue
            if verdict is not None:
                out[gid] = verdict
    log.info("image_selector batch (openai): %d input tokens, %d output tokens (billed at half price)",
             tokens_in, tokens_out)
    return out
