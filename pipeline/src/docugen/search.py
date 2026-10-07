"""Image search through third-party APIs: Google (DataForSEO), Bing (SearchAPI.io), Brave.

Every raw response is cached per project (cache/<source>/), so reruns cost nothing.
We never scrape Google, Bing, Pinterest or YouTube ourselves.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import Settings
from .http import request_json
from .languages import Language
from .models import ImageHit

log = logging.getLogger(__name__)


# Video thumbnails and covers (often with big text and a channel's branding) are never usable images
VIDEO_THUMB_DOMAINS = (
    "youtube.com", "youtu.be", "ytimg.com", "yt3.ggpht.com", "yt3.googleusercontent.com",
    "tiktok.com", "tiktokcdn.com", "tiktokcdn-us.com",
)
# YouTube thumbnail file names, also when another site re-hosts them ("1663797909_hqdefault.jpg")
VIDEO_THUMB_FILE = re.compile(r"(maxresdefault|hqdefault|sddefault|mqdefault|hq720)(_live)?\.(jpe?g|webp|png)$", re.I)


def is_video_thumbnail(h: ImageHit) -> bool:
    domains = [d for d in (h.domain, domain_of(h.image_url)) if d]
    if any(d == v or d.endswith("." + v) for d in domains for v in VIDEO_THUMB_DOMAINS):
        return True
    return bool(VIDEO_THUMB_FILE.search(urlparse(h.image_url).path.rsplit("/", 1)[-1]))


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.") or None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def hit(source: str, query: str, rank: int, image_url: str, page_url: str | None, title: str | None,
        width: Any = None, height: Any = None) -> ImageHit:
    return ImageHit(
        id=hashlib.sha1(image_url.encode()).hexdigest()[:10],
        source=source,
        image_url=image_url,
        page_url=page_url,
        title=(title or "").strip(),
        domain=domain_of(page_url) or domain_of(image_url),
        width=_int(width),
        height=_int(height),
        query=query,
        rank=rank,
    )


class Source:
    """Caches one raw JSON response per query; subclasses fetch and parse."""

    name = ""

    def __init__(self, lang: Language, settings: Settings, cache_dir: Path):
        self.lang = lang
        self.settings = settings
        self.cache_dir = cache_dir / self.name
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def params_key(self) -> dict:
        return {}

    def cache_path(self, query: str, suffix: str = ".json") -> Path:
        key = json.dumps({"q": query, **self.params_key()}, sort_keys=True, ensure_ascii=False)
        return self.cache_dir / (hashlib.sha1(key.encode()).hexdigest() + suffix)

    def fetch(self, query: str) -> Any:
        raise NotImplementedError

    def fetch_many(self, queries: list[str]) -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = pool.map(self._fetch_safe, queries)
        return {q: r for q, r in zip(queries, results) if r is not None}

    def _fetch_safe(self, query: str) -> Any:
        try:
            return self.fetch(query)
        except Exception as exc:  # one failed query must not stop the whole search
            log.warning("%s: '%s' failed: %s", self.name, query, exc)
            return None

    def parse(self, query: str, raw: Any) -> list[ImageHit]:
        raise NotImplementedError

    def search_many(self, queries: list[str]) -> dict[str, list[ImageHit]]:
        queries = list(dict.fromkeys(queries))
        raws: dict[str, Any] = {}
        missing = []
        for q in queries:
            path = self.cache_path(q)
            if path.exists():
                raws[q] = json.loads(path.read_text(encoding="utf-8"))
            else:
                missing.append(q)
        if missing:
            log.info("%s: %d searches (%d cached)", self.name, len(missing), len(queries) - len(missing))
            for q, raw in self.fetch_many(missing).items():
                self.cache_path(q).write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
                raws[q] = raw
        return {q: self.parse(q, raws[q]) for q in queries if q in raws}


class DataForSEOImages(Source):
    """Google Images. Standard queue by default: post every query at once, then collect."""

    name = "dataforseo"
    API = "https://api.dataforseo.com/v3/serp/google/images"
    READY, PENDING = 20000, (40601, 40602)

    def params_key(self) -> dict:
        return {"lang": self.lang.code, "loc": self.location}

    @property
    def location(self) -> int:
        return self.settings.dataforseo_location or self.lang.dataforseo_location

    def _auth(self) -> tuple[str, str] | None:
        # None: the environment's API credential proxy adds the Authorization header.
        s = self.settings
        return (s.dataforseo_login, s.dataforseo_password) if s.dataforseo_login and s.dataforseo_password else None

    def _task(self, query: str) -> dict:
        return {"keyword": query, "language_code": self.lang.code, "location_code": self.location,
                "depth": 100}

    def fetch(self, query: str) -> Any:  # live mode, one query per call
        data = request_json("POST", f"{self.API}/live/advanced", json=[self._task(query)], auth=self._auth())
        return self._result(data["tasks"][0])

    def _result(self, task: dict) -> dict:
        if task.get("status_code") != self.READY:
            raise RuntimeError(f"{task.get('status_code')} {task.get('status_message')}")
        return (task.get("result") or [{}])[0] or {}

    def fetch_many(self, queries: list[str]) -> dict[str, Any]:
        if self.settings.dataforseo_live:
            return super().fetch_many(queries)
        # Post the queries that have no task yet; a task id file survives an interrupted run.
        pending: dict[str, str] = {}
        to_post = []
        for q in queries:
            task_file = self.cache_path(q, ".task")
            if task_file.exists():
                pending[q] = task_file.read_text().strip()
            else:
                to_post.append(q)
        for start in range(0, len(to_post), 100):
            chunk = to_post[start : start + 100]
            data = request_json("POST", f"{self.API}/task_post", json=[self._task(q) for q in chunk],
                                auth=self._auth())
            for q, task in zip(chunk, data["tasks"]):
                if task.get("status_code") != 20100:
                    log.warning("dataforseo: '%s' not queued: %s", q, task.get("status_message"))
                    continue
                pending[q] = task["id"]
                self.cache_path(q, ".task").write_text(task["id"])

        out: dict[str, Any] = {}
        deadline = time.monotonic() + 20 * 60
        while pending and time.monotonic() < deadline:
            time.sleep(10)
            for q, task_id in list(pending.items()):
                data = request_json("GET", f"{self.API}/task_get/advanced/{task_id}", auth=self._auth())
                task = data["tasks"][0]
                if task.get("status_code") in self.PENDING:
                    continue
                del pending[q]
                self.cache_path(q, ".task").unlink(missing_ok=True)
                try:
                    out[q] = self._result(task)
                except RuntimeError as exc:
                    log.warning("dataforseo: '%s' failed: %s", q, exc)
            log.info("dataforseo: %d ready, %d waiting", len(out), len(pending))
        if pending:
            log.warning("dataforseo: %d tasks still queued; rerun to collect them", len(pending))
        return out

    def parse(self, query: str, raw: Any) -> list[ImageHit]:
        items = [i for i in raw.get("items") or [] if i.get("type") == "images_search" and i.get("source_url")]
        return [
            hit(self.name, query, rank, i["source_url"], i.get("url"), i.get("title") or i.get("alt"))
            for rank, i in enumerate(items, start=1)
        ]


class BingImages(Source):
    """Bing Images through SearchAPI.io."""

    name = "bing"
    API = "https://www.searchapi.io/api/v1/search"

    def params_key(self) -> dict:
        return {"market": self.lang.bing_market}

    def fetch(self, query: str) -> Any:
        key = self.settings.searchapi_api_key
        headers = {"Authorization": f"Bearer {key}"} if key else None
        return request_json("GET", self.API, headers=headers, params={
            "engine": "bing_images", "q": query, "market_code": self.lang.bing_market,
        })

    def parse(self, query: str, raw: Any) -> list[ImageHit]:
        out = []
        for rank, r in enumerate(raw.get("images") or [], start=1):
            original = r.get("original") or {}
            if not original.get("link"):
                continue
            page = (r.get("source") or {}).get("link")
            out.append(hit(self.name, query, rank, original["link"], page, r.get("title"),
                           original.get("width"), original.get("height")))
        return out


class GoogleImages(BingImages):
    """Google Images through SearchAPI.io: 100 results per call, same JSON shape as Bing."""

    name = "google"

    def params_key(self) -> dict:
        return {"gl": self._country(), "hl": self.lang.code}

    def _country(self) -> str:
        return self.lang.bing_market.split("-")[-1].lower()

    def fetch(self, query: str) -> Any:
        key = self.settings.searchapi_api_key
        headers = {"Authorization": f"Bearer {key}"} if key else None
        return request_json("GET", self.API, headers=headers, params={
            "engine": "google_images", "q": query, "gl": self._country(), "hl": self.lang.code,
        })


class BraveImages(Source):
    """Brave Image Search: its own index, up to 200 results per call."""

    name = "brave"
    API = "https://api.search.brave.com/res/v1/images/search"

    def params_key(self) -> dict:
        return {"lang": self.lang.code, "safe": self.settings.brave_safesearch,
                "country": self.settings.brave_country}

    def fetch(self, query: str) -> Any:
        params = {"q": query, "count": "200", "search_lang": self.lang.code,
                  "safesearch": self.settings.brave_safesearch}
        if self.settings.brave_country:
            params["country"] = self.settings.brave_country
        headers = {"Accept": "application/json"}
        if self.settings.brave_api_key:
            headers["X-Subscription-Token"] = self.settings.brave_api_key
        return request_json("GET", self.API, params=params, headers=headers)

    def fetch_many(self, queries: list[str]) -> dict[str, Any]:
        """One call at a time, spaced by brave_interval: parallel calls hit the per second limit."""
        out = {}
        for i, q in enumerate(queries):
            if i:
                time.sleep(self.settings.brave_interval)
            raw = self._fetch_safe(q)
            if raw is not None:
                out[q] = raw
        return out

    def parse(self, query: str, raw: Any) -> list[ImageHit]:
        out = []
        for rank, r in enumerate(raw.get("results") or [], start=1):
            props = r.get("properties") or {}
            if not props.get("url"):
                continue
            out.append(hit(self.name, query, rank, props["url"], r.get("url"), r.get("title"),
                           props.get("width"), props.get("height")))
        return out


SOURCE_CLASSES: dict[str, tuple[type[Source], tuple[str, ...]]] = {
    "dataforseo": (DataForSEOImages, ("dataforseo_login", "dataforseo_password")),
    "google": (GoogleImages, ("searchapi_api_key",)),
    "bing": (BingImages, ("searchapi_api_key",)),
    "brave": (BraveImages, ("brave_api_key",)),
}


def build_sources(settings: Settings, lang: Language, cache_dir: Path) -> list[Source]:
    sources = []
    for name in settings.sources:
        if name not in SOURCE_CLASSES:
            raise ValueError(f"Unknown source '{name}' in DOCUGEN_SEARCH (use {', '.join(SOURCE_CLASSES)})")
        cls, keys = SOURCE_CLASSES[name]
        if not all(getattr(settings, k) for k in keys):
            # Fine in a cloud environment whose API credentials add the key on the way out.
            log.info("%s: %s not set, relying on the environment's API credentials",
                     name, ", ".join(k.upper() for k in keys))
        sources.append(cls(lang, settings, cache_dir))
    if not sources:
        raise RuntimeError("DOCUGEN_SEARCH lists no image source")
    return sources


def search_queries(sources: list[Source], queries: list[str]) -> dict[str, dict[str, list[ImageHit]]]:
    """{query: {source: hits}} for every source, the sources running side by side."""
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        per_source = dict(zip([s.name for s in sources], pool.map(lambda s: s.search_many(queries), sources)))
    return {q: {name: res.get(q, []) for name, res in per_source.items()} for q in queries}


def merge(results: dict[str, list[ImageHit]], per_source: int, blocked: list[str],
          existing: list[ImageHit] | None = None) -> list[ImageHit]:
    """Interleave sources (Google 1, Bing 1, Brave 1, Google 2...) and drop repeats, blocked sites
    and video thumbnails."""
    out = list(existing or [])
    seen = {h.image_url for h in out}

    def allowed(h: ImageHit) -> bool:
        domains = [d for d in (h.domain, domain_of(h.image_url)) if d]
        if is_video_thumbnail(h):
            return False
        return not any(d == b or d.endswith("." + b) for d in domains for b in blocked)

    lists = [[h for h in hits if allowed(h)][:per_source] for hits in results.values()]
    for i in range(max((len(x) for x in lists), default=0)):
        for hits in lists:
            if i < len(hits) and hits[i].image_url not in seen:
                seen.add(hits[i].image_url)
                out.append(hits[i])
    return out
