"""Stage 4: search every provider for each scene and rank the candidates."""

from __future__ import annotations

import logging
from pathlib import Path

from .clip_rank import ClipRanker
from .config import Settings
from .models import Candidate, EntityInfo, SceneFootage, ScoredCandidate, VisualBrief
from .providers import BraveImages, Openverse, Pexels, Provider, SerpApiGoogleImages, WikimediaCommons
from .queries import broad_queries, commons_categories, find_entity, specific_queries
from .scoring import score_candidate

log = logging.getLogger(__name__)

GOOD_ENOUGH = 8  # on-target candidates after which broad queries are skipped
KEEP = 30  # ranked candidates stored per scene
CLIP_TOP = 20  # candidates reranked with CLIP


def build_providers(
    settings: Settings, language: str = "en", cache_dir: Path | None = None
) -> dict[str, Provider]:
    """Providers named in DOCUGEN_PROVIDERS (default: google only)."""
    wanted = set(settings.providers)
    providers: dict[str, Provider] = {}
    if "google" in wanted:
        if not settings.serpapi_api_key:
            raise RuntimeError("Set SERPAPI_API_KEY (or change DOCUGEN_PROVIDERS)")
        providers["google"] = SerpApiGoogleImages(
            settings.serpapi_api_key,
            language=language,
            gl=settings.serpapi_gl,
            tbs=settings.serpapi_tbs,
            cache_dir=cache_dir,
        )
    if "wikimedia" in wanted:
        providers["wikimedia"] = WikimediaCommons()
    if "openverse" in wanted:
        providers["openverse"] = Openverse()
    if "pexels" in wanted and settings.pexels_api_key:
        providers["pexels"] = Pexels(settings.pexels_api_key)
    if "web" in wanted and settings.brave_api_key:
        providers["web"] = BraveImages(settings.brave_api_key)
    return providers


def providers_for(brief: VisualBrief, providers: dict[str, Provider]) -> list[Provider]:
    if brief.visual_type == "generic":
        order = ["google", "pexels", "openverse", "wikimedia"]
    elif brief.visual_type == "place":
        order = ["google", "wikimedia", "openverse", "pexels", "web"]
    else:
        order = ["google", "wikimedia", "openverse", "web"]
    return [providers[name] for name in order if name in providers]


def scene_entity(brief: VisualBrief, entities: list[EntityInfo]) -> EntityInfo | None:
    if brief.visual_type == "generic" or not brief.primary_entity:
        return None
    return find_entity(brief.primary_entity, entities) or EntityInfo(name=brief.primary_entity)


class FootageSearch:
    def __init__(
        self,
        settings: Settings,
        providers: dict[str, Provider],
        entities: list[EntityInfo],
        clip: ClipRanker | None = None,
    ):
        self.settings = settings
        self.providers = providers
        self.entities = entities
        self.clip = clip

    def _run(self, provider: Provider, query: str) -> list[Candidate]:
        try:
            return provider.search(query)
        except Exception as exc:  # one failing source must not stop the scene
            log.warning("%s search failed for %r: %s", provider.name, query, exc)
            return []

    def scene(self, brief: VisualBrief) -> SceneFootage:
        entity = scene_entity(brief, self.entities)
        pool: dict[str, Candidate] = {}

        def add(cands: list[Candidate]) -> None:
            for c in cands:
                pool.setdefault(c.image_url, c)

        def accepted() -> list[ScoredCandidate]:
            scored = [score_candidate(c, brief, entity, self.settings) for c in pool.values()]
            return [s for s in scored if s.rejected_reason is None]

        def on_target() -> int:
            """Candidates that actually show the entity (all of them for generic scenes)."""
            return sum(1 for s in accepted() if entity is None or s.scores["entity"] >= 1.0)

        commons = self.providers.get("wikimedia")
        if isinstance(commons, WikimediaCommons):
            for category in commons_categories(brief, entity):
                try:
                    add(commons.category(category))
                except Exception as exc:
                    log.debug("category %s: %s", category, exc)

        sources = providers_for(brief, self.providers)
        for query in specific_queries(brief)[: self.settings.max_queries]:
            for provider in sources:
                add(self._run(provider, query))

        if on_target() < GOOD_ENOUGH:
            for query in broad_queries(brief):
                for provider in sources:
                    add(self._run(provider, query))

        ranked = sorted(accepted(), key=lambda s: s.total, reverse=True)
        if self.clip and ranked:
            ranked = self._rerank(brief, entity, ranked)
        return SceneFootage(scene_index=brief.scene_index, ranked=ranked[:KEEP])

    def _rerank(
        self, brief: VisualBrief, entity: EntityInfo | None, ranked: list[ScoredCandidate]
    ) -> list[ScoredCandidate]:
        assert self.clip is not None
        head, tail = ranked[:CLIP_TOP], ranked[CLIP_TOP:]
        urls = [s.candidate.thumb_url or s.candidate.image_url for s in head]
        sims = self.clip.score_urls(brief.clip_prompt, urls)
        rescored = [
            score_candidate(s.candidate, brief, entity, self.settings, clip=sim)
            for s, sim in zip(head, sims)
        ]
        return sorted(rescored, key=lambda s: s.total, reverse=True) + tail
