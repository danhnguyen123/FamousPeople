"""Resolve people to Wikidata: identity, names in 6 languages, dates, works.

Wikidata is what makes the search entity first: the aliases are used to verify
image metadata, the birth year turns "at 22" into a year, and the list of
works gives event anchors ("<film> premiere <year>").
"""

from __future__ import annotations

import re

from .http import get_json
from .languages import LANGUAGES
from .models import EntityInfo

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
HUMAN = "Q5"

WORKS_QUERY = """
SELECT ?work ?workLabel (MIN(YEAR(?date)) AS ?year) WHERE {{
  {{ ?work wdt:P161 wd:{qid} }} UNION {{ ?work wdt:P175 wd:{qid} }} UNION
  {{ ?work wdt:P50 wd:{qid} }} UNION {{ ?work wdt:P57 wd:{qid} }} UNION
  {{ ?work wdt:P86 wd:{qid} }} UNION {{ wd:{qid} wdt:P800 ?work }}
  OPTIONAL {{ ?work wdt:P577 ?date }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
GROUP BY ?work ?workLabel ORDER BY ?year LIMIT 300
"""


def _year(claims: dict, prop: str) -> int | None:
    for claim in claims.get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        match = re.match(r"^[+-]?(\d{1,4})-", value.get("time", ""))
        if match:
            return int(match.group(1))
    return None


def _string(claims: dict, prop: str) -> str | None:
    for claim in claims.get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, str):
            return value
    return None


def _is_human(claims: dict) -> bool:
    for claim in claims.get("P31", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if value.get("id") == HUMAN:
            return True
    return False


def _entity_from_json(name: str, entity: dict) -> EntityInfo:
    claims = entity.get("claims", {})
    labels = {k: v["value"] for k, v in entity.get("labels", {}).items()}
    aliases = [a["value"] for values in entity.get("aliases", {}).values() for a in values]
    return EntityInfo(
        name=labels.get("en", name),
        qid=entity.get("id"),
        description=entity.get("descriptions", {}).get("en", {}).get("value"),
        labels=labels,
        aliases=sorted(set(aliases)),
        birth_year=_year(claims, "P569"),
        death_year=_year(claims, "P570"),
        commons_category=_string(claims, "P373"),
        image_file=_string(claims, "P18"),
    )


def _get_entities(**params: str) -> dict:
    data = get_json(
        API,
        {
            "action": "wbgetentities",
            "format": "json",
            "props": "labels|aliases|descriptions|claims",
            "languages": "|".join(LANGUAGES),
            **params,
        },
    )
    return {k: v for k, v in data.get("entities", {}).items() if "missing" not in v}


def resolve_person(name: str, wikipedia_title: str | None = None) -> EntityInfo:
    """Find the Wikidata item for a person; returns a bare EntityInfo if not found."""
    entities: dict = {}
    if wikipedia_title:
        entities = _get_entities(sites="enwiki", titles=wikipedia_title)
    if not entities:
        found = get_json(
            API,
            {
                "action": "wbsearchentities",
                "search": name,
                "language": "en",
                "type": "item",
                "limit": "7",
                "format": "json",
            },
        )
        ids = [hit["id"] for hit in found.get("search", [])]
        if ids:
            entities = _get_entities(ids="|".join(ids))
            # Keep search ranking order.
            entities = {i: entities[i] for i in ids if i in entities}
    for entity in entities.values():
        if _is_human(entity.get("claims", {})):
            info = _entity_from_json(name, entity)
            info.notable_works = notable_works(info.qid) if info.qid else []
            return info
    return EntityInfo(name=name)


def notable_works(qid: str) -> list[str]:
    """Films, albums, books... linked to the person, as 'Title (year)'."""
    try:
        data = get_json(
            SPARQL,
            {"query": WORKS_QUERY.format(qid=qid), "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
        )
    except Exception:
        return []
    works = []
    for row in data.get("results", {}).get("bindings", []):
        label = row.get("workLabel", {}).get("value")
        if not label or re.fullmatch(r"Q\d+", label):
            continue
        year = row.get("year", {}).get("value")
        works.append(f"{label} ({year})" if year else label)
    return works
