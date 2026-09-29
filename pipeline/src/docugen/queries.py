"""Turn a visual brief into concrete searches."""

from __future__ import annotations

from .models import EntityInfo, VisualBrief
from .scoring import normalize

PERSON_TYPES = {"person_portrait", "person_event", "person_with_other"}
MAX_CATEGORY_YEARS = 4


def find_entity(name: str | None, entities: list[EntityInfo]) -> EntityInfo | None:
    if not name:
        return None
    wanted = normalize(name)
    for entity in entities:
        if any(normalize(n) == wanted for n in entity.names()):
            return entity
    return None


def commons_categories(brief: VisualBrief, entity: EntityInfo | None) -> list[str]:
    """Commons has per-year categories for well documented people: 'Madonna in 1990'."""
    if entity is None or not entity.commons_category or brief.visual_type not in PERSON_TYPES:
        return []
    cats: list[str] = []
    if brief.year_from or brief.year_to:
        lo = brief.year_from or brief.year_to
        hi = brief.year_to or brief.year_from
        assert lo is not None and hi is not None
        mid = (lo + hi) // 2
        years = sorted(range(lo, hi + 1), key=lambda y: abs(y - mid))[:MAX_CATEGORY_YEARS]
        cats.extend(f"{entity.commons_category} in {y}" for y in years)
    cats.append(entity.commons_category)
    return cats


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for q in items:
        key = normalize(q)
        if q.strip() and key not in seen:
            seen.add(key)
            out.append(q.strip())
    return out


def specific_queries(brief: VisualBrief) -> list[str]:
    return _dedupe([*brief.specific_queries, *brief.native_queries])


def broad_queries(brief: VisualBrief) -> list[str]:
    return _dedupe(brief.broad_queries)
