"""Entity-first scoring of image candidates.

CLIP cannot tell two actresses apart, so identity comes from metadata: the
person's name (or a Wikidata alias) must appear in the file title, caption,
categories or page URL. CLIP only reranks for how well the frame fits the
scene. Final score for scenes about a named entity:

    40% entity    name / alias found in metadata
    25% source    how trustworthy the source's captions are
    20% context   year and event anchor found in metadata
    10% clip      visual fit with the scene (neutral 0.5 when CLIP is off)
     5% quality   resolution and aspect ratio

Generic mood scenes have no entity, so the visual fit carries more weight.
"""

from __future__ import annotations

import re
import unicodedata

from .config import Settings
from .models import Candidate, EntityInfo, LicenseTier, ScoredCandidate, VisualBrief

ENTITY_WEIGHTS = {"entity": 0.40, "source": 0.25, "context": 0.20, "clip": 0.10, "quality": 0.05}
GENERIC_WEIGHTS = {"entity": 0.0, "source": 0.25, "context": 0.15, "clip": 0.40, "quality": 0.20}

# Scene types where the named entity must be proven by metadata.
IDENTITY_REQUIRED = {"person_portrait", "person_event", "person_with_other"}

MIN_SHORT_SIDE = 400

# Stock agencies serve watermarked previews: never usable.
WATERMARKED = {
    "gettyimages.com", "gettyimages.co.uk", "alamy.com", "shutterstock.com", "istockphoto.com",
    "dreamstime.com", "depositphotos.com", "123rf.com", "agefotostock.com", "bridgemanimages.com",
}

WEB_DOMAIN_TRUST = {
    "wikipedia.org": 0.8, "imdb.com": 0.6, "nytimes.com": 0.6, "theguardian.com": 0.6,
    "vanityfair.com": 0.55, "vogue.com": 0.55, "flickr.com": 0.55, "tumblr.com": 0.4,
    "pinterest.com": 0.35, "pinimg.com": 0.3, "fandom.com": 0.45, "reddit.com": 0.3,
}

_YEAR = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)")
_STOPWORDS = {"the", "a", "an", "of", "at", "in", "on", "and", "for", "to", "with", "de", "la", "le"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ł", "l").replace("Ł", "L")
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def _contains(blob: str, phrase: str) -> bool:
    needle = normalize(phrase)
    return len(needle.strip()) > 1 and needle in blob


def _domain_match(domain: str | None, domains: set[str] | list[str] | dict) -> str | None:
    if not domain:
        return None
    for d in domains:
        if domain == d or domain.endswith("." + d):
            return d
    return None


def entity_score(blob: str, entity: EntityInfo | None) -> float:
    if entity is None:
        return 1.0
    for name in entity.names():
        if _contains(blob, name):
            return 1.0
    surname = entity.name.split()[-1] if entity.name.split() else ""
    if len(surname) >= 4 and _contains(blob, surname):
        return 0.45
    return 0.0


def context_score(blob: str, cand: Candidate, brief: VisualBrief) -> float:
    years = {int(y) for y in _YEAR.findall(blob)}
    if brief.year_from is None and brief.year_to is None:
        temporal = 0.6
    elif not years:
        temporal = 0.4
    else:
        lo = brief.year_from or brief.year_to or 0
        hi = brief.year_to or brief.year_from or 0
        distance = min(0 if lo <= y <= hi else min(abs(y - lo), abs(y - hi)) for y in years)
        temporal = 1.0 if distance == 0 else 0.7 if distance <= 2 else 0.4 if distance <= 5 else 0.05

    anchor_terms = [
        t for t in normalize(" ".join(filter(None, [brief.event_anchor, brief.location]))).split()
        if t not in _STOPWORDS and len(t) > 2 and not t.isdigit()
    ]
    if not anchor_terms:
        return temporal
    hits = sum(1 for t in anchor_terms if f" {t} " in blob)
    return 0.6 * temporal + 0.4 * (hits / len(anchor_terms))


def source_score(cand: Candidate, brief: VisualBrief, settings: Settings) -> float:
    generic = brief.visual_type == "generic"
    if cand.provider == "wikimedia":
        score = 0.9
    elif cand.provider == "openverse":
        score = 0.7 if "flickr" in (cand.source_domain or "") else 0.6
    elif cand.provider == "pexels":
        score = 0.8 if generic else 0.1
    else:
        match = _domain_match(cand.source_domain, WEB_DOMAIN_TRUST)
        score = WEB_DOMAIN_TRUST[match] if match else 0.5
    if _domain_match(cand.source_domain, settings.preferred_domains):
        score = min(1.0, score + 0.15)
    return score


def quality_score(cand: Candidate) -> float:
    if not cand.width or not cand.height:
        return 0.5
    short = min(cand.width, cand.height)
    score = min(1.0, short / 1080)
    if cand.width / cand.height >= 1.3:
        score = min(1.0, score + 0.15)
    return score


def license_tier(cand: Candidate) -> LicenseTier:
    if cand.provider == "pexels":
        return "cleared"
    if cand.provider == "web":
        return "unknown"
    lic = (cand.license or "").lower()
    if not lic:
        return "unknown"
    if any(k in lic for k in ("public domain", "pdm", "cc0", "pd-", "pd ")) or lic == "pd":
        return "cleared"
    if "nc" in lic.replace("-", " ").split() or "nd" in lic.replace("-", " ").split():
        return "review"  # NonCommercial / NoDerivatives: not for a monetized, cropped video
    if "cc by" in lic.replace("-", " ") or lic.startswith("cc-by"):
        return "attribution"
    return "review"  # fair use, non-free, custom terms


def allowed_by_policy(tier: LicenseTier, policy: str) -> bool:
    if policy == "review":
        return True
    return tier in ("cleared", "attribution")


def score_candidate(
    cand: Candidate,
    brief: VisualBrief,
    entity: EntityInfo | None,
    settings: Settings,
    clip: float | None = None,
) -> ScoredCandidate:
    blob = normalize(cand.text_blob())
    tier = license_tier(cand)
    needs_entity = entity is not None and brief.visual_type != "generic"
    scores = {
        "entity": entity_score(blob, entity if needs_entity else None),
        "source": source_score(cand, brief, settings),
        "context": context_score(blob, cand, brief),
        "clip": 0.5 if clip is None else clip,
        "quality": quality_score(cand),
    }
    weights = ENTITY_WEIGHTS if needs_entity else GENERIC_WEIGHTS
    total = sum(weights[k] * scores[k] for k in weights)

    reason = None
    if _domain_match(cand.source_domain, WATERMARKED):
        reason = "watermarked stock agency"
    elif _domain_match(cand.source_domain, settings.blocked_domains):
        reason = "blocked domain"
    elif cand.width and cand.height and min(cand.width, cand.height) < MIN_SHORT_SIDE:
        reason = "resolution too low"
    elif not allowed_by_policy(tier, settings.license_policy):
        reason = f"license tier '{tier}' not allowed by policy '{settings.license_policy}'"
    elif brief.visual_type in IDENTITY_REQUIRED and needs_entity and scores["entity"] < 1.0:
        reason = "name not found in metadata"
    elif cand.provider == "pexels" and needs_entity:
        reason = "stock photo cannot show a named entity"

    return ScoredCandidate(
        candidate=cand,
        scores={k: round(v, 3) for k, v in scores.items()},
        total=round(total, 4),
        license_tier=tier,
        rejected_reason=reason,
    )
