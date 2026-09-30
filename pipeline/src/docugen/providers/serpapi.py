"""Google Images through SerpApi (engine=google_images).

One call returns about 100 images with the original URL, size, title and the
page it comes from. Every response is cached on disk per project so reruns do
not spend searches again.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..http import get_json
from ..models import Candidate
from .base import domain_of

API = "https://serpapi.com/search.json"


class SerpApiGoogleImages:
    name = "google"

    def __init__(
        self,
        api_key: str,
        language: str = "en",
        gl: str | None = None,
        tbs: str | None = None,
        cache_dir: Path | None = None,
    ):
        self.api_key = api_key
        self.params = {"engine": "google_images", "hl": language}
        if gl:
            self.params["gl"] = gl
        if tbs:
            self.params["tbs"] = tbs
        self.cache_dir = cache_dir

    def _cache_path(self, query: str) -> Path | None:
        if self.cache_dir is None:
            return None
        key = json.dumps({"q": query, **self.params}, sort_keys=True)
        return self.cache_dir / f"{hashlib.sha1(key.encode()).hexdigest()}.json"

    def _fetch(self, query: str) -> dict:
        cache = self._cache_path(query)
        if cache is not None and cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        data = get_json(API, {**self.params, "q": query, "api_key": self.api_key})
        if data.get("error") and not data.get("images_results"):
            # "Google hasn't returned any results" is a normal empty answer; cache it too.
            if "hasn't returned any results" not in str(data["error"]):
                raise RuntimeError(f"SerpApi: {data['error']}")
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def search(self, query: str, limit: int = 100) -> list[Candidate]:
        out = []
        for r in self._fetch(query).get("images_results", [])[:limit]:
            image_url = r.get("original")
            if not image_url or r.get("is_product"):
                continue
            out.append(
                Candidate(
                    provider="google",
                    image_url=image_url,
                    thumb_url=r.get("thumbnail"),
                    page_url=r.get("link"),
                    title=r.get("title") or "",
                    description=r.get("source") or "",
                    width=r.get("original_width"),
                    height=r.get("original_height"),
                    query=query,
                    source_domain=domain_of(r.get("link")) or r.get("source"),
                )
            )
        return out
