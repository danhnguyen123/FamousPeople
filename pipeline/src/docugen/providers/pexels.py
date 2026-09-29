"""Pexels: free stock photos for generic / mood scenes. Never used for named people."""

from __future__ import annotations

from ..http import get_json
from ..models import Candidate

API = "https://api.pexels.com/v1/search"


class Pexels:
    name = "pexels"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, limit: int = 15) -> list[Candidate]:
        data = get_json(
            API,
            {"query": query, "per_page": str(limit), "orientation": "landscape"},
            headers={"Authorization": self.api_key},
        )
        return [
            Candidate(
                provider="pexels",
                image_url=p["src"].get("large2x") or p["src"]["original"],
                thumb_url=p["src"].get("medium"),
                page_url=p.get("url"),
                title=p.get("alt") or "",
                author=p.get("photographer"),
                license="Pexels License",
                license_url="https://www.pexels.com/license/",
                width=p.get("width"),
                height=p.get("height"),
                query=query,
                source_domain="pexels.com",
            )
            for p in data.get("photos", [])
        ]
