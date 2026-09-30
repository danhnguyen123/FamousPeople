"""Stage select: Claude checks each group's search results from their metadata.

Groups whose pool stays under DOCUGEN_MIN_POOL accepted images get their next
keyword searched and only the new results are sent to Claude, until the
keywords run out.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .config import Settings
from .models import Cue, Group, GroupSearch, GroupSelection, ImageHit, Plan, Reject, Verdict
from .search import Source, merge, search_queries

log = logging.getLogger(__name__)


def narration_by_group(plan: Plan, cues: list[Cue]) -> dict[int, list[str]]:
    text = {c.index: c.text for c in cues}
    out: dict[int, list[str]] = {g.group: [] for g in plan.groups}
    for scene in plan.scenes:
        out.setdefault(scene.group, []).append(" ".join(text.get(i, "") for i in scene.cues))
    return out


def _judge(jobs: dict[int, tuple[Group, str, list[str], list[ImageHit]]], settings: Settings) -> dict[int, Verdict]:
    if not jobs:
        return {}
    if settings.select_batch:
        return llm.select_images_batch(jobs)

    def one(item: tuple[int, tuple]) -> tuple[int, Verdict | None]:
        gid, job = item
        try:
            return gid, llm.select_images(*job)
        except Exception as exc:
            log.warning("group %d: selection failed: %s", gid, exc)
            return gid, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        return {gid: v for gid, v in pool.map(one, jobs.items()) if v is not None}


def _apply(selection: GroupSelection, verdict: Verdict | None, hits: list[ImageHit]) -> None:
    ids = {h.id for h in hits}
    seen: set[str] = set()
    if verdict is not None:
        for pick in verdict.accepted:
            if pick.id in ids and pick.id not in seen:
                seen.add(pick.id)
                selection.accepted.append(pick)
        for reject in verdict.rejected:
            if reject.id in ids and reject.id not in seen:
                seen.add(reject.id)
                selection.rejected.append(reject)
    reason = "not reviewed" if verdict is not None else "selection failed"
    selection.rejected.extend(Reject(id=h.id, reason=reason) for h in hits if h.id not in seen)


def select_all(
    plan: Plan,
    cues: list[Cue],
    searches: dict[int, GroupSearch],
    sources: list[Source],
    settings: Settings,
    save_searches,
) -> dict[int, GroupSelection]:
    groups = {g.group: g for g in plan.groups}
    lines = narration_by_group(plan, cues)
    selections = {gid: GroupSelection(group=gid) for gid in groups}
    judged: dict[int, set[str]] = {gid: set() for gid in groups}
    todo = list(groups)

    while todo:
        new_hits = {gid: [h for h in searches[gid].hits if h.id not in judged[gid]] for gid in todo}
        jobs = {
            gid: (groups[gid], plan.main_subject, lines.get(gid, []), hits)
            for gid, hits in new_hits.items() if hits
        }
        log.info("select: %d groups, %d candidates", len(jobs), sum(len(j[3]) for j in jobs.values()))
        verdicts = _judge(jobs, settings)
        for gid, hits in new_hits.items():
            if hits:
                _apply(selections[gid], verdicts.get(gid), hits)
                judged[gid].update(h.id for h in hits)

        # Small pools: search the next keyword of those groups, then judge only the new results.
        next_query: dict[int, str] = {}
        for gid in todo:
            done = searches[gid].queries
            remaining = [k for k in groups[gid].keywords if k not in done]
            if len(selections[gid].accepted) < settings.min_pool and remaining:
                next_query[gid] = remaining[0]
        if not next_query:
            break
        log.info("select: %d groups have fewer than %d images, searching their next keyword",
                 len(next_query), settings.min_pool)
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
