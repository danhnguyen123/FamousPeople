"""Brave Image Search: open web discovery (magazine scans, fan archives, Pinterest pages...).

Enabled whenever BRAVE_API_KEY is set. This goes through a search API;
it never scrapes Pinterest or Google directly.
"""

from __future__ import annotations

from ..http import get_json
from ..models import Candidate
from .base import domain_of

API = "https://api.search.brave.com/res/v1/images/search"


class BraveImages:
    name = "web"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, limit: int = 40) -> list[Candidate]:
        data = get_json(
            API,
            {"q": query, "count": str(min(limit, 100)), "safesearch": "strict"},
            headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
        )
        out = []
        for r in data.get("results", []):
            props = r.get("properties") or {}
            image_url = props.get("url") or (r.get("thumbnail") or {}).get("src")
            if not image_url:
                continue
            out.append(
                Candidate(
                    provider="web",
                    image_url=image_url,
                    thumb_url=(r.get("thumbnail") or {}).get("src"),
                    page_url=r.get("url"),
                    title=r.get("title") or "",
                    width=props.get("width"),
                    height=props.get("height"),
                    query=query,
                    source_domain=domain_of(r.get("url")) or r.get("source"),
                )
            )
        return out
