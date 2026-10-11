"""Stage select: Claude checks each group's search results from their metadata.

A group needs at least DOCUGEN_MIN_POOL accepted images, and one for every
DOCUGEN_SCENES_PER_IMAGE of its scenes, so a large group does not show the same
few photos over and over. A group under that gets its next keyword searched and
only the new results are sent to Claude, until the keywords run out.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from . import llm, openai_llm
from .config import Settings
from .models import Group, GroupSearch, GroupSelection, ImageHit, Plan, Verdict
from .search import Source, merge, search_queries

log = logging.getLogger(__name__)


def _judge(jobs: dict[int, tuple[Group, str, list[ImageHit]]], settings: Settings) -> dict[int, Verdict]:
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
) -> dict[int, GroupSelection]:
    groups = {g.group: g for g in plan.groups}
    scenes = Counter(s.group for s in plan.scenes)
    wanted = {gid: max(settings.min_pool, math.ceil(scenes[gid] / settings.scenes_per_image)) for gid in groups}
    selections = {gid: GroupSelection(group=gid) for gid in groups}
    judged: dict[int, set[str]] = {gid: set() for gid in groups}
    todo = list(groups)

    while todo:
        new_hits = {gid: [h for h in searches[gid].hits if h.id not in judged[gid]] for gid in todo}
        jobs = {
            gid: (groups[gid], plan.main_subject, hits)
            for gid, hits in new_hits.items() if hits
        }
        log.info("select: %d groups, %d candidates", len(jobs), sum(len(j[2]) for j in jobs.values()))
        verdicts = _judge(jobs, settings)
        for gid, hits in new_hits.items():
            if hits:
                _apply(selections[gid], verdicts.get(gid), hits)
                judged[gid].update(h.id for h in hits)

        # Pools too small for their group: search its next keyword, then judge only the new results.
        next_query: dict[int, str] = {}
        for gid in todo:
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

    for gid, sel in selections.items():
        if not sel.accepted:
            log.warning("group %d (%s): no usable image found", gid, groups[gid].subject)
    return selections
