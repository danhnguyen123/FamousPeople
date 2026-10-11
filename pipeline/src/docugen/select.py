"""Stage select: Claude checks each group's search results from their metadata.

A group needs at least DOCUGEN_MIN_POOL accepted images, and one for every
DOCUGEN_SCENES_PER_IMAGE of its scenes, so a large group does not show the same
few photos over and over. A group under that gets its next keyword searched and
only the new results are sent to Claude, until the keywords run out.

Every answer is cached in cache/select/ (keyed on provider, model, effort,
prompt and message), so a run stopped by an API error keeps what it already
paid for. A group the API gave no answer for keeps its candidates unjudged and
the stage fails at the end: run it again to retry only those groups.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections import Counter
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from . import llm, openai_llm
from .config import Settings
from .models import Group, GroupSearch, GroupSelection, ImageHit, Plan, Verdict
from .search import Source, merge, search_queries

log = logging.getLogger(__name__)


def _verdict_key(job: tuple[Group, str, list[ImageHit]], settings: Settings) -> str:
    model = settings.openai_model if settings.select_provider == "openai" else settings.select_model
    text = "\n".join([settings.select_provider, model, settings.select_effort,
                      llm.prompt("image_selector"), llm._selector_message(*job)])
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _judge(jobs: dict[int, tuple[Group, str, list[ImageHit]]], settings: Settings,
           cache_dir: Path | None = None) -> dict[int, Verdict]:
    """Verdicts for the jobs, from cache_dir when already answered."""
    if not jobs:
        return {}
    if cache_dir is None:
        return _ask(jobs, settings)
    cache_dir.mkdir(parents=True, exist_ok=True)
    keys = {gid: _verdict_key(job, settings) for gid, job in jobs.items()}
    out: dict[int, Verdict] = {}
    for gid, key in keys.items():
        f = cache_dir / f"{key}.json"
        if f.exists():
            out[gid] = Verdict.model_validate_json(f.read_text(encoding="utf-8"))
    if out:
        log.info("select: %d groups answered from cache", len(out))
    fresh = _ask({gid: job for gid, job in jobs.items() if gid not in out}, settings)
    for gid, verdict in fresh.items():
        (cache_dir / f"{keys[gid]}.json").write_text(json.dumps(verdict.model_dump()), encoding="utf-8")
    return out | fresh


def _ask(jobs: dict[int, tuple[Group, str, list[ImageHit]]], settings: Settings) -> dict[int, Verdict]:
    if not jobs:
        return {}
    if settings.select_provider not in ("claude", "openai"):
        raise ValueError(f"DOCUGEN_SELECT_PROVIDER must be claude or openai, not {settings.select_provider!r}")
    backend = openai_llm if settings.select_provider == "openai" else llm
    if settings.select_batch:
        return backend.select_images_batch(jobs)

    def one(item: tuple[int, tuple]) -> tuple[int, Verdict | None]:
        gid, job = item
        try:
            return gid, backend.select_images(*job)
        except Exception as exc:
            log.warning("group %d: selection failed: %s", gid, exc)
            return gid, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        return {gid: v for gid, v in pool.map(one, jobs.items()) if v is not None}


def _apply(selection: GroupSelection, verdict: Verdict | None, hits: list[ImageHit]) -> None:
    """Claude answers with the candidates' numbers in the list it was sent (1-based)."""
    chosen: list[str] = []
    for n in verdict.accepted if verdict is not None else []:
        if 1 <= n <= len(hits) and hits[n - 1].id not in chosen:
            chosen.append(hits[n - 1].id)
    selection.accepted.extend(chosen)
    selection.rejected.extend(h.id for h in hits if h.id not in chosen)


def select_all(
    plan: Plan,
    searches: dict[int, GroupSearch],
    sources: list[Source],
    settings: Settings,
    save_searches,
    cache_dir: Path | None = None,
) -> dict[int, GroupSelection]:
    groups = {g.group: g for g in plan.groups}
    scenes = Counter(s.group for s in plan.scenes)
    wanted = {gid: max(settings.min_pool, math.ceil(scenes[gid] / settings.scenes_per_image)) for gid in groups}
    selections = {gid: GroupSelection(group=gid) for gid in groups}
    judged: dict[int, set[str]] = {gid: set() for gid in groups}
    todo = list(groups)
    unanswered: set[int] = set()

    while todo:
        new_hits = {gid: [h for h in searches[gid].hits if h.id not in judged[gid]] for gid in todo}
        jobs = {
            gid: (groups[gid], plan.main_subject, hits)
            for gid, hits in new_hits.items() if hits
        }
        log.info("select: %d groups, %d candidates", len(jobs), sum(len(j[2]) for j in jobs.values()))
        verdicts = _judge(jobs, settings, cache_dir)
        for gid, hits in new_hits.items():
            if not hits:
                continue
            if gid not in verdicts:
                # No answer (API error): these candidates were not judged, so do not reject them
                # and do not move on to the next keyword.
                unanswered.add(gid)
                continue
            _apply(selections[gid], verdicts[gid], hits)
            judged[gid].update(h.id for h in hits)

        # Pools too small for their group: search its next keyword, then judge only the new results.
        next_query: dict[int, str] = {}
        for gid in todo:
            if gid in unanswered:
                continue
            done = searches[gid].queries
            remaining = [k for k in groups[gid].keywords if k not in done]
            if len(selections[gid].accepted) < wanted[gid] and remaining:
                next_query[gid] = remaining[0]
        if not next_query:
            break
        log.info("select: %d groups have too few images for their scenes, searching their next keyword",
                 len(next_query))
        results = search_queries(sources, list(set(next_query.values())))
        for gid, query in next_query.items():
            s = searches[gid]
            s.queries.append(query)
            s.hits = merge(results.get(query, {}), settings.candidates_per_source,
                           settings.blocked_domains, existing=s.hits)
        save_searches()
        todo = list(next_query)

    if unanswered:
        raise RuntimeError(f"select: no answer for {len(unanswered)} groups ({sorted(unanswered)}); "
                           "answers so far are cached, run the stage again to retry these groups")
    for gid, sel in selections.items():
        if not sel.accepted:
            log.warning("group %d (%s): no usable image found", gid, groups[gid].subject)
    return selections
